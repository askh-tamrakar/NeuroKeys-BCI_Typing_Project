import requests

try:
    url = "http://localhost:5000/api/sessions/EMG"
    print(f"GET {url}")
    res = requests.get(url)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")
except Exception as e:
    print(f"Error: {e}")
