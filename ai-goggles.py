#donloaded these python libraries: opencv + numpy for videos
#also soounddevice and soundfile for sound

import cv2
import numpy as np
import time

# settings from 720 pixels, and 15 frames per second and (44 hz sound or 44,000 samples?)
w = 1280
h = 720
fps = 15
rate = 44100

def get_frame():
    # dont have the real goggles camera
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    
    return frame

def get_sound():
    # still no mic so so just return nothing
    sound = None
    
    return sound

def analyze_frame(frame, mode="faces"):
    # checking edges for now
    if frame is None:
        return None
    
    if mode == "edges":
        
        edges = cv2.Canny(frame, 100, 200)
        
        edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
        return edges_colored
    
    if mode == "faces":
        # here would be the part for face detection here
        return frame
    
    return frame

def analyze_sound(sound):
    # no mic yet (place holder)
    return sound

def run():
    print("starting test...")
    
    frames = 0
    t0 = time.time()
    try:
        
        while frames < 50:  # just 50 frames for now
            f = get_frame()
            v = analyze_frame(f, "edges")
            s = get_sound()
            frames += 1
            if frames % 10 == 0:
                print("got", frames, "frames so far")
                
            time.sleep(1.0/fps)
    except KeyboardInterrupt:
        print("stopped by user (either user stopped the recording or battery died)")
        
        
    finally:
        dt = time.time() - t0
        if dt <= 0: dt = 1
        print("avg fps:", round(frames/dt, 2))

if __name__ == "__main__":
    run()
