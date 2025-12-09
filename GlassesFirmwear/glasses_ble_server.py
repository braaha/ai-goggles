#!/usr/bin/env python3 
# glasses_ble_server 1.4.1
import json
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import subprocess
import os
import time
import threading
import queue
import boto3
from datetime import datetime, timezone

# DEVICE ID - CHANGE THIS PER DEVICE
DEVICE_ID = "glasses-001"  

# RECORDINGS DIRECTORY
RECORDINGS_DIR = f"/home/{DEVICE_ID}/glasses/videos"
os.makedirs(RECORDINGS_DIR, exist_ok=True)
print("[REC] Saving videos to:", RECORDINGS_DIR)

# AWS S3 CONFIG
S3_BUCKET = "smart-glasses-videos-460"
S3_PREFIX = f"devices/{DEVICE_ID}"
SIGNED_URL_TTL = 3600
s3 = boto3.client("s3")
MAX_RECORDINGS_PER_PAGE = 4

# Global recording state
video_proc = None
audio_proc = None
loop_recording = False
segment_seconds = 900
AUDIO_LEAD_SEC = 1.5

# Upload queue and threads
segment_queue = queue.Queue()
recording_thread = None
uploader_thread = None

# BLUEZ / DBUS CONSTANTS
BLUEZ_SERVICE_NAME = 'org.bluez'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'

# UUIDs
GLASSES_SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CONTROL_CHAR_UUID    = '12345678-1234-5678-1234-56789abcdef1'
STATUS_CHAR_UUID     = '12345678-1234-5678-1234-56789abcdef2'

last_status_payload = "IDLE"


def build_recordings_index():
    entries = []
    prefix = f"{S3_PREFIX}/"  

    continuation_token = None

    while True:
        kwargs = {
            "Bucket": S3_BUCKET,
            "Prefix": prefix,
        }
        if continuation_token is not None:
            kwargs["ContinuationToken"] = continuation_token

        resp = s3.list_objects_v2(**kwargs)

        for obj in resp.get("Contents", []):
            key = obj["Key"]  
            if not key.lower().endswith(".mp4"):
                continue

            fname = key.split("/")[-1]
            rec_id = os.path.splitext(fname)[0]

            started_at = parse_started_at_from_key(key, obj.get("LastModified"))

            entries.append({
                "id": rec_id,
                "fileName": fname,
                "startedAt": started_at,
            })

        
        if resp.get("IsTruncated"):
            continuation_token = resp.get("NextContinuationToken")
        else:
            break

    
    entries.sort(key=lambda x: x["startedAt"], reverse=True)
    print(f"[IDX] Built index from S3 with {len(entries)} recordings")
    return entries


def get_presigned_url_for_recording(rec_id: str) -> str:

    key = f"{S3_PREFIX}/{rec_id}.mp4"
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=SIGNED_URL_TTL,
        )
        return url
    except Exception as e:
        print(f"[URL] Failed to generate signed URL for {key}: {e}")
        return ""


def parse_started_at_from_key(key: str, last_modified) -> str:

    try:
        fname = key.split("/")[-1]  
        base, _ = os.path.splitext(fname) 
        prefix = "rec_"

        if base.startswith(prefix):
            ts_str = base[len(prefix):]  
            dt = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
    except Exception as e:
        print(f"[IDX] Failed to parse timestamp from key {key}: {e}")

    try:
        if isinstance(last_modified, datetime):
            dt = last_modified.astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
    except Exception as e:
        print(f"[IDX] Failed to use LastModified for key {key}: {e}")


    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def upload_video_to_s3(path: str):
    if not os.path.exists(path):
        print("[S3] File not found:", path)
        return

    filename = os.path.basename(path)
    s3_key = f"{S3_PREFIX}/{filename}"

    cmd = [
        "aws", "s3", "cp",
        path,
        f"s3://{S3_BUCKET}/{s3_key}",
    ]

    print("[S3] Uploading:", path, "->", f"s3://{S3_BUCKET}/{s3_key}")
    print("[S3] Running:", " ".join(cmd))

    try:
        subprocess.check_call(cmd)
        print("[S3] Upload successful:", s3_key)
        os.remove(path)
    except subprocess.CalledProcessError as e:
        print("[S3] Upload failed with code", e.returncode)


