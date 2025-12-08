"""
Flask WebSocket Server for EEG Data Streaming (FIXED VERSION)
Streams real-time EEG data over WebSocket to React frontend
"""

import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import serial
import argparse
import math

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
SAMPLE_RATE = 250  # Hz
NUM_CHANNELS = 1
SERIAL_PORT = "COM7"
BAUD_RATE = 115200
USE_MOCK_DATA = False  # Set to True to test without hardware

# Global state
ser = None
streaming = False
connected_clients = 0
mock_phase = 0  # For sine wave generation

def parse_eeg_data(line):
    """Parse incoming serial data from Arduino/device"""
    try:
        # Expected format: "value1,value2,value3\n" or "value1\n"
        values = [float(x.strip()) for x in line.strip().split(',')]
        return values
    except (ValueError, AttributeError):
        return None


def generate_mock_eeg():
    """Generate mock EEG data (sine waves for testing)"""
    global mock_phase
    samples = []
    for ch in range(NUM_CHANNELS):
        freq = 8 + (ch % 4) * 4  # Different frequencies per channel
        phase = mock_phase + (ch * 2 * math.pi / NUM_CHANNELS)
        value = math.sin(2 * math.pi * freq * phase / (SAMPLE_RATE * 10)) * 50 + 100
        samples.append(value)
    mock_phase += 1
    return samples


def serial_reader_thread():
    """Read from serial port and broadcast to all connected clients"""
    global ser, streaming, mock_phase
    
    sample_buffer = []
    buffer_size = 30  # Send every 30 samples (~120ms at 250Hz)
    message_count = 0
    
    print("[SERVER] Serial reader thread started")
    
    while streaming:
        try:
            values = None
            
            if USE_MOCK_DATA:
                # Generate mock data
                values = generate_mock_eeg()
            elif ser and ser.is_open:
                # Read from actual serial
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        values = parse_eeg_data(line)
            
            if values:
                sample_buffer.extend(values)
                
                # When buffer is full, send to clients
                if len(sample_buffer) >= buffer_size * NUM_CHANNELS:
                    # Prepare message in your format
                    message = {
                        "source": "EEG",
                        "fs": SAMPLE_RATE,
                        "timestamp": int(time.time() * 1000),
                        "channels": NUM_CHANNELS,
                        "values": sample_buffer[:buffer_size * NUM_CHANNELS]
                    }
                    
                    # Emit to all connected clients
                    socketio.emit('eeg_data', message)
                    message_count += 1
                    
                    if message_count % 10 == 0:
                        print(f"[SERVER] Sent {message_count} messages to {connected_clients} clients | Sample: {sample_buffer[0]:.2f}")
                    
                    # Keep remaining samples
                    sample_buffer = sample_buffer[buffer_size * NUM_CHANNELS:]
                    
        except Exception as e:
            print(f"[SERVER] Serial reader error: {e}")
            time.sleep(0.1)
        
        time.sleep(0.001)  # Small sleep to prevent CPU spinning


def init_serial():
    """Initialize serial connection"""
    global ser, streaming
    
    if False:
        print(f"[SERVER] MOCK MODE ENABLED - using generated sine wave data")
        streaming = True
        
        # Start serial reader thread (will use mock data)
        reader_thread = threading.Thread(target=serial_reader_thread, daemon=True)
        reader_thread.start()
        
        return True
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[SERVER] ✅ Serial port opened: {SERIAL_PORT} @ {BAUD_RATE} baud")
        streaming = True
        
        # Start serial reader thread
        reader_thread = threading.Thread(target=serial_reader_thread, daemon=True)
        reader_thread.start()
        
        return True
    except Exception as e:
        print(f"[SERVER] ❌ Failed to open serial port: {e}")
        print(f"[SERVER] Falling back to MOCK MODE")
        USE_MOCK_DATA = True
        streaming = True
        reader_thread = threading.Thread(target=serial_reader_thread, daemon=True)
        reader_thread.start()
        return True


