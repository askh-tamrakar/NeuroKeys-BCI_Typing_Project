"""
RUN_EMG.py - Main EMG Pipeline Orchestrator (with web UI sliders)
 - Adds an HTTP server that serves a single-page UI with sliders for:
    * bandpass lowcut
    * bandpass highcut
    * notch frequency (0 = disable)
 - UI sends JSON commands over websocket to update server-side filters live.
"""

import asyncio
import json
import time
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import deque
import queue
import http.server
import socketserver
import urllib.parse
import time as _time

# Acquisition & filters (adjust imports to your project layout)
# Ensure those modules exist and StatefulFilter / design_emg_sos / design_notch_sos are available
from src.acquisition.emg_acquisition_modular import EMGAcquisitionModule
from src.preprocessing.emg2_filters import StatefulFilter, design_emg_sos, design_notch_sos

# websockets optional import
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets not installed. Install with: pip install websockets")


# ---------------------------
# Simple HTTP server to serve the UI
# ---------------------------
HTML_UI = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>EMG Live - Filter Controls</title>
  <style>
    body { font-family: Arial, Helvetica, sans-serif; margin: 14px; background:#fafafa; color:#222; }
    .card { background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 12px; }
    label { font-weight: bold; display:block; margin-bottom:4px; }
    .row { display:flex; gap:12px; align-items:center; }
    .value { min-width:48px; text-align:right; font-weight:bold; }
    #canvas { width:100%; height:220px; border:1px solid #ddd; background:#111; display:block; border-radius:6px; }
    button { padding:8px 12px; border-radius:6px; border: none; background:#0066cc; color:white; cursor:pointer; }
    button:disabled { background:#999; cursor:default; }
    .muted { color:#666; font-size:13px; }
  </style>
</head>
<body>
  <h2>EMG Live — Filter Controls & Plot</h2>

  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div class="muted">WebSocket</div>
        <div id="ws-state">Disconnected</div>
      </div>
      <div>
        <button id="btn-connect">Connect WS</button>
      </div>
    </div>
  </div>

  <div class="card">
    <label>Bandpass Lowcut (Hz)</label>
    <div class="row">
      <input id="lowcut" type="range" min="0.1" max="200" step="0.1" value="20" style="flex:1;">
      <div class="value" id="lowcut-val">20.0</div>
    </div>

    <label style="margin-top:10px;">Bandpass Highcut (Hz)</label>
    <div class="row">
      <input id="highcut" type="range" min="5" max="500" step="0.1" value="450" style="flex:1;">
      <div class="value" id="highcut-val">450.0</div>
    </div>

    <label style="margin-top:10px;">Notch Frequency (Hz) — set 0 to disable</label>
    <div class="row">
      <input id="notch" type="range" min="0" max="100" step="0.5" value="50" style="flex:1;">
      <div class="value" id="notch-val">50.0</div>
    </div>

    <div style="margin-top:10px;" class="muted">Q factor for notch: 30 (server-side)</div>
  </div>

  <div class="card">
    <label>Channel 0 Live (raw filtered samples)</label>
    <canvas id="canvas" width="1200" height="220"></canvas>
  </div>

<script>
(function(){
  const wsHost = location.hostname;
  const wsPort = 8765;
  let ws = null;
  let connected = false;

  const btn = document.getElementById('btn-connect');
  const wsState = document.getElementById('ws-state');

  const lowcut = document.getElementById('lowcut');
  const highcut = document.getElementById('highcut');
  const notch = document.getElementById('notch');
  const lowVal = document.getElementById('lowcut-val');
  const highVal = document.getElementById('highcut-val');
  const notchVal = document.getElementById('notch-val');

  // Canvas drawing setup
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  ctx.fillStyle = '#111';
  ctx.fillRect(0,0,W,H);

  // buffer for channel 0
  const buffer = [];

  function drawGrid(){
    ctx.fillStyle = '#111';
    ctx.fillRect(0,0,W,H);
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for(let i=0;i<W;i+=50){
      ctx.beginPath(); ctx.moveTo(i,0); ctx.lineTo(i,H); ctx.stroke();
    }
    for(let j=0;j<H;j+=40){
      ctx.beginPath(); ctx.moveTo(0,j); ctx.lineTo(W,j); ctx.stroke();
    }
  }

  function drawWave() {
    drawGrid();
    if (buffer.length === 0) return;
    // draw waveform scaled to canvas
    ctx.beginPath();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#00ff88';
    const N = Math.min(buffer.length, W);
    for (let i = 0; i < N; ++i) {
      const v = buffer[buffer.length - N + i]; // last N samples
      // scale value to canvas. We don't know ADC range; assume values centered 0..16384
      const x = i;
      const y = H - ((v + 8192) / 16384) * H; // naive mapping
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function appendDataChannel0(arr) {
    // arr is an array of numbers
    for (let v of arr) {
      buffer.push(v);
      if (buffer.length > W) buffer.shift();
    }
    drawWave();
  }

  function setWSState(s){
    wsState.textContent = s;
  }

  function sendFilterUpdate() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const cmd = {
      cmd: "update_filters",
      lowcut: parseFloat(lowcut.value),
      highcut: parseFloat(highcut.value),
      notch: parseFloat(notch.value),
      q: 30.0
    };
    ws.send(JSON.stringify(cmd));
  }

  // slider events
  function updateLabels(){
    lowVal.textContent = parseFloat(lowcut.value).toFixed(1);
    highVal.textContent = parseFloat(highcut.value).toFixed(1);
    notchVal.textContent = parseFloat(notch.value).toFixed(1);
  }
  lowcut.addEventListener('input', ()=>{ updateLabels(); sendFilterUpdate(); });
  highcut.addEventListener('input', ()=>{ updateLabels(); sendFilterUpdate(); });
  notch.addEventListener('input', ()=>{ updateLabels(); sendFilterUpdate(); });
  updateLabels();

  btn.addEventListener('click', ()=>{
    if (connected) {
      if (ws) ws.close();
      return;
    }
    const uri = `ws://${wsHost}:${wsPort}`;
    ws = new WebSocket(uri);

    ws.onopen = function(){
      connected = true;
      btn.textContent = "Disconnect WS";
      setWSState("Connected to " + uri);
      // immediately send current filter settings
      sendFilterUpdate();
    };
    ws.onclose = function(){
      connected = false;
      btn.textContent = "Connect WS";
      setWSState("Disconnected");
    };
    ws.onerror = function(e){
      console.error("WS error", e);
      setWSState("Error");
    };
    ws.onmessage = function(ev){
      try {
        const o = JSON.parse(ev.data);
        // expect payload with 'window' field: array of channels
        if (o.window && Array.isArray(o.window)) {
          // o.window is list of channels: [[ch0_samples], [ch1_samples], ...]
          const ch0 = o.window[0] || [];
          appendDataChannel0(ch0);
        } else if (o.type === 'ack') {
          // optional server ack
          console.log("Server ack:", o);
        }
      } catch (e) {
        // ok if non-json
      }
    };
  });

  // initial draw
  drawGrid();

})();
</script>
</body>
</html>
"""

class SimpleUIRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            content = HTML_UI.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # suppress default logging
        return


def start_http_ui(host="0.0.0.0", port=8000):
    """Run HTTP server that serves the UI page"""
    def run_server():
        with socketserver.TCPServer((host, port), SimpleUIRequestHandler) as httpd:
            print(f"✓ HTTP UI available at http://{host}:{port}/")
            try:
                httpd.serve_forever()
            except Exception:
                pass
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    _time.sleep(0.05)
    return t


# ---------------------------
# EMG Pipeline (same as before) with filter update support
# ---------------------------
class EMGPipeline:
    def __init__(
        self,
        sampling_rate: float = 512.0,
        num_channels: int = 2,
        ws_port: int = 8765,
        buffer_size: int = 1024,
        chunk_size: int = 64
    ):
        self.sampling_rate = sampling_rate
        self.num_channels = num_channels
        self.ws_port = ws_port
        self.buffer_size = buffer_size
        self.chunk_size = chunk_size

        # Acquisition queue
        self.raw_data_queue = queue.Queue()

        # Build default filter (EMG typical)
        self._band_low = 20.0
        self._band_high = 450.0
        self._notch_freq = 50.0
        self._notch_q = 30.0
        self._build_filter_from_presets()

        self.raw_buffers = [deque(maxlen=buffer_size) for _ in range(num_channels)]
        self.filtered_buffers = [deque(maxlen=buffer_size) for _ in range(num_channels)]
        self.time_buffer = deque(maxlen=buffer_size)

        self.is_recording = False
        self.is_running = False
        self.recorded_data = []
        self.save_path = Path("data/raw/session/emg")

        # Websocket
        self.websocket_server = None
        self.ws_loop = None
        self.connected_clients = set()
        self.ws_enabled = HAS_WEBSOCKETS

        # processing
        self.processing_thread = None

        # stats
        self.sample_count = 0
        self.packets_processed = 0
        self.session_start_time = None

    def _build_filter_from_presets(self):
        """(Re)builds the StatefulFilter instance using current presets."""
        sos = design_emg_sos(self.sampling_rate, lowcut=self._band_low, highcut=self._band_high, order=4)
        notch_ba = None
        if self._notch_freq and self._notch_freq > 0:
            notch_ba = design_notch_sos(self._notch_freq, self.sampling_rate, q=self._notch_q)
        # create StatefulFilter (this resets its state)
        self.emg_filter = StatefulFilter(sos=sos, notch_ba=notch_ba)

    def update_filters(self, lowcut: float, highcut: float, notch: float, q: float = 30.0):
        """Public method to update bandpass and notch freq; rebuilds filter state."""
        try:
            # sanity checks
            if lowcut <= 0:
                lowcut = 0.01
            if highcut <= lowcut:
                highcut = lowcut + 0.1
            self._band_low = float(lowcut)
            self._band_high = float(highcut)
            self._notch_freq = float(notch) if notch is not None else 0.0
            self._notch_q = float(q)
            self._build_filter_from_presets()
            print(f"✓ Filters updated: band={self._band_low:.2f}-{self._band_high:.2f}Hz notch={self._notch_freq}Hz q={self._notch_q}")
            # optionally send ack to clients
            self._send_ack_to_clients({
                "type": "ack",
                "message": "filters_updated",
                "band_low": self._band_low,
                "band_high": self._band_high,
                "notch": self._notch_freq
            })
        except Exception as e:
            print(f"[Filter Update Error] {e}")

    def _send_ack_to_clients(self, payload: dict):
        if not self.connected_clients or not self.ws_loop:
            return
        try:
            msg = json.dumps(payload)
            for client in list(self.connected_clients):
                try:
                    asyncio.run_coroutine_threadsafe(client.send(msg), self.ws_loop)
                except Exception:
                    self.connected_clients.discard(client)
        except Exception:
            pass

    def add_raw_data(self, channel_data: dict):
        self.raw_data_queue.put(channel_data)

    def start(self, use_websocket: bool = True, start_http_ui_flag: bool = True):
        print("\n" + "="*60)
        print("Starting EMG Pipeline")
        print("="*60)
        self.is_running = True
        self.session_start_time = datetime.now()
        self.sample_count = 0

        # processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        print(f"✓ Processing thread started - {self.num_channels} channels @ {self.sampling_rate}Hz")

        # start websocket
        if use_websocket and self.ws_enabled:
            self._start_websocket_server()

        # start HTTP UI
        if start_http_ui_flag:
            start_http_ui(host="0.0.0.0", port=8000)

    def stop(self):
        print("\nStopping EMG Pipeline...")
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2)

        if self.websocket_server and self.ws_loop:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown_websocket(), self.ws_loop)
            except Exception as e:
                print(f"[Stop] Failed to schedule websocket shutdown: {e}")

        print("="*60)
        print(f"Total samples processed: {self.sample_count}")
        print(f"Total packets: {self.packets_processed}")
        print("="*60 + "\n")

    def _processing_loop(self):
        chunk_buffer = [[] for _ in range(self.num_channels)]
        while self.is_running:
            try:
                raw_data = self.raw_data_queue.get(timeout=0.1)
                ch0_raw = raw_data.get('ch0_raw_adc', 0)
                ch1_raw = raw_data.get('ch1_raw_adc', 0) if self.num_channels > 1 else 0
                timestamp = raw_data.get('timestamp', datetime.now())

                # filtering
                ch0_filtered = self.emg_filter.process_sample(ch0_raw)
                if self.num_channels > 1:
                    ch1_filtered = self.emg_filter.process_sample(ch1_raw)
                else:
                    ch1_filtered = 0

                # buffers
                self.raw_buffers[0].append(ch0_raw)
                self.filtered_buffers[0].append(ch0_filtered)
                if self.num_channels > 1:
                    self.raw_buffers[1].append(ch1_raw)
                    self.filtered_buffers[1].append(ch1_filtered)
                self.time_buffer.append(self.sample_count / self.sampling_rate)

                # chunk
                chunk_buffer[0].append(ch0_filtered)
                if self.num_channels > 1:
                    chunk_buffer[1].append(ch1_filtered)

                if self.is_recording:
                    self.recorded_data.append({
                        'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
                        'ch0_raw': ch0_raw,
                        'ch0_filtered': ch0_filtered,
                        'ch1_raw': ch1_raw if self.num_channels > 1 else None,
                        'ch1_filtered': ch1_filtered if self.num_channels > 1 else None,
                    })

                self.sample_count += 1

                if len(chunk_buffer[0]) >= self.chunk_size:
                    self._broadcast_websocket(chunk_buffer)
                    chunk_buffer = [[] for _ in range(self.num_channels)]
                    self.packets_processed += 1

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Processing Error] {e}")
                continue

    def _broadcast_websocket(self, chunk_data: list):
        if not self.connected_clients or not self.ws_enabled or not self.ws_loop:
            return
        try:
            payload = {
                'source': 'EMG',
                'timestamp': time.time() * 1000,
                'fs': self.sampling_rate,
                'window': chunk_data,
            }
            message = json.dumps(payload)
            for client in list(self.connected_clients):
                try:
                    if getattr(client, 'closed', False):
                        self.connected_clients.discard(client)
                        continue
                except Exception:
                    pass
                try:
                    asyncio.run_coroutine_threadsafe(client.send(message), self.ws_loop)
                except Exception:
                    self.connected_clients.discard(client)
        except Exception as e:
            print(f"[WebSocket Broadcast Error] {e}")

    def _start_websocket_server(self):
        if not HAS_WEBSOCKETS:
            print("⚠ WebSocket disabled (websockets module not installed)")
            return

        def run_ws_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.ws_loop = loop
            server_obj = None

            async def handler(websocket, path=None):
                # Add websocket only
                self.connected_clients.add(websocket)
                addr = websocket.remote_address if hasattr(websocket, 'remote_address') else "unknown"
                print(f"[WebSocket] Client connected: {addr}")

                try:
                    async for message in websocket:
                        # try parse JSON commands
                        try:
                            o = json.loads(message)
                            if isinstance(o, dict) and o.get('cmd') == 'update_filters':
                                low = float(o.get('lowcut', self._band_low))
                                high = float(o.get('highcut', self._band_high))
                                notch = float(o.get('notch', self._notch_freq))
                                q = float(o.get('q', self._notch_q))
                                # update server-side filters
                                self.update_filters(low, high, notch, q=q)
                                # reply ack
                                try:
                                    await websocket.send(json.dumps({"type":"ack","message":"filters_set"}))
                                except Exception:
                                    pass
                                continue
                        except json.JSONDecodeError:
                            # not JSON; maybe "ping"
                            pass
                        # simple ping/pong
                        if message == "ping":
                            try:
                                await websocket.send("pong")
                            except Exception:
                                pass
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    print(f"[WebSocket handler error] {e}")
                finally:
                    try:
                        self.connected_clients.discard(websocket)
                        print(f"[WebSocket] Client disconnected: {addr}")
                    except Exception:
                        pass

            async def start_server_coro():
                nonlocal server_obj
                server_obj = await websockets.serve(handler, "0.0.0.0", self.ws_port)
                self.websocket_server = server_obj
                print(f"✓ WebSocket server listening on ws://0.0.0.0:{self.ws_port}")
                await server_obj.wait_closed()

            try:
                loop.run_until_complete(start_server_coro())
            except Exception as e:
                print(f"[WebSocket server error] {e}")
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()

        ws_thread = threading.Thread(target=run_ws_server, daemon=True)
        ws_thread.start()
        _time.sleep(0.05)

    async def _shutdown_websocket(self):
        if self.websocket_server:
            try:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
                print("✓ WebSocket server shut down")
            except Exception as e:
                print(f"[WebSocket shutdown error] {e}")
        try:
            for c in list(self.connected_clients):
                try:
                    await c.close()
                except Exception:
                    pass
            self.connected_clients.clear()
        except Exception:
            pass

    # recording & utility methods unchanged
    def start_recording(self):
        self.is_recording = True
        self.recorded_data = []
        print("✓ Recording started")

    def stop_recording(self):
        self.is_recording = False
        if not self.recorded_data:
            print("⚠ No data to save")
            return None
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            folder = self.save_path
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"EMG_recording_{timestamp}.json"
            filepath = folder / filename
            metadata = {
                "recording_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
                    "total_samples": len(self.recorded_data),
                    "sampling_rate_hz": self.sampling_rate,
                    "channels": self.num_channels,
                },
                "data": self.recorded_data
            }
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"✓ Saved {len(self.recorded_data)} samples to {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"✗ Save failed: {e}")
            return None

    def get_current_data(self) -> dict:
        return {
            'raw': [list(buf) for buf in self.raw_buffers],
            'filtered': [list(buf) for buf in self.filtered_buffers],
            'timestamps': list(self.time_buffer),
            'sample_count': self.sample_count,
            'packets_processed': self.packets_processed,
        }

    def get_statistics(self) -> dict:
        elapsed = (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        stats = {
            'sample_count': self.sample_count,
            'packets_processed': self.packets_processed,
            'elapsed_seconds': elapsed,
            'sample_rate': self.sample_count / elapsed if elapsed > 0 else 0,
            'websocket_clients': len(self.connected_clients) if self.ws_enabled else 0,
            'is_recording': self.is_recording,
        }
        for ch in range(self.num_channels):
            if len(self.filtered_buffers[ch]) > 0:
                data = np.array(list(self.filtered_buffers[ch]))
                stats[f'ch{ch}_min'] = float(np.min(data))
                stats[f'ch{ch}_max'] = float(np.max(data))
                stats[f'ch{ch}_mean'] = float(np.mean(data))
        return stats


# ---------------------------
# Integration bridge for Tkinter UI (unchanged)
# ---------------------------
class EMGAcquisitionBridge:
    def __init__(self, tkinter_app, pipeline: EMGPipeline):
        self.app = tkinter_app
        self.pipeline = pipeline
        self.original_parse_method = tkinter_app.parse_and_store_packet
        tkinter_app.parse_and_store_packet = self.parse_and_forward

    def parse_and_forward(self, packet):
        try:
            counter = packet[2]
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            timestamp = datetime.now()

            self.pipeline.add_raw_data({
                'ch0_raw_adc': ch0_raw,
                'ch1_raw_adc': ch1_raw,
                'timestamp': timestamp,
                'sequence_counter': int(counter),
            })

            try:
                self.app.graph_buffer_ch0.append(ch0_raw)
                self.app.graph_buffer_ch1.append(ch1_raw)
                self.app.graph_time_buffer.append(self.app.graph_index)
                self.app.graph_index += 1
                self.app.packet_count += 1
                self.app.latest_packet = {
                    'timestamp': timestamp.isoformat(),
                    'ch0_raw_adc': ch0_raw,
                    'ch1_raw_adc': ch1_raw,
                    'sequence_counter': int(counter),
                }
                self.app.pending_updates += 1
            except Exception:
                pass

        except Exception as e:
            print(f"Bridge parse error: {e}")


# ---------------------------
# Main
# ---------------------------
def main():
    pipeline = EMGPipeline(
        sampling_rate=512.0,
        num_channels=2,
        ws_port=8765,
        buffer_size=2048,
        chunk_size=64
    )
    pipeline.start(use_websocket=True, start_http_ui_flag=True)

    # Tkinter acquisition UI
    import tkinter as tk
    from src.acquisition.emg_acquisition import EMGAcquisitionApp

    root = tk.Tk()
    app = EMGAcquisitionApp(root)

    bridge = EMGAcquisitionBridge(app, pipeline)

    original_start = app.start_acquisition
    original_stop = app.stop_acquisition

    def start_with_pipeline():
        original_start()
        pipeline.start_recording()

    def stop_with_pipeline():
        pipeline.stop_recording()
        original_stop()

    app.start_acquisition = start_with_pipeline
    app.stop_acquisition = stop_with_pipeline

    print("✓ Tkinter UI connected to pipeline")
    print("✓ WebSocket server on ws://localhost:8765")
    print("✓ HTTP UI on http://localhost:8000 (open this in a browser to control filters)")

    try:
        root.mainloop()
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
