
import serial
import time

PORT = "COM7"  # Change this if Arduino uses another COM port
BAUD_RATE = 9600

try:
    with serial.Serial(PORT, BAUD_RATE, timeout=2) as arduino:
        time.sleep(2)
        arduino.reset_input_buffer()

        print(f"Connected to Arduino on {PORT}")
        print("Receiving live sensor data... Press Ctrl+C to stop.\n")

        while True:
            try:
                line = arduino.readline().decode(
                    "utf-8", errors="replace"
                ).strip()

                if line:
                    print(line)

            except serial.SerialException as error:
                print("Serial reading error:", error)
                break

except serial.SerialException as error:
    print("Connection failed:", error)
    print("Check COM port and close Arduino Serial Monitor.")

except KeyboardInterrupt:
    print("\nStopped by user.")
