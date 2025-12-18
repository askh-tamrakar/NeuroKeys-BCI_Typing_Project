# src/acquisition/lsl_streams.py
"""
LSLStreamer + helpers
- Lightweight helpers to create LSL outlets for:
    - BioSignals-Raw (raw ADC ints)
    - BioSignals (processed µV floats)
- Also provides helper to add channel metadata (label & type)
"""

from typing import List, Optional
try:
    import pylsl
    LSL_AVAILABLE = True
except Exception:
    pylsl = None
    LSL_AVAILABLE = False
    print("⚠️  pylsl not available - LSL streams will be disabled. Install with `pip install pylsl`.")


class LSLStreamer:
    def __init__(self, name: str, channel_types: List[str], channel_labels: Optional[List[str]] = None,
                 channel_count: Optional[int] = None, nominal_srate: float = 512.0, source_id: Optional[str] = None):
        """
        name: stream name
        channel_types: list of type strings (e.g., ['EMG','EMG'] or ['EEG','EOG'])
        channel_labels: optional list of labels; length should match channel_types
        channel_count: if provided, used as channel_count; else len(channel_types)
        """
        self.name = name
        self.channel_types = channel_types or []
        self.channel_labels = channel_labels or []
        self.nominal_srate = nominal_srate
        self.source_id = source_id or name
        self.channel_count = channel_count if channel_count is not None else max(1, len(self.channel_types))
        self.outlet: Optional[pylsl.StreamOutlet] = None

        if LSL_AVAILABLE:
            self._create_outlet()
        else:
            print(f"[LSLStreamer] LSL not available - '{self.name}' stubbed")

    def _create_outlet(self):
        try:
            info = pylsl.StreamInfo(
                name=self.name,
                type='EEG',  # general type; consumers will inspect channel metadata
                channel_count=self.channel_count,
                nominal_srate=float(self.nominal_srate),
                channel_format='float32',
                source_id=self.source_id
            )
            channels = info.desc().append_child("channels")
            # If types provided, use them; otherwise label generically
            for i in range(self.channel_count):
                label = self.channel_labels[i] if i < len(self.channel_labels) else f"ch{i}"
                typ = self.channel_types[i] if i < len(self.channel_types) else ""
                ch = channels.append_child("channel")
                ch.append_child_value("label", str(label))
                if typ:
                    ch.append_child_value("type", str(typ))
            self.outlet = pylsl.StreamOutlet(info)
            print(f"[LSLStreamer] Created stream '{self.name}' (channels={self.channel_count})")
        except Exception as e:
            print(f"[LSLStreamer] Failed to create LSL outlet '{self.name}': {e}")
            self.outlet = None

    def push_sample(self, sample: List[float], ts: Optional[float] = None):
        if not LSL_AVAILABLE or self.outlet is None:
            return
        try:
            if ts is not None:
                self.outlet.push_sample(sample, ts)
            else:
                self.outlet.push_sample(sample)
        except Exception as e:
            print(f"[LSLStreamer] push_sample error for '{self.name}': {e}")

    def push_chunk(self, chunk: List[List[float]], ts: Optional[float] = None):
        """Push a list of samples at once"""
        if not LSL_AVAILABLE or self.outlet is None or not chunk:
            return
        try:
            if ts is not None:
                self.outlet.push_chunk(chunk, ts)
            else:
                self.outlet.push_chunk(chunk)
        except Exception as e:
            print(f"[LSLStreamer] push_chunk error for '{self.name}': {e}")
