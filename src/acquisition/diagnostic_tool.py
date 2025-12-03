"""
EOG Serial Diagnostic Tool
Helps troubleshoot why Arduino is not sending data
"""

import serial
import serial.tools.list_ports
import time
import sys


def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)


def list_ports():
    """List all available serial ports"""
    print_header("Available Serial Ports")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("❌ No serial ports found!")
        return []
    
    for i, (port, desc, hwid) in enumerate(ports):
        print(f"{i}: {port}")
        print(f"   Description: {desc}")
        print(f"   Hardware ID: {hwid}")
    
    return ports


def test_connection(port, baud=230400):
    """Test if we can connect to the port"""
    print_header(f"Testing Connection: {port} @ {baud} baud")
    
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"✅ Connection successful")
        time.sleep(2)  # Wait for Arduino to initialize
        
        # Try to read some data
        print("\n⏳ Waiting for data (5 seconds)...")
        print("Expected: Should see bytes coming in")
        
        data_received = False
        start = time.time()
        
        while time.time() - start < 5:
            if ser.in_waiting > 0:
                data_received = True
                break
            time.sleep(0.1)
        
        if data_received:
            print(f"✅ Data detected! {ser.in_waiting} bytes in buffer")
            return ser
        else:
            print("❌ No data received after 5 seconds")
            print("\nPossible issues:")
            print("  1. Arduino not running the correct sketch")
            print("  2. Arduino not powered")
            print("  3. Sketch has 'START' command requirement")
            print("  4. USB cable issue")
            return None
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None


def read_raw_bytes(ser, duration=5):
    """Read raw bytes and display them"""
    print_header(f"Reading Raw Bytes ({duration} seconds)")
    
    bytes_read = bytearray()
    start = time.time()
    count = 0
    
    print(f"{'Time':<8} {'Byte (Hex)':<12} {'Byte (Dec)':<12} {'Pattern':<20}")
    print("-" * 60)
    
    while time.time() - start < duration:
        if ser.in_waiting > 0:
            byte = ser.read(1)
            bytes_read.extend(byte)
            count += 1
            
            hex_val = hex(byte[0])
            dec_val = str(byte[0])
            
            # Detect patterns
            pattern = ""
            if byte[0] == 0xC7:
                pattern = "← SYNC1 (packet start!)"
            elif byte[0] == 0x7C:
                pattern = "← SYNC2 (packet start!)"
            elif byte[0] == 0x01:
                pattern = "← END (packet end!)"
            
            elapsed = time.time() - start
            print(f"{elapsed:>7.2f}s {hex_val:<12} {dec_val:<12} {pattern:<20}")
            
            if count >= 50:  # Show first 50 bytes
                print("... (showing first 50 bytes)")
                break
        else:
            time.sleep(0.01)
    
    print(f"\nTotal bytes received: {count}")
    if count == 0:
        print("❌ NO DATA RECEIVED")
    else:
        print(f"✅ Data flowing: {count} bytes")
    
    return bytes_read


