import Foundation
import CoreBluetooth
import Combine

// Must match the Pi’s UUIDs
let glassesServiceUUID = CBUUID(string: "12345678-1234-5678-1234-56789ABCDEF0")
let controlCharUUID    = CBUUID(string: "12345678-1234-5678-1234-56789ABCDEF1")
let statusCharUUID     = CBUUID(string: "12345678-1234-5678-1234-56789ABCDEF2")

enum GlassesConnectionState {
    case disconnected
    case scanning
    case connecting
    case connected
}

enum GlassesWifiState {
    case unknown
    case notConfigured
    case disconnected
    case connecting
    case connected
}

enum GlassesRecordingState: String {
    case idle = "IDLE"
    case recording = "RECORDING"
    case unknown = "UNKNOWN"
}

struct DiscoveredDevice: Identifiable {
    let id: UUID
    let peripheral: CBPeripheral
    let name: String
    let rssi: Int
}

class GlassesBluetoothManager: NSObject, ObservableObject {
    @Published var connectionState: GlassesConnectionState = .disconnected
    @Published var recordingState: GlassesRecordingState = .unknown
    
    @Published var wifiState: GlassesWifiState = .unknown
    @Published var wifiSSID: String?
    @Published var wifiIPAddress: String?
    @Published var isWifiBusy: Bool = false
    @Published var wifiError: String?
    
    @Published var lastError: String?
    @Published var discoveredDevices: [DiscoveredDevice] = []
    @Published var connectedDeviceName: String?
    
    @Published var recordings: [Recording] = []
    @Published var isLoadingRecordings: Bool = false
    @Published var recordingsError: String?
    @Published var hasMoreRecordings: Bool = true
    
    @Published var playbackURL: URL?
    @Published var playbackURLError: String?

    private let recordingsDecoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()
    
    private var central: CBCentralManager!
    private var glassesPeripheral: CBPeripheral?

    private var controlChar: CBCharacteristic?
    private var statusChar: CBCharacteristic?
    
    private var lastRecordingsOffset: Int = 0
    private let recordingsPageSize = 4

    override init() {
        super.init()
        self.central = CBCentralManager(delegate: self, queue: nil)
    }

    // MARK: - Public API for views

