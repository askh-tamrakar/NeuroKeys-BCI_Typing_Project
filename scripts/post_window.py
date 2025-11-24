# scripts/post_window.py
import requests, numpy as np, time, json
URL = "http://localhost:8000/infer"
def post_random(mod="EEG"):
    fs = 250
    window = (0.1 * np.random.randn(8, fs)).tolist()
    payload = {"modality": mod, "data": window, "fs": fs}
    r = requests.post(URL, json=payload)
    print("resp:", r.json())

if __name__ == "__main__":
    while True:
        post_random("EEG")
        time.sleep(0.5)