def detect_packets(bytes_data):
    """Try to detect packet structure"""
    print_header("Packet Structure Detection")
    
    if len(bytes_data) < 10:
        print(f"❌ Not enough data ({len(bytes_data)} bytes, need at least 10)")
        return
    
    print(f"Total bytes: {len(bytes_data)}\n")
    
    # Look for SYNC pattern (0xC7 0x7C)
    sync_positions = []
    for i in range(len(bytes_data) - 1):
        if bytes_data[i] == 0xC7 and bytes_data[i+1] == 0x7C:
            sync_positions.append(i)
    
    if not sync_positions:
        print("❌ No SYNC pattern found (0xC7 0x7C)")
        print("\nThis means:")
        print("  - Arduino is sending garbage")
        print("  - Baud rate mismatch")
        print("  - USB cable issue")
        print("  - Arduino sketch not running")
        return
    
    print(f"✅ Found {len(sync_positions)} SYNC pattern(s) at positions: {sync_positions}\n")
    
    # Analyze spacing
    if len(sync_positions) >= 2:
        spacing = sync_positions[1] - sync_positions[0]
        print(f"Spacing between SYNC bytes: {spacing} bytes")
        
        if spacing == 8:
            print("✅ CORRECT: 8-byte packets detected!")
        elif spacing == 16:
            print("⚠️  16-byte packets? (Old format?)")
        else:
            print(f"❓ Unexpected spacing: {spacing} bytes")
    
    # Show first few packets
    print("\nFirst 3 packet attempts:")
    for idx in range(min(3, len(sync_positions))):
        pos = sync_positions[idx]
        packet_end = min(pos + 10, len(bytes_data))
        packet = bytes_data[pos:packet_end]
        
        print(f"\nPacket {idx+1} at position {pos}:")
        print(f"  Hex: {' '.join(f'{b:02X}' for b in packet)}")
        
        if len(packet) >= 8:
            print(f"  Byte 0: {packet[0]:02X} (SYNC1, expect 0xC7)")
            print(f"  Byte 1: {packet[1]:02X} (SYNC2, expect 0x7C)")
            print(f"  Byte 2: {packet[2]:02X} (Counter)")
            print(f"  Byte 3-4: {packet[3]:02X} {packet[4]:02X} (Ch0)")
            print(f"  Byte 5-6: {packet[5]:02X} {packet[6]:02X} (Ch1)")
            print(f"  Byte 7: {packet[7]:02X} (END, expect 0x01)")
            
            if packet[7] == 0x01:
                print("  ✅ Valid end byte!")
            else:
                print(f"  ❌ Invalid end byte (expected 0x01, got {packet[9]:02X})")


def test_arduino_commands(ser):
    """Test if Arduino responds to commands"""
    print_header("Testing Arduino Commands")
    
    commands = [
        ("WHORU\n", "Device identification"),
        ("CONFIG\n", "Configuration info"),
        ("STATUS\n", "Current status"),
        ("START\n", "Start acquisition"),
    ]
    
    for cmd, description in commands:
        print(f"\nSending: {cmd.strip()} ({description})")
        
        # Clear buffer
        ser.reset_input_buffer()
        time.sleep(0.1)
        
        # Send command
        ser.write(cmd.encode())
        time.sleep(0.5)
        
        # Read response
        if ser.in_waiting > 0:
            response = ser.read_all()
            print(f"✅ Response: {response.decode('utf-8', errors='ignore')}")
        else:
            print("❌ No response from Arduino")


def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  EOG SERIAL DIAGNOSTIC TOOL".center(58) + "║")
    print("║" + "  Troubleshoot Arduino Connection Issues".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # Step 1: List ports
    ports = list_ports()
    if not ports:
        print("\n❌ No serial ports found. Check USB cable.")
        sys.exit(1)
    
    # Step 2: Select port
    print_header("Select Port")
    port_idx = 0
    if len(ports) > 1:
        port_idx = int(input("Enter port number [0]: ") or "0")
    
    port_name = ports[port_idx][0]
    print(f"Selected: {port_name}")
    
    # Step 3: Test connection
    ser = test_connection(port_name)
    if not ser or not ser.is_open:
        print("\n❌ Could not establish connection")
        sys.exit(1)
    
    # Step 4: Read raw bytes
    try:
        bytes_data = read_raw_bytes(ser, duration=5)
        
        # Step 5: Detect packets
        if bytes_data:
            detect_packets(bytes_data)
        
        # Step 6: Test commands
        print_header("Arduino Command Test")
        response = input("Test Arduino commands? (y/n): ")
        if response.lower() == 'y':
            test_arduino_commands(ser)
        
    finally:
        ser.close()
    
    print_header("Diagnostic Complete")
    print("\nNext steps based on results:")
    print("  ✅ If data flowing: Check packet parsing in Python app")
    print("  ❌ If no data: Check Arduino sketch and USB cable")
    print("  ⚠️  If wrong format: Verify Arduino sketch matches expectations")


if __name__ == "__main__":
    main()
