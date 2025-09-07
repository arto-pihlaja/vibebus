#!/usr/bin/env python3
"""
Unit tests for VibebusChat class
"""

import unittest
from unittest.mock import patch, MagicMock
from main import VibebusChat


class TestVibebusChat(unittest.TestCase):
    """Test cases for VibebusChat class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Mock environment variables to avoid API key requirements
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            self.chat = VibebusChat()
    
    def test_get_current_time_success(self):
        """Test get_current_time returns expected data structure"""
        result = self.chat.get_current_time()
        
        # Check that all expected keys are present
        expected_keys = ['current_time', 'current_date', 'weekday', 'timezone']
        for key in expected_keys:
            self.assertIn(key, result)
        
        # Check that values are strings and not empty
        for key in expected_keys:
            self.assertIsInstance(result[key], str)
            self.assertNotEqual(result[key], '')
        
        # Check timezone is Helsinki
        self.assertEqual(result['timezone'], 'Europe/Helsinki')
    
    def test_get_next_departures_default_stop(self):
        """Test get_next_departures with default stop ID"""
        # Mock the API call to avoid actual network request
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": {"stop": {"name": "Test Stop"}}}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            with patch.dict('os.environ', {'DIGITRANSIT_API_KEY': 'test_key'}):
                result = self.chat.get_next_departures()
                
                # Should not return error
                self.assertNotIn('error', result)
    
    def test_get_next_departures_missing_api_key(self):
        """Test get_next_departures without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
                result = self.chat.get_next_departures()
                
                # Should return error about missing API key
                self.assertIn('error', result)
                self.assertIn('DIGITRANSIT_API_KEY not found', result['error'])
    
    def test_tools_configuration(self):
        """Test that tools are properly configured"""
        self.assertEqual(len(self.chat.tools), 3)
        
        # Check tool names
        tool_names = [tool['function']['name'] for tool in self.chat.tools]
        expected_names = ['get_weather', 'get_next_departures', 'get_current_time']
        
        for name in expected_names:
            self.assertIn(name, tool_names)


if __name__ == '__main__':
    unittest.main()