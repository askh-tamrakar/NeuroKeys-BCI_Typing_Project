import requests
import time

try:
    resp = requests.get("http://localhost:5000/api/status")
    data = resp.json()
    print("--- Server Status ---")
    print(f"Connected: {data.get('connected')}")
    print(f"Sample Count: {data.get('samples_broadcast')}")
    print(f"Channels: {data.get('channels')}")
    print(f"Sample Rate: {data.get('sample_rate')}")
    print("---------------------")
except Exception as e:
    print(f"Failed to connect to server: {e}")