def recording_loop():
    global loop_recording, segment_seconds
    global video_proc, audio_proc

    print("[REC] recording_loop started, loop_recording =", loop_recording)

    while loop_recording:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        raw_video = os.path.join(RECORDINGS_DIR, f"rec_{timestamp}.h264")
        raw_audio = os.path.join(RECORDINGS_DIR, f"rec_{timestamp}.wav")
        mp4_path  = os.path.join(RECORDINGS_DIR, f"rec_{timestamp}.mp4")


        video_cmd = [
            "rpicam-vid",
            "-t", str(segment_seconds * 1000),  
            "--width", "1280",
            "--height", "720",
            "--framerate", "30",
            "-o", raw_video,
        ]


        audio_cmd = [
            "arecord",
            "-D", "plughw:0,0",
            "-c2",
            "-r", "48000",
            "-f", "S32_LE",
            "-t", "wav",
            "-d", str(segment_seconds),
            raw_audio,
        ]
        print("[REC] Starting new segment at timestamp", timestamp)
        print("[REC] Video cmd:", " ".join(video_cmd))
        print("[REC] Audio cmd:", " ".join(audio_cmd))

        try:
            video_proc = subprocess.Popen(video_cmd)
            audio_proc = subprocess.Popen(audio_cmd)

            # These waits will return early if STOP kills the procs
            video_ret = video_proc.wait()
            audio_ret = audio_proc.wait()

            print(f"[REC] Video process exited with {video_ret}")
            print(f"[REC] Audio process exited with {audio_ret}")
        except Exception as e:
            print("[REC] Error running video/audio:", e)
            video_proc = None
            audio_proc = None
            break
        finally:
            video_proc = None
            audio_proc = None


        if os.path.exists(raw_video) and os.path.getsize(raw_video) > 0 \
           and os.path.exists(raw_audio) and os.path.getsize(raw_audio) > 0:
            print("[REC] Queuing segment for processing:", raw_video, raw_audio, "->", mp4_path)
            segment_queue.put((raw_video, raw_audio, mp4_path))
        else:
            print("[REC] Skipping segment, missing or empty raw files:",
                  raw_video, raw_audio)

        if not loop_recording:
            print("[REC] Loop flag cleared after segment, exiting loop")
            break

    print("[REC] Recording loop exited")


