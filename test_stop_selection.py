#!/usr/bin/env python3
"""
Test for the stop selection flow fix
"""

import unittest
from unittest.mock import patch, MagicMock
from main import VibebusChat


class TestStopSelectionFlow(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.chat = VibebusChat()
        
        # Mock search results
        self.mock_stops = [
            {'gtfsId': 'HSL:1234567', 'name': 'Test Stop 1', 'code': 'E1234'},
            {'gtfsId': 'HSL:7654321', 'name': 'Test Stop 2', 'code': 'E5678'}
        ]
        self.chat.last_stop_search_results = self.mock_stops
    
    def test_numeric_selection_detection(self):
        """Test that numeric selections are detected correctly"""
        # Valid selections
        self.assertTrue(self._is_numeric_selection("1"))
        self.assertTrue(self._is_numeric_selection("2"))
        self.assertTrue(self._is_numeric_selection(" 1 "))  # With whitespace
        
        # Invalid selections
        self.assertFalse(self._is_numeric_selection("3"))  # Out of range
        self.assertFalse(self._is_numeric_selection("0"))  # Out of range
        self.assertFalse(self._is_numeric_selection("hello"))  # Non-numeric
        self.assertFalse(self._is_numeric_selection(""))  # Empty
        
        # Test with no search results
        self.chat.last_stop_search_results = []
        self.assertFalse(self._is_numeric_selection("1"))
    
    def _is_numeric_selection(self, message):
        """Helper method that mimics the logic in send_message"""
        return (self.chat.last_stop_search_results and 
                message.strip().isdigit() and 
                1 <= int(message.strip()) <= len(self.chat.last_stop_search_results))
    
    def test_get_stop_id_from_selection(self):
        """Test getting stop ID from selection"""
        self.assertEqual(self.chat.get_stop_id_from_selection("1"), "HSL:1234567")
        self.assertEqual(self.chat.get_stop_id_from_selection("2"), "HSL:7654321")
        self.assertEqual(self.chat.get_stop_id_from_selection("3"), "")  # Invalid
        self.assertEqual(self.chat.get_stop_id_from_selection("invalid"), "")  # Non-numeric
    
    @patch('main.VibebusChat.get_next_departures')
    @patch('main.VibebusChat.format_bus_response')
    def test_send_message_with_numeric_selection(self, mock_format, mock_departures):
        """Test that send_message handles numeric selections directly"""
        # Mock the departure API response
        mock_departures.return_value = {"data": {"stop": {"name": "Test Stop", "stoptimesWithoutPatterns": []}}}
        mock_format.return_value = "🚌 Next Departures from Test Stop:\n\nNo upcoming departures found"
        
        # Send numeric selection
        result = self.chat.send_message("1")
        
        # Verify the response
        self.assertIn("🚌 Next Departures", result)
        
        # Verify that get_next_departures was called with correct stop ID
        mock_departures.assert_called_once_with("HSL:1234567")
        
        # Verify that search results were cleared
        self.assertEqual(self.chat.last_stop_search_results, [])
        
        # Verify conversation history was updated
        self.assertEqual(len(self.chat.conversation), 3)  # System + User + Assistant
        self.assertEqual(self.chat.conversation[-2]["role"], "user")
        self.assertEqual(self.chat.conversation[-2]["content"], "1")
        self.assertEqual(self.chat.conversation[-1]["role"], "assistant")
    
    def test_send_message_non_numeric_goes_to_llm(self):
        """Test that non-numeric messages still go to the LLM"""
        # Mock the OpenAI client response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello there!"
        mock_response.choices[0].message.tool_calls = None
        
        # Replace the client with a mock
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        self.chat.client = mock_client
        
        # Send non-numeric message
        result = self.chat.send_message("hello")
        
        # Verify LLM was called
        mock_client.chat.completions.create.assert_called()
        
        # Verify search results were not cleared
        self.assertEqual(self.chat.last_stop_search_results, self.mock_stops)


if __name__ == '__main__':
    unittest.main()