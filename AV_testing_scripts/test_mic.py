import subprocess

print("testing microphone...")

try:

    cmd = [
        "arecord",
        "-D", "hw:1,0",
        "-f", "S32_LE",
        "-r", "48000",
        "-c", "2",
        "-d", "3",
        "mic_test.wav"
    ]

    subprocess.run(cmd, check=True)
    
    print("mic test finished the file is saved as mic_test.wav")

except Exception as e:
    print("mic test failed. maybe wiring or libraries messed up")
    
    print(e)