@app.route('/')
def index():
    """Serve a simple test page"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>EEG WebSocket Server</title>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <style>
            body { font-family: monospace; padding: 20px; background: #1a1a1a; color: #fff; }
            .container { max-width: 600px; margin: 0 auto; }
            .status { padding: 10px; border-radius: 5px; margin-bottom: 20px; font-weight: bold; }
            .connected { background: #0f0; color: #000; }
            .disconnected { background: #f00; color: #fff; }
            .log { background: #222; padding: 15px; border-radius: 5px; max-height: 400px; overflow-y: auto; font-size: 12px; }
            .log-line { margin: 5px 0; }
            .success { color: #0f0; }
            .error { color: #f00; }
            .info { color: #0ff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧠 EEG WebSocket Server (Test Client)</h1>
            <div class="status disconnected" id="status">Status: Waiting...</div>
            <h3>Message Log:</h3>
            <div class="log" id="log"></div>
        </div>
        
        <script>
            const socket = io({
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: Infinity
            });
            
            const logEl = document.getElementById('log');
            const statusEl = document.getElementById('status');
            let messageCount = 0;
            
            function addLog(msg, type = 'info') {
                const line = document.createElement('div');
                line.className = `log-line ${type}`;
                line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
                logEl.appendChild(line);
                logEl.scrollTop = logEl.scrollHeight;
            }
            
            socket.on('connect', () => {
                statusEl.className = 'status connected';
                statusEl.textContent = '✅ Status: Connected to Server';
                addLog('Connected to WebSocket server', 'success');
            });
            
            socket.on('disconnect', () => {
                statusEl.className = 'status disconnected';
                statusEl.textContent = '❌ Status: Disconnected';
                addLog('Disconnected from server', 'error');
            });
            
            socket.on('eeg_data', (data) => {
                messageCount++;
                const sample = data.values[0]?.toFixed(2) || 'N/A';
                addLog(`📊 EEG Data #${messageCount}: ${data.channels}ch, ${data.values.length} samples, value=${sample}`, 'success');
            });
            
            socket.on('error', (err) => {
                addLog(`⚠️ Error: ${err}`, 'error');
            });
        </script>
    </body>
    </html>
    '''


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    global connected_clients
    connected_clients += 1
    print(f"[SERVER] ✅ Client connected. Total: {connected_clients}")
    emit('message', {'data': f'Connected. {connected_clients} total clients.'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    global connected_clients
    connected_clients = max(0, connected_clients - 1)
    print(f"[SERVER] ❌ Client disconnected. Total: {connected_clients}")


@socketio.on('ping')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'timestamp': int(time.time() * 1000)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=str, default='COM7', help='Serial port (e.g., COM7, /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--channels', type=int, default=1, help='Number of EEG channels')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Flask host')
    parser.add_argument('--web-port', type=int, default=5000, help='Web port')
    parser.add_argument('--mock', action='store_true', help='Use mock data instead of serial')
    args = parser.parse_args()
    
    SERIAL_PORT = args.port
    BAUD_RATE = args.baud
    NUM_CHANNELS = args.channels
    
    if args.mock:
        USE_MOCK_DATA = True
    
    print(f"""
    🧠 EEG WebSocket Server
    ========================
    Serial Port: {SERIAL_PORT}
    Baud Rate: {BAUD_RATE}
    Channels: {NUM_CHANNELS}
    Sample Rate: {SAMPLE_RATE} Hz
    Mock Mode: {USE_MOCK_DATA}
    Web Server: http://{args.host}:{args.web_port}
    Test Page: http://localhost:{args.web_port}
    
    Starting server...
    """)
    
    # Initialize serial connection
    init_serial()
    
    # Start Flask-SocketIO server
    socketio.run(app, host=args.host, port=args.web_port, debug=False)
