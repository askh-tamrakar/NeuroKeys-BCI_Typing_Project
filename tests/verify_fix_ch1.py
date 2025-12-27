
import sys
import os
import struct
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.acquisition.packet_parser import PacketParser
from src.feature.extractors.blink_extractor import BlinkExtractor

def test_packet_parser():
    print("[Test] Verification of PacketParser...")
    parser = PacketParser(packet_len=12)
    
    # Create a mock 12-byte packet
    # Sync1(0xC7), Sync2(0x7C), Counter(100), Ch0(1000), Ch1(2000), Ch2(3000), Ch3(4000), End(0x01)
    # >BHHHH format for payload
    payload = struct.pack(">BHHHH", 100, 1000, 2000, 3000, 4000)
    mock_packet = b'\xC7\x7C' + payload + b'\x01'
    
    assert len(mock_packet) == 12
    
    pkt = parser.parse(mock_packet)
    
    assert pkt.counter == 100
    assert pkt.ch0_raw == 1000
    assert pkt.ch1_raw == 2000
    assert pkt.ch2_raw == 3000
    assert pkt.ch3_raw == 4000
    
    print("[PASS] PacketParser correctly parsed 4-channel packet.")

def test_blink_extractor():
    print("[Test] Verification of BlinkExtractor threshold...")
    
    config = {
        "features": {
            "EOG": {
                "amp_threshold": 1.0 # The pivotal fix
            }
        }
    }
    
    extractor = BlinkExtractor(channel_index=1, config=config, sr=512)
    
    # Baseline is 0 initially.
    # Feed 3.0 (Signal > Threshold)
    extractor.process(0.0) # Init baseline
    
    # Trigger?
    res = extractor.process(3.0)
    
    if extractor.is_collecting:
        print("[PASS] BlinkExtractor triggered collection for input 3.0 with threshold 1.0")
    else:
        print(f"[FAIL] BlinkExtractor did NOT trigger collection. Threshold: {extractor.amp_threshold}, Input: 3.0")
        sys.exit(1)

if __name__ == "__main__":
    try:
        test_packet_parser()
        test_blink_extractor()
        print("\nAll verifications passed!")
    except Exception as e:
        print(f"\n[FAIL] verification failed: {e}")
        sys.exit(1)
