from picamera2 import Picamera2
import time

print("starting camera test hold on...")

try:
    cam = Picamera2()
    config = cam.create_still_configuration()
    cam.configure(config)

    cam.start()
    time.sleep(2)  # here you might want to gives it a second to warm up

    outfile = "camera_test.jpg"
    cam.capture_file(outfile)
    cam.stop()

    print("camera test done. saved as", outfile)

except Exception as e:
    print("camera test failed. something is wrong")
    print(e)
