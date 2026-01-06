import requests
import time
import random

url = "http://localhost:5000/api/window"
payload = {
    "sensor": "EMG",
    "action": "Rest",
    "samples": [random.random() for _ in range(256)],
    "session_name": "TestSession"
}

print(f"Sending POST to {url}...")
try:
    resp = requests.post(url, json=payload)
    print(f"Status: {resp.status_code}")
    print("Response text:", resp.text)
    if resp.status_code == 500:
        try:
            print("Traceback:", resp.json().get('traceback'))
        except:
            pass
except Exception as e:
    print(f"Request failed: {e}")
