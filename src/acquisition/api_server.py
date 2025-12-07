"""
Flask API Backend for Unified Acquisition System
Handles HTTP requests, manages sessions, serves recordings
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')  # Windows emoji fix
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import serial.tools.list_ports
import json
from pathlib import Path
from datetime import datetime
import threading
import io
import csv

app = Flask(__name__)
CORS(app)

# Global state
acquisition_app = None
current_session = None
sessions_dir = Path("data/raw/session")
sessions_dir.mkdir(parents=True, exist_ok=True)


@app.route('/api/ports', methods=['GET'])
def get_ports():
    """Get available COM ports"""
    ports = []
    for port, desc, hwid in serial.tools.list_ports.comports():
        ports.append({
            'port': port,
            'description': desc,
            'hwid': hwid
        })
    return jsonify({'ports': ports})


@app.route('/api/connect', methods=['POST'])
def connect_device():
    """Connect to device with specified settings"""
    global acquisition_app
    
    try:
        data = request.json
        port = data.get('port')
        baud_rate = data.get('baudRate', 230400)
        sampling_rate = data.get('samplingRate', 512)
        channel_mapping = data.get('channelMapping', {0: 'EEG', 1: 'EOG'})
        
        # Connect via the acquisition app
        if acquisition_app:
            acquisition_app.ser = serial.Serial(port, baud_rate, timeout=0.1)
            acquisition_app.is_connected = True
            acquisition_app.channel_mapping = channel_mapping
            acquisition_app.SAMPLING_RATE = sampling_rate
            
            return jsonify({
                'success': True,
                'message': f'Connected to {port}',
                'config': {
                    'port': port,
                    'baudRate': baud_rate,
                    'samplingRate': sampling_rate,
                    'channelMapping': channel_mapping
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Acquisition app not initialized'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/disconnect', methods=['POST'])
def disconnect_device():
    """Disconnect from device"""
    global acquisition_app
    
    try:
        if acquisition_app and acquisition_app.ser:
            acquisition_app.ser.close()
            acquisition_app.is_connected = False
        return jsonify({'success': True, 'message': 'Disconnected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    """Start a new recording session"""
    global current_session, acquisition_app
    
    try:
        data = request.json
        session_name = data.get('name', f'session_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}')
        
        current_session = {
            'id': datetime.now().isoformat(),
            'name': session_name,
            'startTime': datetime.now().isoformat(),
            'data': []
        }
        
        if acquisition_app:
            acquisition_app.is_recording = True
            acquisition_app.session_data = []
            acquisition_app.session_start_time = datetime.now()
        
        return jsonify({
            'success': True,
            'sessionId': current_session['id'],
            'message': f'Recording started: {session_name}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    """Stop recording and save session"""
    global current_session, acquisition_app
    
    try:
        if not current_session:
            return jsonify({'success': False, 'error': 'No active recording'}), 400
        
        data = request.json
        session_id = data.get('sessionId')
        duration = data.get('duration', 0)
        
        if acquisition_app:
            acquisition_app.is_recording = False
            session_data = acquisition_app.session_data
        else:
            session_data = current_session.get('data', [])
        
        # Save session to file
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filename = f"session_{current_session['name']}_{timestamp}.json"
        filepath = sessions_dir / filename
        
        metadata = {
            'session_info': {
                'id': session_id,
                'name': current_session['name'],
                'startTime': current_session['startTime'],
                'duration_seconds': duration,
                'total_packets': len(session_data),
                'sampling_rate_hz': acquisition_app.SAMPLING_RATE if acquisition_app else 512,
                'channel_0_type': acquisition_app.channel_mapping.get(0, 'EEG') if acquisition_app else 'EEG',
                'channel_1_type': acquisition_app.channel_mapping.get(1, 'EOG') if acquisition_app else 'EOG'
            },
            'data': session_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        current_session = None
        
        return jsonify({
            'success': True,
            'sessionId': session_id,
            'filePath': str(filepath),
            'totalPackets': len(session_data),
            'fileSize': f'{filepath.stat().st_size / 1024:.2f} KB',
            'message': f'Session saved: {filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """Get list of saved recordings"""
    try:
        recordings = []
        for file in sorted(sessions_dir.glob('*.json'), reverse=True):
            with open(file, 'r') as f:
                data = json.load(f)
            
            session_info = data.get('session_info', {})
            recordings.append({
                'id': session_info.get('id', file.stem),
                'name': session_info.get('name', file.stem),
                'timestamp': int(datetime.fromisoformat(session_info.get('startTime', datetime.now().isoformat())).timestamp() * 1000),
                'duration': session_info.get('duration_seconds', 0),
                'dataPoints': session_info.get('total_packets', 0),
                'size': f'{file.stat().st_size / 1024:.2f} KB',
                'filePath': str(file)
            })
        
        return jsonify({'success': True, 'recordings': recordings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/recording/<recording_id>', methods=['DELETE'])
def delete_recording(recording_id):
    """Delete a recording"""
    try:
        # Find and delete the file
        for file in sessions_dir.glob('*.json'):
            with open(file, 'r') as f:
                data = json.load(f)
            if data.get('session_info', {}).get('id') == recording_id:
                file.unlink()
                return jsonify({'success': True, 'message': 'Recording deleted'})
        
        return jsonify({'success': False, 'error': 'Recording not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/recording/download/<recording_id>', methods=['POST'])
def download_recording(recording_id):
    """Download recording as JSON or CSV"""
    try:
        data = request.json
        format_type = data.get('format', 'json')
        
        # Find the recording file
        target_file = None
        for file in sessions_dir.glob('*.json'):
            with open(file, 'r') as f:
                file_data = json.load(f)
            if file_data.get('session_info', {}).get('id') == recording_id:
                target_file = file
                break
        
        if not target_file:
            return jsonify({'success': False, 'error': 'Recording not found'}), 404
        
        # Read the JSON file
        with open(target_file, 'r') as f:
            file_data = json.load(f)
        
        session_info = file_data.get('session_info', {})
        raw_data = file_data.get('data', [])
        
        if format_type == 'json':
            # Return JSON file
            buffer = io.BytesIO()
            buffer.write(json.dumps(file_data, indent=2).encode())
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='application/json',
                as_attachment=True,
                download_name=f"{session_info.get('name', 'session')}.json"
            )
        
        elif format_type == 'csv':
            # Convert to CSV
            buffer = io.StringIO()
            if raw_data:
                # Get all unique keys from data
                fieldnames = set()
                for item in raw_data:
                    fieldnames.update(item.keys())
                fieldnames = sorted(list(fieldnames))
                
                writer = csv.DictWriter(buffer, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(raw_data)
            
            # Convert to bytes
            csv_bytes = buffer.getvalue().encode()
            buffer_bytes = io.BytesIO(csv_bytes)
            
            return send_file(
                buffer_bytes,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"{session_info.get('name', 'session')}.csv"
            )
        
        else:
            return jsonify({'success': False, 'error': 'Unsupported format'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'connected': acquisition_app.is_connected if acquisition_app else False,
        'recording': acquisition_app.is_recording if acquisition_app else False
    })


def set_acquisition_app(app):
    """Set the acquisition app reference"""
    global acquisition_app
    acquisition_app = app


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
