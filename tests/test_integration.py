import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

# Add src to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(project_root, 'src'))

# Mock hardware dependencies
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()

# Configure matplotlib mocks
mock_mpl = MagicMock()
mock_fig = MagicMock()
mock_ax = MagicMock()
mock_line = MagicMock()
mock_ax.plot.return_value = [mock_line]
mock_fig.add_subplot.return_value = mock_ax
sys.modules['matplotlib'] = mock_mpl
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
sys.modules['matplotlib.figure'] = MagicMock()
sys.modules['matplotlib.figure'].Figure.return_value = mock_fig

from acquisition.acquisition import EMGAcquisitionApp

class TestIntegration(unittest.TestCase):
    def test_filter_btn_creates_window(self):
        root = tk.Tk()
        app = EMGAcquisitionApp(root)
        
        # Initial state
        self.assertIsNone(app.filter_window)
        
        # Click button (simulate)
        app.toggle_filter_window()
        
        # Check window created
        self.assertIsNotNone(app.filter_window)
        self.assertTrue(app.filter_window.winfo_exists())
        
        # Simulate data packet
        packet = b'\xC7\x7C\x01\x00\x00\x01\x00\x01' # Mock packet
        # Manually call parse
        # data_entry construction in parse_and_store_packet uses indexing
        # We'll just verify the method update_data exists on the window
        self.assertTrue(hasattr(app.filter_window, 'update_data'))
        
        # Cleanup
        app.filter_window.destroy()
        root.destroy()

if __name__ == '__main__':
    unittest.main()
