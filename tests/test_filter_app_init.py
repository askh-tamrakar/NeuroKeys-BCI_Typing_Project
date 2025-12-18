import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(project_root, 'src'))

# Mock dependencies before importing
# Mock dependencies before importing
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()

# Configure matplotlib Mocks to handle plot unpacking
mock_mpl = MagicMock()
mock_fig = MagicMock()
mock_ax = MagicMock()
mock_line = MagicMock()
# When plot is called, return a list containing one mock line
mock_ax.plot.return_value = [mock_line]
mock_fig.add_subplot.return_value = mock_ax

sys.modules['matplotlib'] = mock_mpl
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
# Ensure Figure constructor returns our mock_fig
sys.modules['matplotlib.figure'] = MagicMock()
sys.modules['matplotlib.figure'].Figure.return_value = mock_fig

# Mock chords module if not found
try:
    import chords.chords_serial
except ImportError:
    # If imports fail in test env, mock it completely
    chords_mock = MagicMock()
    sys.modules['chords'] = chords_mock
    sys.modules['chords.chords_serial'] = chords_mock

from processing.filter_app import EMGFilterApp

class TestFilterApp(unittest.TestCase):
    @patch('processing.filter_app.Chords_USB')
    def test_init(self, MockChords):
        """Test that the app initializes without crashing."""
        root = MagicMock()
        app = EMGFilterApp(root)
        self.assertIsNotNone(app)
        self.assertTrue(hasattr(app, 'usb_client'))
        print("EMGFilterApp initialized successfully.")

if __name__ == '__main__':
    unittest.main()
