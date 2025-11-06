# main.py
import time
from camera_module import test_camera, get_frame
from mic_module import test_microphone, get_sound
from analysis_module import analyze_frame

def run_simulation(fps=15):
    print("\n=== STARTING SIMULATION ===")
    frames = 0
    t0 = time.time()
    try:
        while frames < 50:
            frame = get_frame()
            analyzed = analyze_frame(frame, "edges")
            sound = get_sound(duration=0.5)
            frames += 1
            if frames % 10 == 0:
                print(f"Captured {frames} frames...")
            time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        print("Stopped manually.")
    finally:
        dt = time.time() - t0
        if dt <= 0:
            dt = 1
        print("Average FPS:", round(frames / dt, 2))
        print("Simulation complete.")


if __name__ == "__main__":
    print("=== AI GOGGLES TEST START ===\n")
    cam_ok = test_camera()
    mic_ok = test_microphone()

    if cam_ok and mic_ok:
        print("\nBoth camera and microphone are working correctly.")
    else:
        print("\nOne or more tests failed. Check wiring or software setup.")

    run_simulation()
