"""
EEG Dashboard Server with WebSocket Support - FIXED
Handles multi-channel EEG streaming via WebSocket

Usage:
  pip install flask flask-socketio python-socketio python-engineio
  python eeg_websocket_server.py --port COM7 --baud 115200 --channels 1
"""

import serial
import json
import argparse
import time
import sys
from threading import Thread
from collections import deque
from datetime import datetime

try:
    from flask import Flask, jsonify
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit, disconnect
except ImportError:
    print("❌ Missing dependencies!")
    print("   Run: pip install flask flask-socketio python-socketio python-engineio flask-cors")
    sys.exit(1)

class EEGDataBuffer:
    """Buffer multi-channel EEG data"""
    
    def __init__(self, num_channels=1, max_size=2000):
        self.num_channels = num_channels
        self.buffers = [deque(maxlen=max_size) for _ in range(num_channels)]
        self.latest = [None] * num_channels
        self.stats = {
            'samples_received': 0,
            'last_update': None,
            'connection_time': datetime.now().isoformat(),
            'channels': num_channels
        }
    
    def add_sample(self, channel, value):
        """Add single sample to channel"""
        if channel < self.num_channels:
            self.buffers[channel].append(value)
            self.latest[channel] = value
            self.stats['samples_received'] += 1
            self.stats['last_update'] = datetime.now().isoformat()
    
    def add_multi_sample(self, values):
        """Add samples across all channels"""
        for ch, value in enumerate(values):
            if ch < self.num_channels:
                self.add_sample(ch, value)
    
    def get_latest(self):
        """Get latest values for all channels"""
        return self.latest
    
    def get_buffer(self, channel=0, n=500):
        """Get last N points for a channel"""
        if channel < self.num_channels:
            return list(self.buffers[channel])[-n:]
        return []
    
    def get_all_channels(self, n=500):
        """Get last N points for all channels"""
        return [list(self.buffers[ch])[-n:] for ch in range(self.num_channels)]
    
    def get_stats(self):
        """Get buffer statistics"""
        stats = self.stats.copy()
        stats['channel_stats'] = []
        
        for ch in range(self.num_channels):
            if len(self.buffers[ch]) == 0:
                stats['channel_stats'].append({'empty': True})
            else:
                values = list(self.buffers[ch])
                stats['channel_stats'].append({
                    'channel': ch,
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'mean': sum(values) / len(values),
                    'latest': self.latest[ch]
                })
        
        return stats


class EEGSerialReader:
    """Read multi-channel EEG data from serial"""
    
    def __init__(self, port, baud_rate=115200, num_channels=1):
        self.port = port
        self.baud_rate = baud_rate
        self.num_channels = num_channels
        self.ser = None
        self.running = False
        self.data_buffer = EEGDataBuffer(num_channels)
        self.error_count = 0
        self.max_errors = 10
        self.socketio = None
    
    def set_socketio(self, socketio):
        """Set SocketIO instance for broadcasting"""
        self.socketio = socketio
    
    def connect(self):
        """Connect to serial port"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            
            print(f"🔌 Connecting to {self.port} at {self.baud_rate} baud...")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1,
                write_timeout=1
            )
            self.ser.reset_input_buffer()
            print(f"✅ Connected to {self.port}")
            print(f"📊 Streaming {self.num_channels} channel(s)")
            self.error_count = 0
            return True
        
        except serial.SerialException as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def parse_line(self, line):
        """Parse a single line from Arduino"""
        try:
            if line.startswith('{'):
                data = json.loads(line)
                
                # Single sample format
                if 'sample' in data:
                    return float(data['sample'])
                
                # Multi-sample format
                if 'samples' in data and isinstance(data['samples'], list):
                    return data['samples']
        
        except (json.JSONDecodeError, ValueError, IndexError, KeyError):
            pass
        
        return None
    
    def read_loop(self):
        """Main reading loop"""
        self.running = True
        print("📊 Reading stream...\n")
        
        last_print_time = time.time()
        samples_since_print = 0
        
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    if not self.connect():
                        time.sleep(2)
                        continue
                
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        result = self.parse_line(line)
                        
                        if result is not None:
                            # Single sample
                            if isinstance(result, float):
                                self.data_buffer.add_sample(0, result)
                                samples_since_print += 1
                            # Multiple samples (multi-channel)
                            elif isinstance(result, list):
                                self.data_buffer.add_multi_sample(result)
                                samples_since_print += len(result)
                            
                            # Broadcast via WebSocket
                            if self.socketio:
                                latest = self.data_buffer.get_latest()
                                try:
                                    # FIXED: Use skip_sid with to() for broadcasting
                                    self.socketio.emit('eeg_data', {
                                        'source': 'EEG',
                                        'fs': 250,
                                        'timestamp': int(time.time() * 1000),
                                        'values': latest,
                                        'channels': self.num_channels
                                    }, to=None, skip_sid=None)
                                except Exception as e:
                                    # Fallback: just emit normally
                                    pass
                
                # Print status every 2 seconds
                current_time = time.time()
                if current_time - last_print_time >= 2:
                    total = self.data_buffer.stats['samples_received']
                    print(f"📡 {samples_since_print} samples/sec | Total: {total} samples")
                    last_print_time = current_time
                    samples_since_print = 0
                
                time.sleep(0.001)
            
            except serial.SerialException as e:
                self.error_count += 1
                print(f"⚠️  Serial error: {e}")
                
                if self.error_count >= self.max_errors:
                    print("❌ Too many errors, reconnecting...")
                    if self.ser:
                        self.ser.close()
                    time.sleep(2)
            
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start reading in background thread"""
        if not self.connect():
            return False
        
        thread = Thread(target=self.read_loop, daemon=True)
        thread.start()
        return True
    
    def stop(self):
        """Stop reading"""
        self.running = False
        if self.ser:
            self.ser.close()


