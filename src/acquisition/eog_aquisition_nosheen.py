import serial
import serial.tools.list_ports
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

class SerialApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino Serial Logger")
        self.serial_port = None
        self.running = False

        # UI Elements
        ttk.Label(root, text="Select Port:").grid(row=0, column=0, padx=5, pady=5)

        self.port_box = ttk.Combobox(root, values=self.get_ports(), width=20)
        self.port_box.grid(row=0, column=1, padx=5, pady=5)

        self.start_btn = ttk.Button(root, text="Start", command=self.start_logging)
        self.start_btn.grid(row=1, column=0, padx=5, pady=10)

        self.stop_btn = ttk.Button(root, text="Stop", command=self.stop_logging, state=tk.DISABLED)
        self.stop_btn.grid(row=1, column=1, padx=5, pady=10)

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def start_logging(self):
        port = self.port_box.get()
        if not port:
            messagebox.showerror("Error", "Please select a port!")
            return

        try:
            self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            threading.Thread(target=self.read_serial, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def stop_logging(self):
        self.running = False
        if self.serial_port:
            self.serial_port.close()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def read_serial(self):
        with open("arduino_data.json", "a") as file:
            while self.running:
                try:
                    if self.serial_port.in_waiting:
                        data = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                        if data:
                            entry = {"timestamp": time.time(), "value": data}
                            file.write(json.dumps(entry) + "\n")
                except Exception as e:
                    print("Error reading serial:", e)
                time.sleep(0.01)

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialApp(root)
    root.mainloop()
