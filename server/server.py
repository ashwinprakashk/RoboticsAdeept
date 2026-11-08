from flask import Flask, request, send_from_directory
import Adeept
import threading
import time
import os
import serial

app = Flask(__name__)

servo_names = ["Base", "Lower Leg", "Upper Arm", "Neck", "Bite"]
home_angles = [13, 110, 156, 76, 98]
current_servo_angles = [13, 110, 156, 76, 98]

connected = False

def get_current_servo_positions():
    return current_servo_angles.copy()

def find_serial_port():
    import glob
    candidates = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    for port in candidates:
        if not os.path.exists(port):
            continue
        print(f"[INFO] Testing serial port availability: {port}")
        try:
            s = serial.Serial(port, 115200, timeout=1.5)
            time.sleep(3)  # Wait for DTR auto-reset
            s.write(b"{'start':['setup']}\n")
            s.flush()
            res = s.readline().decode('utf-8', errors='ignore').strip()
            s.close()
            if res:
                print(f"[SUCCESS] Arduino verified on {port} (reply: {res!r})")
                return port
            else:
                print(f"[WARNING] Port {port} gave no reply")
        except Exception as e:
            print(f"[WARNING] Probing port {port} failed: {e}")
    raise Exception("No responding Arduino serial port found")

def reconnect_serial():
    global connected
    connected = False
    print("[INFO] Attempting to reconnect to Arduino...")
    while not connected:
        try:
            port = find_serial_port()
            print(f"[INFO] Initializing Adeept extension on {port}...")
            Adeept.com_init(port, 115200, 1)
            if hasattr(Adeept, 'wait_connect'):
                Adeept.wait_connect()
            elif hasattr(Adeept, 'wiat_connect'):
                Adeept.wiat_connect()

            Adeept.three_function("'servo_attach'", 0, 9)
            Adeept.three_function("'servo_attach'", 1, 6)
            Adeept.three_function("'servo_attach'", 2, 5)
            Adeept.three_function("'servo_attach'", 3, 3)
            Adeept.three_function("'servo_attach'", 4, 11)

            for i, v in enumerate(home_angles):
                Adeept.three_function("'servo_write'", i, v)

            connected = True
            print("[INFO] Reconnected successfully!")
        except Exception as e:
            print(f"[ERROR] Reconnect failed: {e}. Retrying in 2 seconds...")
            time.sleep(2)

def watchdog():
    global connected
    while True:
        time.sleep(10)
        if not connected:
            continue
        try:
            Adeept.three_function("'NULL'", 0, 0)
        except Exception:
            print("[WATCHDOG] Connection lost. Reconnecting...")
            connected = False
            reconnect_serial()

def init_serial():
    reconnect_serial()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/cmd', methods=['POST'])
def cmd():
    if not connected:
        return {"status": "error", "msg": "Arduino not connected"}, 503
    data = request.json
    index = int(data["index"])
    value = int(data["value"])
    if index == 1:
        value = 180 - value
    print(f"[SERVER] servo_write {index} -> {value}")
    Adeept.three_function("'servo_write'", index, value)
    current_servo_angles[index] = value
    return {"status": "ok"}

saved_positions = []
playback_active = False

@app.route('/save_positions', methods=['POST'])
def save_positions():
    global saved_positions
    saved_positions = request.json["positions"]
    print("[SERVER] Saved positions:", saved_positions)
    return {"status": "ok"}

@app.route('/start_playback', methods=['POST'])
def start_playback():
    global playback_active
    playback_active = True
    print("[SERVER] Playback started")
    return {"status": "ok"}

@app.route('/stop_playback', methods=['POST'])
def stop_playback():
    global playback_active
    playback_active = False
    print("[SERVER] Playback stopped")
    return {"status": "ok"}

@app.route('/current')
def current():
    return {"angles": current_servo_angles}

def playback_loop():
    while True:
        time.sleep(0.02)
        if not playback_active or not connected:
            continue
        valid_positions = [p for p in saved_positions if p]
        if not valid_positions:
            continue
        for target in valid_positions:
            if not playback_active:
                break
            smooth_move_to(target)

def smooth_move_to(target_ui):
    steps = 50
    delay = 0.02
    target = [180 - target_ui[i] if i == 1 else target_ui[i] for i in range(5)]
    current = get_current_servo_positions()
    for s in range(steps):
        if not playback_active:
            return
        t = s / steps
        for i in range(5):
            val = int(current[i] + (target[i] - current[i]) * t)
            Adeept.three_function("'servo_write'", i, val)
            current_servo_angles[i] = val
        time.sleep(delay)

threading.Thread(target=init_serial, daemon=True).start()
threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=playback_loop, daemon=True).start()

if __name__ == '__main__':
    print("Starting web server on port 5000...")
    app.run(host='0.0.0.0', port=5000)
