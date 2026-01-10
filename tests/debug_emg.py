import requests
import time
import json

BASE_URL = "http://localhost:1972/api/emg"

def test_emg_flow():
    print("Testing EMG Recording Flow...")
    
    # 1. Start Recording Rest
    print("\n1. Starting Recording (Rest)...")
    try:
        res = requests.post(f"{BASE_URL}/start", json={"label": 0})
        print(f"Start Response: {res.status_code} {res.text}")
    except Exception as e:
        print(f"FAILED to connect: {e}")
        return

    # 2. Check Status
    time.sleep(0.5)
    res = requests.get(f"{BASE_URL}/status")
    status = res.json()
    print(f"Status: {status}")
    
    if not status.get('recording'):
        print("❌ FAILED: Status should be recording")
    else:
        print("✅ Status is recording")

    if status.get('current_label') != 0 and status.get('current_label') != 'Rest':
        # logic in server maps 0->Rest. Endpoint returns mapped?
        # My implementation: returns mapped counts, and current_label mapped back to int.
        # Let's check what it returns.
        print(f"Current Label: {status.get('current_label')} (Expect 0)")

    # 3. Stop Recording
    print("\n2. Stopping Recording...")
    res = requests.post(f"{BASE_URL}/stop")
    print(f"Stop Response: {res.status_code} {res.text}")
    
    # 4. Check Status
    time.sleep(0.5)
    res = requests.get(f"{BASE_URL}/status")
    status = res.json()
    print(f"Status: {status}")
    
    if status.get('recording'):
        print("❌ FAILED: Status should NOT be recording")
    else:
        print("✅ Status is stopped")

if __name__ == "__main__":
    test_emg_flow()
