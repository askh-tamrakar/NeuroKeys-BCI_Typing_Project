import socket
import threading
import sys
import os
import time
import struct
import json
from pathlib import Path

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src.acquisition.lsl_streams import LSLStreamer, LSL_AVAILABLE

# Configuration
PORTS = {
    "raw": 6000,
    "processed": 6001,
    "events": 6002
}

STREAMS = {}

def handle_raw_connection(conn, addr, streamer):
    """
    Handle connection for Raw Data.
    Expects binary data: [Value1 (float), Value2 (float)] per sample.
    Simple protocol: Just stream of floats (4 bytes each).
    Packet size: 2 channels * 4 bytes = 8 bytes.
    """
    print(f"[StreamManager] 🔌 Raw source connected: {addr}")
    try:
        # We assume 2 channels of floats (8 bytes)
        # Using struct because it's efficient
        packet_size = 8 
        while True:
            data = conn.recv(packet_size)
            if not data or len(data) < packet_size:
                break
            
            # Unpack 2 floats
            # '<ff' means little-endian, 2 floats
            try:
                samples = struct.unpack('<ff', data)
                streamer.push_sample(samples)
            except Exception:
                pass
                
    except Exception as e:
        print(f"[StreamManager] Raw stream error: {e}")
    finally:
        print(f"[StreamManager] Raw source disconnected: {addr}")
        conn.close()

def handle_processed_connection(conn, addr, streamer):
    """
    Handle connection for Processed Data.
    Expects binary data: N channels * 4 bytes.
    For now, assume fixed channels or length-prefixed?
    Let's use length-prefixed for flexibility since processed might change.
    Protocol: [NumChannels (int 1 byte)] [Float1] [Float2] ...
    Actually, let's stick to 2 channels for now as per `filter_router.py` logic?
    Wait, `filter_router.py` handles dynamic channels. 
    Ideally, we send JSON lines for complex variable data, but binary is faster.
    Let's use a simple protocol:
    [Header: 0xAA] [Count (1 byte)] [Floats...]
    """
    print(f"[StreamManager] 🔌 Processed source connected: {addr}")
    try:
        while True:
            # Read header
            header = conn.recv(2) # 0xAA + Count
            if not header or len(header) < 2:
                break
            
            sync, count = header
            if sync != 0xAA:
                continue # Lost sync?
                
            payload_size = count * 4
            data = conn.recv(payload_size)
            if len(data) < payload_size:
                break
                
            fmt = f'<{count}f'
            samples = struct.unpack(fmt, data)
            streamer.push_sample(samples)
            
    except Exception as e:
        print(f"[StreamManager] Processed stream error: {e}")
    finally:
        print(f"[StreamManager] Processed source disconnected: {addr}")
        conn.close()

def handle_events_connection(conn, addr, streamer):
    """
    Handle events.
    Expects newline-delimited JSON strings or strings.
    """
    print(f"[StreamManager] 🔌 Event source connected: {addr}")
    buffer = b""
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            buffer += chunk
            
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                try:
                    msg = line.decode('utf-8').strip()
                    if msg:
                        streamer.push_sample([msg])
                except Exception:
                    pass
                    
    except Exception as e:
        print(f"[StreamManager] Event stream error: {e}")
    finally:
        print(f"[StreamManager] Event source disconnected: {addr}")
        conn.close()


def server_thread(port, handle_func, streamer):
    """Generic server thread."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port))
    s.listen(1)
    # Get stream name safely
    stream_name = 'Unknown'
    if streamer:
        if hasattr(streamer, 'name'):
            stream_name = streamer.name
        elif hasattr(streamer, 'info'): # Raw pylsl outlet
            try:
                stream_name = streamer.info().name()
            except:
                pass
                
    print(f"[StreamManager] 👂 Listening on {port} for {stream_name}")
    
    while True:
        try:
            conn, addr = s.accept()
            # Handle one client at a time per port (simplification)
            # Or spawn a thread per client? 
            # We typically only have ONE source per stream type (e.g. ONE acquisition app).
            # So one-at-a-time is fine.
            handle_func(conn, addr, streamer)
        except Exception as e:
            print(f"[StreamManager] Server error on {port}: {e}")
            time.sleep(1)

def main():
    print("="*50)
    print("   BRIDGE Stream Manager (LSL Broker)")
    print("="*50)
    
    if not LSL_AVAILABLE:
        print("❌ LSL not available! Install pylsl.")
        return

    # 1. Create LSL Outlets
    # Raw
    STREAMS['raw'] = LSLStreamer(
        "BioSignals-Raw-uV",
        channel_types=["EMG", "EOG"],
        channel_labels=["EMG_0", "EOG_1"],
        channel_count=2,
        nominal_srate=512
    )
    
    # Processed
    # Note: We configure it generically; consumers check metadata.
    # We might need to receive metadata from the source to fully configure this?
    # For now, we init with 2 channels, but pylsl outlets are rigid once created.
    # If filter_router changes channels, we might have an issue.
    # However, the user request says "creates three different lsl streams".
    STREAMS['processed'] = LSLStreamer(
        "BioSignals-Processed",
        channel_types=["EMG", "EOG"], # Default
        channel_labels=["EMG_filt", "EOG_filt"],
        channel_count=2,
        nominal_srate=512
    )
    
    # Events
    try:
        import pylsl
        info = pylsl.StreamInfo('BioSignals-Events', 'Markers', 1, 0, 'string', 'BioSignals-Events-Ind')
        STREAMS['events'] = pylsl.StreamOutlet(info)
        print("[StreamManager] Created stream 'BioSignals-Events' (Markers)")
    except Exception as e:
        print(f"Error creating event stream: {e}")

    # 2. Start Server Threads
    t1 = threading.Thread(target=server_thread, args=(PORTS['raw'], handle_raw_connection, STREAMS['raw']), daemon=True)
    t2 = threading.Thread(target=server_thread, args=(PORTS['processed'], handle_processed_connection, STREAMS['processed']), daemon=True)
    
    # For events, we need a wrapper because LSLStreamer logic is for floats.
    # We'll use a lambda or small wrapper class if `push_sample` matches.
    # `pylsl.StreamOutlet.push_sample` takes a list.
    t3 = threading.Thread(target=server_thread, args=(PORTS['events'], handle_events_connection, STREAMS['events']), daemon=True)

    t1.start()
    t2.start()
    t3.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[StreamManager] Stopping...")
        sys.exit(0)

if __name__ == "__main__":
    main()