def uploader_worker():

    print("[UP] Uploader worker started")

    while True:
        item = segment_queue.get()   # blocking

        if item is None:
            # Sentinel for clean shutdown if you ever want it
            print("[UP] Got sentinel, exiting uploader worker")
            break

        raw_video, raw_audio, mp4_path = item
        print(f"[UP] Processing segment:\n  video={raw_video}\n  audio={raw_audio}\n  mp4={mp4_path}")

        # Sanity check: files exist
        if not os.path.exists(raw_video):
            print("[UP] ERROR: raw video missing:", raw_video)
            segment_queue.task_done()
            continue
        if not os.path.exists(raw_audio):
            print("[UP] ERROR: raw audio missing:", raw_audio)
            segment_queue.task_done()
            continue

        # --- Mux into MP4 (same as you had before) ---
        audio_filter = (
            f"asetpts=PTS-{AUDIO_LEAD_SEC}/TB,"
            "pan=mono|c0=0.5*c0+0.5*c1,volume=8.0"
        )

        cmd_wrap = [
            "ffmpeg",
            "-y",
            "-r", "30",
            "-i", raw_video,
            "-i", raw_audio,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-filter:a", audio_filter,
            "-movflags", "+faststart",
            mp4_path,
        ]

        print("[UP] Muxing A/V -> MP4:", " ".join(cmd_wrap))
        try:
            wrap_proc = subprocess.Popen(
                cmd_wrap,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            wrap_output, _ = wrap_proc.communicate()
            print("[UP] ffmpeg output:\n", wrap_output)
        except Exception as e:
            print("[UP] ERROR during ffmpeg mux:", e)
            segment_queue.task_done()
            continue

        # If MP4 exists, clean up raw files
        if os.path.exists(mp4_path):
            try:
                os.remove(raw_video)
                os.remove(raw_audio)
            except Exception as e:
                print("[UP] Warning: failed to remove raw files:", e)

        # Upload to S3
        try:
            upload_video_to_s3(mp4_path)
        except Exception as e:
            print("[S3] Unexpected error during upload:", e)

        segment_queue.task_done()


def start_segmented_recording(seconds):
    global loop_recording, segment_seconds, uploader_thread

    if seconds <= 0:
        print("[REC] Invalid segment length, ignoring:", seconds)
        return

    if loop_recording:
        print("[REC] Already in segmented recording mode, ignoring START")
        return

    segment_seconds = seconds
    loop_recording = True
    print(f"[REC] Starting segmented recording, {segment_seconds}s per file")

    if uploader_thread is None or not uploader_thread.is_alive():
        print("[UP] Starting uploader worker thread")
        uploader_thread = threading.Thread(
            target=uploader_worker,
            name="uploader_worker",
            daemon=True,
        )
        uploader_thread.start()

    t = threading.Thread(target=recording_loop, daemon=True)
    t.start()
    print("[REC] Recording thread started, id:", t.ident)


def stop_recording():
    global loop_recording, video_proc, audio_proc
    print("[REC] STOP requested")
    loop_recording = False

    for name, proc in (("video", video_proc), ("audio", audio_proc)):
        if proc is not None:
            print(f"[REC] Terminating {name} recording process")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[REC] Force-killing {name} recording process")
                proc.kill()

    video_proc = None
    audio_proc = None


def get_status_string():
    if loop_recording:
        return "RECORDING"
    else:
        return "IDLE"


def update_status_payload(payload: str):
    global last_status_payload
    last_status_payload = payload
    print("[STATUS] Updated status payload:", payload)


def get_wifi_status_payload():

    ssid = None
    ip = None

    # Try iwgetid to see current SSID
    try:
        out = subprocess.check_output(
            ["iwgetid", "-r"],
            stderr=subprocess.STDOUT,
            text=True
        ).strip()
        if out:
            ssid = out
    except Exception as e:
        print("[WIFI] iwgetid failed:", e)

    if ssid:
        # Try to get an IPv4 address
        try:
            ip_out = subprocess.check_output(
                ["hostname", "-I"],
                stderr=subprocess.STDOUT,
                text=True
            ).strip()
            if ip_out:
                ip = ip_out.split()[0]
        except Exception as e:
            print("[WIFI] hostname -I failed:", e)

        if ip:
            return f"WIFI:CONNECTED:{ssid}:{ip}"
        else:
            return f"WIFI:CONNECTED:{ssid}"
    else:
        # Not connected (or unable to detect)
        return "WIFI:DISCONNECTED"


def configure_wifi_async(ssid: str, password: str):

    def worker():
        con_name = "glasses-wifi"
        print(f"[WIFI] Configuring Wi-Fi SSID='{ssid}' via '{con_name}'")
        update_status_payload("WIFI:CONNECTING")

        try:
            # 1) Delete any existing connection with our fixed name
            try:
                delete_cmd = ["nmcli", "connection", "delete", con_name]
                print("[WIFI] Running:", " ".join(delete_cmd))
                subprocess.run(
                    delete_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=10,
                )
            except Exception as e:
                print("[WIFI] Warning: failed to delete old connection:", e)

            # 2) Add a fresh WPA-PSK Wi-Fi connection
            add_cmd = [
                "nmcli", "connection", "add",
                "type", "wifi",
                "ifname", "wlan0",
                "con-name", con_name,
                "ssid", ssid,
                "wifi-sec.key-mgmt", "wpa-psk",
                "wifi-sec.psk", password,
                "ipv4.method", "auto",
                "ipv6.method", "auto",
            ]
            print("[WIFI] Running:", " ".join(add_cmd))
            add_res = subprocess.run(
                add_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
            )
            print("[WIFI] nmcli add output:\n", add_res.stdout)

            if add_res.returncode != 0:
                print("[WIFI] nmcli add failed with code", add_res.returncode)
                update_status_payload("WIFI:DISCONNECTED")
                return

            # 3) Bring it up
            up_cmd = ["nmcli", "connection", "up", con_name]
            print("[WIFI] Running:", " ".join(up_cmd))
            up_res = subprocess.run(
                up_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=45,
            )
            print("[WIFI] nmcli up output:\n", up_res.stdout)

            if up_res.returncode == 0:
                time.sleep(2)
                payload = get_wifi_status_payload()
                update_status_payload(payload)
            else:
                print("[WIFI] nmcli up failed with code", up_res.returncode)
                out = up_res.stdout or ""
                if "No network with SSID" in out:
                    update_status_payload(f"WIFI:NOT_FOUND:{ssid}")
                elif "Secrets were required" in out or "wrong password" in out.lower():
                    update_status_payload("WIFI:BAD_PASSWORD")
                else:
                    update_status_payload("WIFI:DISCONNECTED")

        except FileNotFoundError:
            print("[WIFI] nmcli not found on this system")
            update_status_payload("WIFI:DISCONNECTED")
        except Exception as e:
            print("[WIFI] Error configuring Wi-Fi:", e)
            update_status_payload("WIFI:DISCONNECTED")

    threading.Thread(target=worker, daemon=True).start()


# ==== GATT APPLICATION / SERVICE / CHARACTERISTIC CLASSES ====
class Application(dbus.service.Object):

    def __init__(self, bus):
        self.path = '/'
        self.services = []
        super().__init__(bus, self.path)

    def add_service(self, service):
        self.services.append(service)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_OM_IFACE,
                         out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for ch in service.characteristics:
                response[ch.get_path()] = ch.get_properties()
        return response


class Service(dbus.service.Object):

    PATH_BASE = '/org/glasses/service'

    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary,
                'Characteristics': dbus.Array(
                    [ch.get_path() for ch in self.characteristics],
                    signature='o'
                ),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, chrc):
        self.characteristics.append(chrc)


