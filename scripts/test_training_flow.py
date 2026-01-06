import requests
import time
import sys

BASE_URL = "http://localhost:1972/api"

def run_test():
    print("Testing Backend Training Flow...")
    
    # 1. Check Status
    try:
        r = requests.get(f"{BASE_URL}/status")
        print(f"Status Check: {r.status_code}")
    except Exception as e:
        print(f"Backend not running? {e}")
        return

    # 2. Clear Data
    print("Clearing Data...")
    requests.delete(f"{BASE_URL}/emg/data")
    
    # 3. Start Recording (Mock Rock)
    print("Starting Recording 'Rock'...")
    r = requests.post(f"{BASE_URL}/emg/start", json={"label": 1}) # 1 = Rock
    if r.status_code != 200:
        print(f"Start Failed: {r.text}")
        return

    print("Recording for 3 seconds...")
    time.sleep(3)

    # 5. Stop Recording
    print("Stopping Recording...")
    r = requests.post(f"{BASE_URL}/emg/stop")
    print(f"Stop Response: {r.json()}")
    
    # 6. Train
    print("Training...")
    r = requests.post(f"{BASE_URL}/train-emg-rf")
    if r.status_code == 200:
        print(f"Training Success: {r.json()}")
    else:
        print(f"Training Failed: {r.text}")

if __name__ == "__main__":
    run_test()
