"""
EMG Data Acquisition Application
Arduino Serial Communication with PyQt5 GUI
Saves EMG data to JSON with timestamps

Author: EMG Team
Date: 2024-12-03
"""

import sys
import json
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QTextEdit, QSpinBox, QFileDialog,
    QMessageBox, QGroupBox, QStatusBar, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon


class SerialWorker(QObject):
    """Worker thread for serial communication"""
    
    # Signals
    data_received = pyqtSignal(dict)  # Emits parsed packet data
    status_changed = pyqtSignal(str)  # Emits status messages
    error_occurred = pyqtSignal(str)  # Emits error messages
    packet_count_updated = pyqtSignal(int)  # Emits packet count
    
    def __init__(self):
        super().__init__()
        self.ser = None
        self.is_running = False
        self.packet_count = 0
        self.data_buffer = []
        
    def connect_port(self, port, baudrate):
        """Establish serial connection"""
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.status_changed.emit(f"Connected to {port} @ {baudrate} baud")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Connection failed: {str(e)}")
            return False
    
    def disconnect_port(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.status_changed.emit("Disconnected from serial port")
    
    def parse_packet(self, packet):
        """Parse 10-byte EMG packet from Arduino
        
        Packet structure (10 bytes):
        Byte 0: Sync Byte 1 (0xC7)
        Byte 1: Sync Byte 2 (0x7C)
        Byte 2: Counter (0-255)
        Byte 3-4: Channel 0 (ADC value, little-endian)
        Byte 5-6: Channel 1 (ADC value, little-endian)
        Byte 7-8: Reserved
        Byte 9: End Byte (0x01)
        """
        try:
            if len(packet) != 10:
                return None
            
            # Verify sync bytes
            if packet[0] != 0xC7 or packet[1] != 0x7C:
                return None
            
            # Verify end byte
            if packet[9] != 0x01:
                return None
            
            # Extract data
            counter = packet[2]
            ch0 = (packet[4] << 8) | packet[3]  # Little-endian
            ch1 = (packet[6] << 8) | packet[5]  # Little-endian
            
            return {
                'timestamp': datetime.now().isoformat(),
                'counter': counter,
                'channel_0': ch0,
                'channel_1': ch1,
                'unix_timestamp': time.time()
            }
        except Exception as e:
            self.error_occurred.emit(f"Parse error: {str(e)}")
            return None
    
    def read_data(self):
        """Read data from serial port in separate thread"""
        if not self.ser or not self.ser.is_open:
            self.error_occurred.emit("Serial port not open")
            return
        
        self.is_running = True
        self.packet_count = 0
        buffer = bytearray()
        self.status_changed.emit("Acquisition started...")
        
        try:
            while self.is_running:
                if self.ser.in_waiting > 0:
                    # Read available bytes
                    chunk = self.ser.read(self.ser.in_waiting)
                    buffer.extend(chunk)
                    
                    # Try to find complete packets
                    while len(buffer) >= 10:
                        # Find sync bytes
                        sync_index = -1
                        for i in range(len(buffer) - 1):
                            if buffer[i] == 0xC7 and buffer[i + 1] == 0x7C:
                                sync_index = i
                                break
                        
                        if sync_index == -1:
                            # No sync bytes found, discard buffer
                            buffer = bytearray()
                            break
                        
                        if sync_index > 0:
                            # Discard bytes before sync
                            buffer = buffer[sync_index:]
                        
                        if len(buffer) < 10:
                            break
                        
                        # Extract packet
                        packet = bytes(buffer[:10])
                        buffer = buffer[10:]
                        
                        # Parse packet
                        data = self.parse_packet(packet)
                        if data:
                            self.packet_count += 1
                            self.data_buffer.append(data)
                            self.data_received.emit(data)
                            self.packet_count_updated.emit(self.packet_count)
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
        
        except Exception as e:
            self.error_occurred.emit(f"Read error: {str(e)}")
        finally:
            self.is_running = False
            self.status_changed.emit("Acquisition stopped")


class EMGDataAcquisitionApp(QMainWindow):
    """Main GUI Application for EMG Data Acquisition"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.serial_thread = None
        self.session_data = []
        self.init_ui()
        self.refresh_ports()
        
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("EMG Data Acquisition System")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # ===== Serial Configuration Group =====
        config_group = QGroupBox("Serial Port Configuration")
        config_layout = QHBoxLayout()
        
        # Port selection
        config_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        config_layout.addWidget(self.port_combo)
        
        # Baud rate
        config_layout.addWidget(QLabel("Baud Rate:"))
        self.baud_spinbox = QSpinBox()
        self.baud_spinbox.setValue(230400)
        self.baud_spinbox.setMinimum(9600)
        self.baud_spinbox.setMaximum(921600)
        self.baud_spinbox.setSingleStep(9600)
        config_layout.addWidget(self.baud_spinbox)
        
        # Refresh ports button
        self.refresh_button = QPushButton("Refresh Ports")
        self.refresh_button.clicked.connect(self.refresh_ports)
        config_layout.addWidget(self.refresh_button)
        
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # ===== Control Buttons Group =====
        button_group = QGroupBox("Acquisition Controls")
        button_layout = QHBoxLayout()
        
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)
        self.connect_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.connect_button)
        
        # Start button
        self.start_button = QPushButton("Start Acquisition")
        self.start_button.clicked.connect(self.start_acquisition)
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("background-color: #008CBA; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.start_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop Acquisition")
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #FF6B6B; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.stop_button)
        
        # Disconnect button
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_serial)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.disconnect_button)
        
        # Save button
        self.save_button = QPushButton("Save Data")
        self.save_button.clicked.connect(self.save_data)
        self.save_button.setEnabled(False)
        self.save_button.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px;")
        button_layout.addWidget(self.save_button)
        
        button_group.setLayout(button_layout)
        main_layout.addWidget(button_group)
        
        # ===== Data Display Group =====
        display_group = QGroupBox("Real-Time Data Stream")
        display_layout = QVBoxLayout()
        
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.data_display.setFont(QFont("Courier", 9))
        self.data_display.setMaximumHeight(300)
        display_layout.addWidget(self.data_display)
        
        display_group.setLayout(display_layout)
        main_layout.addWidget(display_group)
        
        # ===== Statistics Group =====
        stats_group = QGroupBox("Acquisition Statistics")
        stats_layout = QHBoxLayout()
        
        # Packet count
        stats_layout.addWidget(QLabel("Packets Received:"))
        self.packet_label = QLabel("0")
        self.packet_label.setFont(QFont("Arial", 12, QFont.Bold))
        stats_layout.addWidget(self.packet_label)
        
        stats_layout.addSpacing(30)
        
        # Session samples
        stats_layout.addWidget(QLabel("Session Samples:"))
        self.sample_label = QLabel("0")
        self.sample_label.setFont(QFont("Arial", 12, QFont.Bold))
        stats_layout.addWidget(self.sample_label)
        
        stats_layout.addSpacing(30)
        
        # Data rate
        stats_layout.addWidget(QLabel("Data Rate:"))
        self.datarate_label = QLabel("0.0 KB/s")
        self.datarate_label.setFont(QFont("Arial", 12, QFont.Bold))
        stats_layout.addWidget(self.datarate_label)
        
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        main_layout.addWidget(stats_group)
        
        # Add status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready to connect")
        
        # Data rate timer
        self.data_rate_timer = QTimer()
        self.data_rate_timer.timeout.connect(self.update_data_rate)
        self.data_rate_bytes = 0
        
    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        
        if ports:
            for port in ports:
                self.port_combo.addItem(f"{port.device} - {port.description}")
        else:
            self.port_combo.addItem("No ports available")
            
    def connect_serial(self):
        """Connect to selected serial port"""
        if self.port_combo.count() == 0 or "No ports" in self.port_combo.currentText():
            QMessageBox.warning(self, "No Ports", "No serial ports available")
            return
        
        # Extract port name
        port = self.port_combo.currentText().split(" - ")[0]
        baudrate = self.baud_spinbox.value()
        
        # Create worker and thread
        self.worker = SerialWorker()
        self.serial_thread = QThread()
        self.worker.moveToThread(self.serial_thread)
        
        # Connect signals
        self.worker.data_received.connect(self.on_data_received)
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.packet_count_updated.connect(self.on_packet_count_updated)
        
        # Try to connect
        if self.worker.connect_port(port, baudrate):
            self.start_button.setEnabled(True)
            self.disconnect_button.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.baud_spinbox.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.connect_button.setEnabled(False)
            self.statusBar.showMessage(f"Connected to {port}")
        else:
            QMessageBox.critical(self, "Connection Error", 
                                f"Failed to connect to {port}")
    
    def disconnect_serial(self):
        """Disconnect from serial port"""
        self.stop_acquisition()
        
        if self.worker:
            self.worker.disconnect_port()
        
        self.port_combo.setEnabled(True)
        self.baud_spinbox.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(False)
        
        self.statusBar.showMessage("Disconnected")
        self.data_display.clear()
        
    def start_acquisition(self):
        """Start data acquisition"""
        if not self.worker or not self.worker.ser or not self.worker.ser.is_open:
            QMessageBox.warning(self, "Not Connected", "Please connect to a port first")
            return
        
        self.session_data = []
        self.worker.data_buffer = []
        self.data_display.clear()
        
        # Start reading thread
        self.serial_thread.started.connect(self.worker.read_data)
        self.serial_thread.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.port_combo.setEnabled(False)
        self.connect_button.setEnabled(False)
        
        self.data_rate_timer.start(1000)  # Update data rate every second
        self.statusBar.showMessage("Acquisition running...")
    
    def stop_acquisition(self):
        """Stop data acquisition"""
        if self.worker:
            self.worker.is_running = False
        
        if self.serial_thread:
            self.serial_thread.quit()
            self.serial_thread.wait()
            self.serial_thread = None
        
        self.data_rate_timer.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.connect_button.setEnabled(False)
        
        if self.worker:
            self.session_data = self.worker.data_buffer.copy()
        
        self.statusBar.showMessage("Acquisition stopped")
    
    def on_data_received(self, data):
        """Handle received data packet"""
        self.data_rate_bytes += 10  # 10-byte packet
        
        # Display latest packet
        display_text = (
            f"[{data['timestamp']}] "
            f"Counter: {data['counter']:3d} | "
            f"Ch0 (Flexor): {data['channel_0']:5d} | "
            f"Ch1 (Extensor): {data['channel_1']:5d}"
        )
        
        # Keep only last 50 lines
        current_text = self.data_display.toPlainText()
        lines = current_text.split('\n')
        if len(lines) > 50:
            lines = lines[-50:]
        lines.append(display_text)
        self.data_display.setPlainText('\n'.join(lines))
        
        # Auto-scroll to bottom
        self.data_display.verticalScrollBar().setValue(
            self.data_display.verticalScrollBar().maximum()
        )
        
        self.sample_label.setText(str(len(self.worker.data_buffer)))
    
    def on_packet_count_updated(self, count):
        """Update packet count display"""
        self.packet_label.setText(str(count))
    
    def on_status_changed(self, message):
        """Handle status changes"""
        self.statusBar.showMessage(message)
    
    def on_error(self, error):
        """Handle errors"""
        QMessageBox.critical(self, "Error", error)
    
    def update_data_rate(self):
        """Update data rate display"""
        data_rate_kbs = (self.data_rate_bytes / 1024)  # KB/s
        self.datarate_label.setText(f"{data_rate_kbs:.2f} KB/s")
        self.data_rate_bytes = 0  # Reset for next second
    
    def save_data(self):
        """Save collected data to JSON file"""
        if not self.session_data:
            QMessageBox.warning(self, "No Data", "No data to save")
            return
        
        # File dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save EMG Data",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Add metadata
            save_data = {
                'metadata': {
                    'session_start': self.session_data[0]['timestamp'] if self.session_data else '',
                    'session_end': self.session_data[-1]['timestamp'] if self.session_data else '',
                    'total_samples': len(self.session_data),
                    'sampling_rate': 512,  # Hz
                    'channels': 2,
                    'channel_0': 'Forearm Flexor (A0)',
                    'channel_1': 'Forearm Extensor (A1)',
                    'hardware': 'Arduino Uno R4',
                    'packet_format': '10 bytes (sync + counter + 2x16-bit ADC + end)'
                },
                'data': self.session_data
            }
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            QMessageBox.information(
                self,
                "Success",
                f"Data saved successfully to:\n{file_path}\n\nTotal samples: {len(self.session_data)}"
            )
            
            self.statusBar.showMessage(f"Data saved to {file_path}")
        
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save data: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.worker and self.worker.ser and self.worker.ser.is_open:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Serial port is still open. Close it?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.stop_acquisition()
                self.worker.disconnect_port()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    window = EMGDataAcquisitionApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()