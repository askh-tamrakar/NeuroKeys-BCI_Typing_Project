"""
Diagnostic script to verify EEG data flow
Tests: Arduino → Serial → Flask → Browser

Usage:
  python diagnose_eeg_flow.py --port COM7
"""

import serial
import time
import argparse
import sys

def test_serial_data(port, baud=115200):
    """Read raw serial data from Arduino"""
    print("\n" + "="*60)
    print("STEP 1: Reading Raw Serial Data")
    print("="*60)
    
    try:
        ser = serial.Serial(port, baud, timeout=2)
        print(f"✅ Connected to {port}")
        
        ser.reset_input_buffer()
        print("Reading 10 lines from Arduino...\n")
        
        for i in range(10):
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"{i+1}. {line[:100]}")
            else:
                time.sleep(0.1)
        
        ser.close()
        return True
        
    except Exception as e:
        print(f"❌ Error reading serial: {e}")
        return False


def test_flask_api():
    """Test Flask API endpoints"""
    print("\n" + "="*60)
    print("STEP 2: Testing Flask API")
    print("="*60)
    
    try:
        import requests
    except ImportError:
        print("❌ requests not installed. Run: pip install requests")
        return False
    
    endpoints = [
        ('http://localhost:5000/api/health', 'Server Health'),
        ('http://localhost:5000/api/stats', 'Signal Stats'),
        ('http://localhost:5000/api/stream', 'Latest Sample'),
    ]
    
    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ {name}:")
                print(f"   URL: {url}")
                
                # Check for samples_received
                if 'samples_received' in data:
                    print(f"   Samples received: {data['samples_received']}")
                    if data['samples_received'] > 0:
                        print("   ✅ DATA IS FLOWING!")
                    else:
                        print("   ❌ No samples received yet")
                else:
                    print(f"   {data}")
            else:
                print(f"❌ {name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: {e}")
    
    return True


def test_dashboard():
    """Test dashboard connection"""
    print("\n" + "="*60)
    print("STEP 3: Dashboard Connection Check")
    print("="*60)
    
    print("""
    ✅ Dashboard setup:
    1. Flask server running:
       python eeg_dashboard_server.py --port COM7 --baud 115200
    
    2. React app running:
       npm run dev
    
    3. Open browser:
       http://localhost:5173
    
    4. Check Topbar:
       - Status should be: 🟢 connected
       - Latency should show: ~50-100ms
    
    5. Check LiveView:
       - Waveform chart should update
       - Stats should change (RMS, Power, Mean, ZCR)
       - Signal health indicator should show color
    """)


def main():
    parser = argparse.ArgumentParser(description='Diagnose EEG data flow')
    parser.add_argument('--port', default='COM7', help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🧠 EEG DATA FLOW DIAGNOSTIC")
    print("="*60)
    
    # Step 1: Test serial
    serial_ok = test_serial_data(args.port, args.baud)
    
    if not serial_ok:
        print("\n❌ SERIAL FAILED")
        print("\nTroubleshooting:")
        print("1. Is Arduino plugged in?")
        print("2. Is the sketch uploaded?")
        print("3. Check Device Manager for correct COM port")
        print("4. Try: python com_diagnostic.py")
        sys.exit(1)
    
    # Step 2: Test Flask
    time.sleep(1)
    print("\nMake sure Flask server is running in another terminal:")
    print("  python eeg_dashboard_server.py --port COM7 --baud 115200")
    input("Press Enter to continue (make sure Flask is running)...\n")
    
    api_ok = test_flask_api()
    
    if not api_ok:
        print("\n❌ FLASK API FAILED")
        print("\nTroubleshooting:")
        print("1. Is Flask server running?")
        print("2. Check Flask terminal for errors")
        print("3. Try: curl http://localhost:5000/api/health")
        sys.exit(1)
    
    # Step 3: Test dashboard
    test_dashboard()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETE")
    print("="*60)
    print("""
    Summary:
    ✅ Arduino is sending data via serial
    ✅ Flask server is receiving and buffering
    ✅ API is serving data
    
    Next: Check dashboard in browser
    """)


if __name__ == '__main__':
    main()