class Characteristic(dbus.service.Object):

    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.get_path() + '/char' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.service = service
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self.service.get_path(),
                'UUID': self.uuid,
                'Flags': self.flags,
                'Descriptors': dbus.Array([], signature='o'),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        print("[GATT] Base WriteValue, ignoring:", value)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        print("[GATT] Base ReadValue, returning empty")
        return dbus.ByteArray(b'')


# CONTROL CHARACTERISTIC CLASS
class ControlCharacteristic(Characteristic):
    # Write-only characteristic for receiving commands  

    def __init__(self, bus, index, service):
        super().__init__(bus, index, CONTROL_CHAR_UUID,
                         ['write-without-response', 'write'], service)

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        raw = bytes(value).decode('utf-8').strip()
        cmd = raw.upper()
        print("[CTRL] Received raw command:", raw)

        # Start recording command
        if cmd.startswith("START"):
            parts = raw.split(":")
            if len(parts) == 2:
                try:
                    seconds = int(parts[1])
                except ValueError:
                    print("[CTRL] Invalid seconds in START command, using default:", segment_seconds)
                    seconds = segment_seconds
            else:
                seconds = segment_seconds

            print(f"[CTRL] START with segment length {seconds}s")
            start_segmented_recording(seconds)
            update_status_payload(get_status_string())

        # Stop recording command
        elif cmd == "STOP":
            print("[CTRL] STOP")
            stop_recording()
            update_status_payload(get_status_string())

        # Wi-Fi status request
        elif cmd == "GET_WIFI":
            print("[CTRL] Wi-Fi status requested")
            payload = get_wifi_status_payload()
            update_status_payload(payload)

        # Configure Wi-Fi from the app:
        elif cmd.startswith("SET_WIFI:"):
            parts = raw.split(":", 2)
            if len(parts) != 3:
                print("[CTRL] Invalid SET_WIFI format, expected SET_WIFI:<ssid>:<password>")
                update_status_payload("WIFI:DISCONNECTED")
                return

            ssid = parts[1]
            password = parts[2]
            print(f"[CTRL] SET_WIFI for SSID='{ssid}'")
            configure_wifi_async(ssid, password)

        elif cmd.startswith("GET_RECORDINGS"):
            # Optional format: GET_RECORDINGS or GET_RECORDINGS:<offset>
            offset = 0
            parts = raw.split(":", 1)
            if len(parts) == 2:
                try:
                    offset = int(parts[1])
                except ValueError:
                    print("[CTRL] Invalid offset in GET_RECORDINGS, using 0")
                    offset = 0

            print(f"[CTRL] iOS requested recordings index from offset {offset}")
            try:
                all_entries = build_recordings_index()
                page = all_entries[offset:offset + MAX_RECORDINGS_PER_PAGE]
                payload = json.dumps(page)
                update_status_payload(payload)
            except Exception as e:
                print("[CTRL] Error building recordings index:", e)
                update_status_payload("[]")


        elif cmd.startswith("GET_URL:"):
            # Example raw: "GET_URL:rec_2025-12-08_22-16-57"
            parts = raw.split(":", 1)
            if len(parts) != 2:
                print("[CTRL] Invalid GET_URL format")
                update_status_payload("URL:ERROR")
                return

            rec_id = parts[1]
            print(f"[CTRL] GET_URL for recording id '{rec_id}'")

            url = get_presigned_url_for_recording(rec_id)
            if url:
                # We prefix with "URL:" so the app can distinguish it
                update_status_payload(f"URL:{url}")
            else:
                update_status_payload("URL:ERROR")


        else:
            print("[CTRL] Unknown command:", cmd)