    func startScan() {
        guard central.state == .poweredOn else {
            lastError = "Bluetooth not powered on (state = \(central.state.rawValue))"
            print("[BLE] Cannot scan, state =", central.state.rawValue)
            return
        }

        print("[BLE] Starting scan for GLASSES service")
        lastError = nil
        connectionState = .scanning
        discoveredDevices = []
        connectedDeviceName = nil

        central.scanForPeripherals(
            withServices: [glassesServiceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    func stopScan() {
        central.stopScan()
        if connectionState == .scanning {
            connectionState = .disconnected
        }
    }

    func connect(to device: DiscoveredDevice) {
        print("[BLE] User selected device:", device.name, device.id)
        connectionState = .connecting
        let peripheral = device.peripheral
        glassesPeripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        central.connect(peripheral, options: nil)
    }

    func disconnect() {
        if let p = glassesPeripheral {
            central.cancelPeripheralConnection(p)
        }
    }

    func startRecording(intervalSeconds: Int) {
        let clamped = max(1, intervalSeconds) 
        let command = "START:\(clamped)"
        print("[BLE] Sending command:", command)
        sendCommand(command)
        recordingState = .recording
    }
    func stopRecording() {
        sendCommand("STOP")
        recordingState = .idle
    }

    func refreshStatus() {
        guard let statusChar = statusChar,
              let p = glassesPeripheral else { return }
        p.readValue(for: statusChar)
    }
    
    func requestWifiStatus() {
        wifiError = nil

        guard connectionState == .connected else {
            wifiError = "Glasses are not connected over Bluetooth."
            return
        }

        isWifiBusy = true

        sendCommand("GET_WIFI")

        readStatusFromPi()
    }
    
    func requestRecordings(reset: Bool = true) {
        recordingsError = nil

        guard connectionState == .connected else {
            recordingsError = "Glasses are not connected over Bluetooth."
            return
        }

        if reset {
            recordings = []
            hasMoreRecordings = true
            lastRecordingsOffset = 0
        } else {
            if !hasMoreRecordings {
                return
            }
        }

        isLoadingRecordings = true

        let cmd: String
        if lastRecordingsOffset == 0 {
            cmd = "GET_RECORDINGS"
        } else {
            cmd = "GET_RECORDINGS:\(lastRecordingsOffset)"
        }

        print("[BLE] Requesting recordings with offset:", lastRecordingsOffset)
        sendCommand(cmd)
        readStatusFromPi()
    }

    
    func requestPlaybackURL(for recording: Recording) {
        playbackURL = nil
        playbackURLError = nil

        guard connectionState == .connected else {
            playbackURLError = "Glasses are not connected over Bluetooth."
            return
        }

        let cmd = "GET_URL:\(recording.id)"
        print("[BLE] Requesting URL for recording:", recording.id)
        sendCommand(cmd)
        readStatusFromPi()
    }

    
    
    private func handleRecordingsJSON(_ jsonString: String) {
        print("[BLE] Parsing recordings JSON, length:", jsonString.count)

        guard let data = jsonString.data(using: .utf8) else {
            recordingsError = "Invalid recordings data"
            isLoadingRecordings = false
            return
        }

        do {
            let recs = try recordingsDecoder.decode([Recording].self, from: data)
            DispatchQueue.main.async {
                if self.lastRecordingsOffset == 0 {
                    self.recordings = recs
                } else {
                    self.recordings += recs
                }


                if recs.count == self.recordingsPageSize {
                    self.lastRecordingsOffset = self.recordings.count
                    self.hasMoreRecordings = true
                } else {
                    self.hasMoreRecordings = false
                }

                self.isLoadingRecordings = false
                self.recordingsError = nil
            }
            print("[BLE] Decoded \(recs.count) recordings (total now \(recordings.count))")
        } catch {
            print("[BLE] Failed to decode recordings JSON:", error)
            DispatchQueue.main.async {
                self.recordingsError = "Failed to decode recordings: \(error.localizedDescription)"
                self.isLoadingRecordings = false
            }
        }
    }



    
    
    private func resetConnectionState() {
        print("[BLE] Resetting connection state")

        glassesPeripheral = nil
        controlChar = nil
        statusChar = nil
        connectedDeviceName = nil

        recordingState = .unknown

        wifiState = .unknown
        wifiSSID = nil
        wifiIPAddress = nil
        isWifiBusy = false
        wifiError = nil

        recordings = []
        isLoadingRecordings = false
        recordingsError = nil

        discoveredDevices = []

        connectionState = .disconnected
    }


    
    func disconnectWifi() {
        wifiError = nil

        guard connectionState == .connected else {
            wifiError = "Glasses are not connected over Bluetooth."
            return
        }

        isWifiBusy = true
        sendCommand("DISCONNECT_WIFI")

        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            if self.connectionState == .connected {
                self.requestWifiStatus()
            }
        }
    }
    
    private func readStatusFromPi() {
        guard let p = glassesPeripheral,
              let statusChar = statusChar else {
            print("[BLE] Status characteristic not ready, cannot read yet")
            return
        }
        p.readValue(for: statusChar)
    }


        func configureWifi(ssid: String, password: String) {
            wifiError = nil

            let trimmedSSID = ssid.trimmingCharacters(in: .whitespacesAndNewlines)
            let trimmedPassword = password.trimmingCharacters(in: .whitespacesAndNewlines)

            guard !trimmedSSID.isEmpty, !trimmedPassword.isEmpty else {
                wifiError = "SSID and password can’t be empty."
                return
            }

            guard connectionState == .connected else {
                wifiError = "Glasses are not connected over Bluetooth."
                return
            }

            isWifiBusy = true

            let safeSSID = trimmedSSID.replacingOccurrences(of: ":", with: "_")
            let safePassword = trimmedPassword.replacingOccurrences(of: ":", with: "_")
            let command = "SET_WIFI:\(safeSSID):\(safePassword)"
            sendCommand(command)
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 5) { [weak self] in
                guard let self = self else { return }
                if self.connectionState == .connected {
                    self.requestWifiStatus()
                }
            }
        }

    
    // MARK: - Private
    
    private func handleWifiStatus(_ raw: String) {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let parts = trimmed.components(separatedBy: ":")

        guard parts.count >= 2 else { return }

        let stateToken = parts[1].uppercased()

        switch stateToken {
        case "DISCONNECTED":
            wifiState = .disconnected
            wifiSSID = nil
            wifiIPAddress = nil
            isWifiBusy = false
            wifiError = nil
        case "NOT_CONFIGURED":
            wifiState = .notConfigured
            wifiSSID = nil
            wifiIPAddress = nil
            isWifiBusy = false
            wifiError = nil
        case "CONNECTING":
            wifiState = .connecting
            isWifiBusy = true
            wifiError = nil
        case "CONNECTED":
            wifiState = .connected
            isWifiBusy = false
            wifiError = nil

            if parts.count >= 3 {
                wifiSSID = parts[2]
            }
            if parts.count >= 4 {
                wifiIPAddress = parts[3]
            }
        default:
            break
        }
    }
    

    private func sendCommand(_ cmd: String) {

        guard connectionState == .connected else {
            lastError = "No connected glasses"
            return
        }

        guard let p = glassesPeripheral,
              let controlChar = controlChar else {
            print("[BLE] Control characteristic not ready, dropping command:", cmd)
            return
        }

        let data = (cmd + "\n").data(using: .utf8)!
        p.writeValue(data, for: controlChar, type: .withoutResponse)
    }

}

// CBCentralManagerDelegate

extension GlassesBluetoothManager: CBCentralManagerDelegate {
    
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            print("[BLE] Central powered on")
        case .poweredOff:
            print("[BLE] Bluetooth is off")
            connectionState = .disconnected
            resetConnectionState()
        case .unauthorized:
            print("[BLE] Unauthorized")
            lastError = "Bluetooth unauthorized"
        case .unsupported:
            print("[BLE] Unsupported")
            lastError = "Bluetooth unsupported"
        default:
            break
        }
    }

    func centralManager(_ central: CBCentralManager,
                        didDiscover peripheral: CBPeripheral,
                        advertisementData: [String : Any],
                        rssi RSSI: NSNumber) {

        let nameFromAdv = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = peripheral.name ?? nameFromAdv ?? "Glasses"

        print("[BLE] Discovered GLASSES peripheral:")
        print("   ID: \(peripheral.identifier)")
        print("   Name: \(name)")
        print("   RSSI: \(RSSI)")
        print("   Adv: \(advertisementData)")

        let id = peripheral.identifier
        let newDevice = DiscoveredDevice(
            id: id,
            peripheral: peripheral,
            name: name,
            rssi: RSSI.intValue
        )

        if let index = discoveredDevices.firstIndex(where: { $0.id == id }) {
            discoveredDevices[index] = newDevice
        } else {
            discoveredDevices.append(newDevice)
        }
    }


    func centralManager(_ central: CBCentralManager,
                        didConnect peripheral: CBPeripheral) {
        print("[BLE] Connected to peripheral:", peripheral.identifier)
        connectionState = .connected
        connectedDeviceName = peripheral.name ?? "Unknown Device"
        peripheral.discoverServices([glassesServiceUUID])
    }

    func centralManager(_ central: CBCentralManager,
                        didFailToConnect peripheral: CBPeripheral,
                        error: Error?) {
        print("[BLE] Failed to connect:", error?.localizedDescription ?? "unknown")
        connectionState = .disconnected
        lastError = error?.localizedDescription
        resetConnectionState()
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        print("[BLE] Disconnected:", error?.localizedDescription ?? "no error")
        
        DispatchQueue.main.async {
            self.glassesPeripheral = nil
            self.controlChar = nil
            self.statusChar = nil
            self.connectedDeviceName = nil
            
            self.recordingState = .unknown
            
            self.wifiState = .unknown
            self.wifiSSID = nil
            self.wifiIPAddress = nil
            self.isWifiBusy = false
            self.wifiError = nil

            self.connectionState = .disconnected
        }
    }
}

