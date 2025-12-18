#!/usr/bin/env python3
"""
Test script to verify all acquisition module components work correctly
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from src.acquisition import (
            SerialPacketReader,
            PacketParser,
            Packet,
            LSLStreamer,
            AcquisitionApp
        )
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_packet_parser():
    """Test packet parser functionality"""
    print("\nTesting PacketParser...")
    
    try:
        from src.acquisition import PacketParser
        
        parser = PacketParser()
        # Create a test packet: [SYNC1, SYNC2, CTR, CH0_H, CH0_L, CH1_H, CH1_L, END]
        test_packet = bytes([0xC7, 0x7C, 0x01, 0x10, 0x00, 0x20, 0x00, 0x01])
        
        packet = parser.parse(test_packet)
        
        assert packet.counter == 1, f"Expected counter=1, got {packet.counter}"
        assert packet.ch0_raw == 0x1000, f"Expected ch0_raw=4096, got {packet.ch0_raw}"
        assert packet.ch1_raw == 0x2000, f"Expected ch1_raw=8192, got {packet.ch1_raw}"
        
        print(f"✅ PacketParser works correctly")
        print(f"   Counter: {packet.counter}")
        print(f"   CH0: {packet.ch0_raw}")
        print(f"   CH1: {packet.ch1_raw}")
        return True
    except Exception as e:
        print(f"❌ PacketParser test failed: {e}")
        return False

def test_serial_reader():
    """Test serial reader instantiation"""
    print("\nTesting SerialPacketReader...")
    
    try:
        from src.acquisition import SerialPacketReader
        
        reader = SerialPacketReader(port="COM1", baud=230400)
        
        assert reader.port == "COM1"
        assert reader.baud == 230400
        assert reader.packet_len == 8
        
        print("✅ SerialPacketReader instantiates correctly")
        return True
    except Exception as e:
        print(f"❌ SerialPacketReader test failed: {e}")
        return False

def test_lsl_streams():
    """Test LSL streams"""
    print("\nTesting LSLStreamer...")
    
    try:
        from src.acquisition import LSLStreamer, LSL_AVAILABLE
        
        if not LSL_AVAILABLE:
            print("⚠️  pylsl not available - LSL tests skipped")
            return True
        
        streamer = LSLStreamer(
            "TestStream",
            channel_types=["EMG", "EOG"],
            channel_labels=["EMG_0", "EOG_1"],
            channel_count=2,
            nominal_srate=512.0
        )
        
        print("✅ LSLStreamer instantiates correctly")
        return True
    except Exception as e:
        print(f"❌ LSLStreamer test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Acquisition Module Verification Tests")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_packet_parser,
        test_serial_reader,
        test_lsl_streams
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n✅ All tests passed! Acquisition module is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
