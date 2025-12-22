import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import numpy as np
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Mock pylsl before importing FilterRouter
sys.modules['pylsl'] = MagicMock()

from src.processing.filter_router import FilterRouter, parse_channel_map
from src.processing.emg_processor import EMGFilterProcessor
from src.processing.eog_processor import EOGFilterProcessor
from src.processing.eeg_processor import EEGFilterProcessor

class TestFilterRouter(unittest.TestCase):

    def setUp(self):
        # Default config content
        self.config_data = {
            "sampling_rate": 512,
            "channel_mapping": {
                "ch0": {"sensor": "EMG", "enabled": True},
                "ch1": {"sensor": "EOG", "enabled": True}
            },
            "filters": {
                "EMG": {"cutoff": 70.0, "order": 4},
                "EOG": {"cutoff": 10.0, "order": 4},
                "EEG": {}
            }
        }
    
    @patch('src.processing.filter_router.load_config')
    def test_initialization(self, mock_load):
        mock_load.return_value = self.config_data
        router = FilterRouter()
        self.assertEqual(router.sr, 512)
        self.assertEqual(router.config, self.config_data)

    def test_parse_channel_map(self):
        # Mock LSL StreamInfo
        mock_info = MagicMock()
        mock_info.channel_count.return_value = 2
        mock_ch = MagicMock()
        
        # Simulating children iteration is complex with MagicMock for XML, 
        # so we mostly test the fallback or basic structure if possible.
        # Here we rely on the fallback list comprehension in the function 
        # if XML parsing fails or returns empty.
        
        # Test Fallback
        mock_info.desc().child().empty.return_value = True
        mapping = parse_channel_map(mock_info)
        self.assertEqual(len(mapping), 2)
        self.assertEqual(mapping[0], (0, 'ch0', 'ch0'))

    @patch('src.processing.filter_router.load_config')
    def test_configure_pipeline_correct_mapping(self, mock_load):
        mock_load.return_value = self.config_data
        router = FilterRouter()
        
        # Manually set raw_index_map as if stream was resolved
        router.raw_index_map = [
            (0, 'ch0', 'type0'),
            (1, 'ch1', 'type1')
        ]
        
        router._configure_pipeline()
        
        # Check if processors are created according to config "ch0"->EMG, "ch1"->EOG
        self.assertIn(0, router.channel_processors)
        self.assertIn(1, router.channel_processors)
        
        self.assertIsInstance(router.channel_processors[0], EMGFilterProcessor)
        self.assertIsInstance(router.channel_processors[1], EOGFilterProcessor)
        
        # Check Mapping
        self.assertEqual(router.channel_mapping[0]['sensor'], 'EMG')
        self.assertEqual(router.channel_mapping[1]['sensor'], 'EOG')

    @patch('src.processing.filter_router.load_config')
    def test_configure_pipeline_disabled_channel(self, mock_load):
        config_disabled = self.config_data.copy()
        config_disabled["channel_mapping"]["ch0"]["enabled"] = False
        mock_load.return_value = config_disabled
        
        router = FilterRouter()
        router.raw_index_map = [(0, 'ch0', 'type0')]
        
        router._configure_pipeline()
        
        # Disabled channel should have None processor
        self.assertIsNone(router.channel_processors[0])
        self.assertEqual(router.channel_mapping[0]['enabled'], False)

    @patch('src.processing.filter_router.load_config')
    def test_process_logic(self, mock_load):
        """Test the logic that would happen inside the run loop"""
        mock_load.return_value = self.config_data
        router = FilterRouter()
        router.raw_index_map = [(0, 'ch0', 'type0')]
        router._configure_pipeline()
        
        processor = router.channel_processors[0]
        self.assertIsNotNone(processor)
        
        # Mock the processor's process_sample method
        processor.process_sample = MagicMock(return_value=123.45)
        
        # Simulate one loop iteration logic
        raw_sample = [10.0]
        processed_sample = []
        
        for ch_idx in range(router.num_channels):
            raw_val = raw_sample[ch_idx]
            proc = router.channel_processors.get(ch_idx)
            if proc:
                val = proc.process_sample(raw_val)
            else:
                val = raw_val
            processed_sample.append(val)
            
        self.assertEqual(processed_sample[0], 123.45)
        processor.process_sample.assert_called_with(10.0)

if __name__ == '__main__':
    unittest.main()