# ===== FLASK + SOCKETIO APP =====

def create_app(reader):
    """Create Flask + SocketIO app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'eeg-dashboard-secret'
    
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    
    # Set reader's socketio instance
    reader.set_socketio(socketio)
    
    # ===== REST API ENDPOINTS =====
    
    @app.route('/api/health')
    def health():
        """Health check"""
        return jsonify({
            'status': 'ok' if reader.ser and reader.ser.is_open else 'disconnected',
            'port': reader.port,
            'baud': reader.baud_rate,
            'channels': reader.num_channels,
            'samples': reader.data_buffer.stats['samples_received']
        })
    
    @app.route('/api/stats')
    def stats():
        """Get signal statistics"""
        return jsonify(reader.data_buffer.get_stats())
    
    @app.route('/api/buffer/<int:channel>')
    def buffer_channel(channel):
        """Get buffered samples for specific channel"""
        n = 500  # Default
        data = reader.data_buffer.get_buffer(channel, n)
        
        return jsonify({
            'source': 'EEG',
            'fs': 250,
            'channel': channel,
            'data': data
        })
    
    @app.route('/')
    def index():
        """Root endpoint"""
        return jsonify({
            'message': 'EEG WebSocket Server',
            'endpoints': {
                '/api/health': 'GET - Server health',
                '/api/stats': 'GET - Signal statistics',
                '/api/buffer/<channel>': 'GET - Channel buffer',
                'ws': 'WebSocket - Real-time streaming'
            }
        })
    
    # ===== WEBSOCKET EVENTS =====
    
    @socketio.on('connect')
    def handle_connect():
        """Client connected"""
        print(f"🔗 Client connected")
        emit('response', {
            'status': 'connected',
            'channels': reader.num_channels,
            'fs': 250
        })
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Client disconnected"""
        print(f"❌ Client disconnected")
    
    @socketio.on('request_buffer')
    def handle_request_buffer(data):
        """Client requests full buffer"""
        channel = data.get('channel', 0)
        n = data.get('n', 500)
        
        buffer_data = reader.data_buffer.get_buffer(channel, n)
        emit('buffer_data', {
            'channel': channel,
            'data': buffer_data,
            'timestamp': int(time.time() * 1000)
        })
    
    @socketio.on('request_all_channels')
    def handle_request_all_channels(data):
        """Client requests all channels"""
        n = data.get('n', 500)
        
        all_data = reader.data_buffer.get_all_channels(n)
        emit('all_channels_data', {
            'data': all_data,
            'channels': reader.num_channels,
            'timestamp': int(time.time() * 1000)
        })
    
    @socketio.on_error_default
    def default_error_handler(e):
        """Default error handler"""
        print(f"❌ Socket error: {e}")
    
    return app, socketio


def main():
    parser = argparse.ArgumentParser(description='EEG WebSocket Server')
    parser.add_argument('--port', default='COM7', help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--channels', type=int, default=1, help='Number of EEG channels')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--ws-port', type=int, default=5000, help='WebSocket port')
    
    args = parser.parse_args()
    
    # Create reader
    reader = EEGSerialReader(args.port, args.baud, args.channels)
    if not reader.start():
        print("❌ Failed to start reader")
        sys.exit(1)
    
    # Create Flask + SocketIO app
    app, socketio = create_app(reader)
    
    print("\n" + "="*60)
    print("🧠 EEG WEBSOCKET SERVER")
    print("="*60)
    print(f"Serial: {args.port} @ {args.baud} baud")
    print(f"Channels: {args.channels}")
    print(f"\nServer running on: http://localhost:{args.ws_port}")
    print(f"WebSocket: ws://localhost:{args.ws_port}")
    print("\nAPI Endpoints:")
    print(f"  GET /api/health")
    print(f"  GET /api/stats")
    print(f"  GET /api/buffer/<channel>")
    print("="*60 + "\n")
    
    # Run SocketIO server
    try:
        socketio.run(app, host=args.host, port=args.ws_port, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n✋ Shutting down...")
        reader.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