// CBPeripheralDelegate

extension GlassesBluetoothManager: CBPeripheralDelegate {

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverServices error: Error?) {
        if let error = error {
            print("[BLE] Service discovery error:", error)
            lastError = error.localizedDescription
            return
        }
        guard let services = peripheral.services else { return }
        for service in services where service.uuid == glassesServiceUUID {
            peripheral.discoverCharacteristics([controlCharUUID, statusCharUUID],
                                               for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService,
                    error: Error?) {
        if let error = error {
            print("[BLE] Error discovering characteristics:", error)
            lastError = error.localizedDescription
            return
        }

        for ch in service.characteristics ?? [] {
            if ch.uuid == CBUUID(string: controlCharUUID.uuidString) {
                print("[BLE] Found control characteristic")
                self.controlChar = ch
            } else if ch.uuid == CBUUID(string: statusCharUUID.uuidString) {
                print("[BLE] Found status characteristic")
                self.statusChar = ch
            }
        }

        if connectionState == .connected,
           controlChar != nil,
           statusChar != nil {
            print("[BLE] Characteristics ready, auto-requesting Wi-Fi status")
            requestWifiStatus()
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didUpdateValueFor characteristic: CBCharacteristic,
                    error: Error?) {
        if let error = error {
            print("[BLE] Update value error:", error)
            lastError = error.localizedDescription
            return
        }
        guard let data = characteristic.value,
              let s = String(data: data, encoding: .utf8) else { return }

        let raw = s.trimmingCharacters(in: .whitespacesAndNewlines)
        print("[BLE] Status update:", raw)

        // Wi-Fi status
        if raw.uppercased().hasPrefix("WIFI:") {
            handleWifiStatus(raw)
            return
        }

        // Recordings JSON 
        if raw.first == "[" {
            handleRecordingsJSON(raw)
            return
        }
        
        // Playback URL
        if raw.hasPrefix("URL:") {
            let urlString = String(raw.dropFirst(4))
            if urlString == "ERROR" {
                playbackURLError = "Failed to get video URL from glasses."
            } else if let url = URL(string: urlString) {
                playbackURL = url
                print("[BLE] Got playback URL:", url)
            } else {
                playbackURLError = "Invalid URL from glasses."
            }
            return
        }
    

        // Recording state text
        let statusString = raw.uppercased()
        switch statusString {
        case "IDLE":
            recordingState = .idle
        case "RECORDING":
            recordingState = .recording
        default:
            recordingState = .unknown
        }
    }
}

