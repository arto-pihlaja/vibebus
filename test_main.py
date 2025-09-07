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
    
    def test_format_time_response_success(self):
        """Test format_time_response with valid time data"""
        time_data = {
            'current_time': '14:35:22',
            'current_date': '2025-01-09',
            'weekday': 'Thursday',
            'timezone': 'Europe/Helsinki'
        }
        
        expected_response = (
            "🕐 Current Time in Helsinki:\n"
            "Time: 14:35:22\n"
            "Date: 2025-01-09\n"
            "Day: Thursday\n"
            "Timezone: Europe/Helsinki"
        )
        
        result = self.chat.format_time_response(time_data)
        self.assertEqual(result, expected_response)
    
    def test_format_time_response_with_error(self):
        """Test format_time_response when error is present in data"""
        time_data = {"error": "Time API error: Connection failed"}
        
        expected_response = "Sorry, I couldn't get the current time: Time API error: Connection failed"
        
        result = self.chat.format_time_response(time_data)
        self.assertEqual(result, expected_response)
    
    def test_format_time_response_missing_fields(self):
        """Test format_time_response with missing fields (using N/A defaults)"""
        time_data = {
            'current_time': '14:35:22',
            # Missing date, weekday, timezone
        }
        
        expected_response = (
            "🕐 Current Time in Helsinki:\n"
            "Time: 14:35:22\n"
            "Date: N/A\n"
            "Day: N/A\n"
            "Timezone: N/A"
        )
        
        result = self.chat.format_time_response(time_data)
        self.assertEqual(result, expected_response)
    
    def test_format_time_response_empty_data(self):
        """Test format_time_response with empty data dictionary"""
        time_data = {}
        
        expected_response = (
            "🕐 Current Time in Helsinki:\n"
            "Time: N/A\n"
            "Date: N/A\n"
            "Day: N/A\n"
            "Timezone: N/A"
        )
        
        result = self.chat.format_time_response(time_data)
        self.assertEqual(result, expected_response)
    
    def test_format_time_response_invalid_data_type(self):
        """Test format_time_response with invalid data type (should raise exception handled by try-catch)"""
        time_data = "invalid_data_type"
        
        result = self.chat.format_time_response(time_data)
        self.assertTrue(result.startswith("Sorry, I couldn't parse the time data properly:"))
        self.assertIn("'str' object has no attribute 'get'", result)


if __name__ == '__main__':
    unittest.main()