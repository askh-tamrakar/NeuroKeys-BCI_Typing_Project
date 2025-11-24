import serial.tools.list_ports
print([port.device for port in serial.tools.list_ports.comports()])