# STATUS CHARACTERISTIC CLASS
class StatusCharacteristic(Characteristic):
    # Read/Notify characteristic for status updates

    subscribers = [] 

    def __init__(self, bus, index, service):
        super().__init__(bus, index, STATUS_CHAR_UUID, ['read', 'notify'], service)

    @dbus.service.method(GATT_CHRC_IFACE,
                         in_signature='a{sv}',
                         out_signature='ay')
    
    def ReadValue(self, options):
        global last_status_payload
        full = (last_status_payload or "IDLE").encode("utf-8")

        # offset is a uint16 in ATT; BlueZ passes it in options["offset"]
        offset = int(options.get("offset", 0))

        if offset >= len(full):
            chunk = b""
        else:
            chunk = full[offset:]

        print(f"[STATUS] ReadValue offset={offset} -> len={len(chunk)}")
        return dbus.ByteArray(chunk)

    ### NEW — BLE notification support
    @staticmethod
    def notify(data: bytes):
        for sub in StatusCharacteristic.subscribers:
            try:
                sub.PropertiesChanged(
                    GATT_CHRC_IFACE,
                    {"Value": dbus.ByteArray(data)},
                    []
                )
            except Exception as e:
                print("[BLE] Notify error:", e)

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        if self not in StatusCharacteristic.subscribers:
            StatusCharacteristic.subscribers.append(self)
        print("[BLE] StatusCharacteristic subscribed")

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        if self in StatusCharacteristic.subscribers:
            StatusCharacteristic.subscribers.remove(self)
        print("[BLE] StatusCharacteristic unsubscribed")


# SERVICE CLASS
class GlassesService(Service):
    #Main service that defines all Bluetooth characteristics for the glasses.

    def __init__(self, bus, index):
        super().__init__(bus, index, GLASSES_SERVICE_UUID, True)

        # Add control and status characteristics
        self.add_characteristic(ControlCharacteristic(bus, 0, self))
        self.add_characteristic(StatusCharacteristic(bus, 1, self))


# ADVERTISEMENT CLASS 
class Advertisement(dbus.service.Object):

    PATH_BASE = '/org/glasses/advertisement'

    def __init__(self, bus, index, advertising_type, service_uuids, local_name):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = service_uuids
        self.local_name = local_name
        super().__init__(bus, self.path)

    def get_properties(self):
        return {
            'org.bluez.LEAdvertisement1': {
                'Type': self.ad_type,  # "peripheral"
                'ServiceUUIDs': dbus.Array(self.service_uuids, signature='s'),
                'LocalName': self.local_name,
                'Includes': dbus.Array(['tx-power'], signature='s'),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != 'org.bluez.LEAdvertisement1':
            return {}
        return self.get_properties()['org.bluez.LEAdvertisement1']

    @dbus.service.method('org.bluez.LEAdvertisement1')
    def Release(self):
        print("[ADV] Advertisement released")


# HELPER: FIND ADAPTER 
def find_adapter_path(bus):
    om = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, "/"),
        DBUS_OM_IFACE
    )
    objects = om.GetManagedObjects()
    for path, ifaces in objects.items():
        if 'org.bluez.Adapter1' in ifaces:
            return path
    return None


# MAIN 
def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = find_adapter_path(bus)
    if adapter_path is None:
        raise RuntimeError("No Bluetooth adapter found")

    print("[BLE] Using adapter:", adapter_path)

    service_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
        GATT_MANAGER_IFACE
    )

    adv_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
        ADVERTISING_MANAGER_IFACE
    )

    app = Application(bus)
    app.add_service(GlassesService(bus, 0))

    adv = Advertisement(
        bus,
        index=0,
        advertising_type='peripheral',
        service_uuids=[GLASSES_SERVICE_UUID],
        local_name=DEVICE_ID 
    )

    mainloop = GLib.MainLoop()

    def on_app_reg_ok():
        print("[BLE] GATT application registered")

    def on_app_reg_err(e):
        print("[BLE] Failed to register GATT application:", e)
        mainloop.quit()

    def on_adv_reg_ok():
        print("[BLE] Advertisement registered")

    def on_adv_reg_err(e):
        print("[BLE] Failed to register advertisement:", e)
        mainloop.quit()

    print("[BLE] Registering GATT application...")
    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=on_app_reg_ok,
        error_handler=on_app_reg_err
    )

    print("[BLE] Registering advertisement...")
    adv_manager.RegisterAdvertisement(
        adv.get_path(),
        {},
        reply_handler=on_adv_reg_ok,
        error_handler=on_adv_reg_err
    )

    try:
        mainloop.run()
    except KeyboardInterrupt:
        print("\n[BLE] Exiting")


if __name__ == "__main__":
    main()
