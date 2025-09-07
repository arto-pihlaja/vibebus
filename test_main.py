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
        self.assertEqual(len(self.chat.tools), 5)
        
        # Check tool names
        tool_names = [tool['function']['name'] for tool in self.chat.tools]
        expected_names = ['get_weather', 'get_next_departures', 'get_current_time', 'get_stops_by_name', 'get_stop_id_from_selection']
        
        for name in expected_names:
            self.assertIn(name, tool_names)
    
    def test_conversation_max_length_default(self):
        """Test that conversationMaxLength has correct default value"""
        self.assertEqual(self.chat.conversationMaxLength, 100)
    
    def test_conversation_max_length_custom(self):
        """Test that conversationMaxLength can be set to custom value"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            chat = VibebusChat(conversation_max_length=50)
            self.assertEqual(chat.conversationMaxLength, 50)
    
    def test_trim_conversation_no_trim_needed(self):
        """Test _trim_conversation when no trimming is needed"""
        # Add a few messages below the max length
        self.chat.conversation = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant message 1"}
        ]
        
        original_length = len(self.chat.conversation)
        self.chat._trim_conversation()
        
        # Should remain unchanged
        self.assertEqual(len(self.chat.conversation), original_length)
        self.assertEqual(self.chat.conversation[0]["role"], "system")
    
    def test_trim_conversation_with_system_message(self):
        """Test _trim_conversation preserves system message"""
        # Set small max length for testing
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            chat = VibebusChat(conversation_max_length=3)
        
        # Add more messages than max length
        chat.conversation = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant message 1"},
            {"role": "user", "content": "User message 2"},
            {"role": "assistant", "content": "Assistant message 2"}
        ]
        
        chat._trim_conversation()
        
        # Should keep system message + last 2 messages
        self.assertEqual(len(chat.conversation), 3)
        self.assertEqual(chat.conversation[0]["role"], "system")
        self.assertEqual(chat.conversation[0]["content"], "System message")
        self.assertEqual(chat.conversation[1]["content"], "User message 2")
        self.assertEqual(chat.conversation[2]["content"], "Assistant message 2")
    
    def test_trim_conversation_without_system_message(self):
        """Test _trim_conversation when no system message exists"""
        # Set small max length for testing
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            chat = VibebusChat(conversation_max_length=2)
        
        # Add messages without system message
        chat.conversation = [
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant message 1"},
            {"role": "user", "content": "User message 2"},
            {"role": "assistant", "content": "Assistant message 2"}
        ]
        
        chat._trim_conversation()
        
        # Should keep last 2 messages
        self.assertEqual(len(chat.conversation), 2)
        self.assertEqual(chat.conversation[0]["content"], "User message 2")
        self.assertEqual(chat.conversation[1]["content"], "Assistant message 2")
    
    def test_trim_conversation_exactly_at_limit(self):
        """Test _trim_conversation when conversation is exactly at limit"""
        # Set max length for testing
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
            chat = VibebusChat(conversation_max_length=3)
        
        # Add exactly max length messages
        chat.conversation = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant message"}
        ]
        
        original_conversation = chat.conversation.copy()
        chat._trim_conversation()
        
        # Should remain unchanged
        self.assertEqual(chat.conversation, original_conversation)
    
    def test_format_weather_response_success(self):
        """Test format_weather_response with valid weather data"""
        weather_data = {
            'current': {
                'temperature_2m': 15.2,
                'wind_speed_10m': 3.5,
                'precipitation': 0.0
            },
            'daily': {
                'temperature_2m_max': [18.5],
                'temperature_2m_min': [12.0]
            }
        }
        
        result = self.chat.format_weather_response(weather_data)
        
        self.assertIn("🌤️ Current Weather in Helsinki:", result)
        self.assertIn("Temperature: 15.2°C", result)
        self.assertIn("Wind Speed: 3.5 m/s", result)
        self.assertIn("Precipitation: 0.0 mm", result)
        self.assertIn("Today's Range: 12.0°C - 18.5°C", result)
    
    def test_format_weather_response_with_error(self):
        """Test format_weather_response when error is present in data"""
        weather_data = {"error": "Weather API error: Connection failed"}
        
        expected_response = "Sorry, I couldn't get the weather information: Weather API error: Connection failed"
        
        result = self.chat.format_weather_response(weather_data)
        self.assertEqual(result, expected_response)
    
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
    
    def test_format_bus_response_success(self):
        """Test format_bus_response with valid bus data"""
        bus_data = {
            'data': {
                'stop': {
                    'name': 'Test Bus Stop',
                    'stoptimesWithoutPatterns': [
                        {
                            'realtimeDeparture': 54000,  # 15:00 in seconds since midnight
                            'serviceDay': 1641859200,    # Mock service day
                            'realtime': True,
                            'headsign': 'Central Station',
                            'trip': {
                                'route': {
                                    'shortName': '55'
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        result = self.chat.format_bus_response(bus_data, "HSL:1234")
        
        self.assertIn("🚌 Next Departures from Test Bus Stop:", result)
        self.assertIn("Bus 55 → Central Station", result)
        self.assertIn("🟢", result)  # Realtime indicator
    
    def test_format_bus_response_with_error(self):
        """Test format_bus_response when error is present in data"""
        bus_data = {"error": "Bus API error: Connection failed"}
        
        expected_response = "Sorry, I couldn't get the bus departure information: Bus API error: Connection failed"
        
        result = self.chat.format_bus_response(bus_data, "HSL:1234")
        self.assertEqual(result, expected_response)
    
    def test_format_bus_response_no_departures(self):
        """Test format_bus_response when no departures are found"""
        bus_data = {
            'data': {
                'stop': {
                    'name': 'Empty Bus Stop',
                    'stoptimesWithoutPatterns': []
                }
            }
        }
        
        expected_response = "🚌 No upcoming departures found for Empty Bus Stop"
        
        result = self.chat.format_bus_response(bus_data, "HSL:1234")
        self.assertEqual(result, expected_response)
    
    def test_get_stops_by_name_missing_api_key(self):
        """Test get_stops_by_name without API key"""
        with patch.dict('os.environ', {}, clear=True):
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'}):
                result = self.chat.get_stops_by_name("hertton")
                
                # Should return error about missing API key
                self.assertIn('error', result)
                self.assertIn('DIGITRANSIT_API_KEY not found', result['error'])
    
    def test_get_stops_by_name_success(self):
        """Test get_stops_by_name with successful API response"""
        # Mock the API call to avoid actual network request
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": {
                    "stops": [
                        {
                            "gtfsId": "HSL:1234567",
                            "name": "Herttonemi",
                            "code": "H1234",
                            "lat": 60.1850,
                            "lon": 25.0317
                        }
                    ]
                }
            }
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            with patch.dict('os.environ', {'DIGITRANSIT_API_KEY': 'test_key'}):
                result = self.chat.get_stops_by_name("hertton")
                
                # Should not return error
                self.assertNotIn('error', result)
                self.assertIn('data', result)
                self.assertIn('stops', result['data'])
    
    def test_format_stops_response_success(self):
        """Test format_stops_response with valid stops data"""
        stops_data = {
            'data': {
                'stops': [
                    {
                        'gtfsId': 'HSL:1234567',
                        'name': 'Herttonemi',
                        'code': 'H1234',
                        'lat': 60.1850,
                        'lon': 25.0317
                    },
                    {
                        'gtfsId': 'HSL:7654321',
                        'name': 'Herttonemi asema',
                        'code': 'H5678',
                        'lat': 60.1860,
                        'lon': 25.0327
                    }
                ]
            }
        }
        
        result = self.chat.format_stops_response(stops_data, "hertton")
        
        self.assertIn("🚏 Found 2 stops matching 'hertton'. Which one do you mean?", result)
        self.assertIn("1. Herttonemi H1234 (ID: HSL:1234567)", result)
        self.assertIn("2. Herttonemi asema H5678 (ID: HSL:7654321)", result)
    
    def test_format_stops_response_with_error(self):
        """Test format_stops_response when error is present in data"""
        stops_data = {"error": "Stops API error: Connection failed"}
        
        expected_response = "Sorry, I couldn't search for stops: Stops API error: Connection failed"
        
        result = self.chat.format_stops_response(stops_data, "hertton")
        self.assertEqual(result, expected_response)
    
    def test_format_stops_response_no_results(self):
        """Test format_stops_response when no stops are found"""
        stops_data = {
            'data': {
                'stops': []
            }
        }
        
        expected_response = "🚏 No stops found matching 'nonexistent'"
        
        result = self.chat.format_stops_response(stops_data, "nonexistent")
        self.assertEqual(result, expected_response)
    
    def test_format_stops_response_single_result(self):
        """Test format_stops_response when only one stop is found"""
        stops_data = {
            'data': {
                'stops': [
                    {
                        'gtfsId': 'HSL:1234567',
                        'name': 'Herttonemi',
                        'code': 'H1234',
                        'lat': 60.1850,
                        'lon': 25.0317
                    }
                ]
            }
        }
        
        result = self.chat.format_stops_response(stops_data, "hertton")
        
        self.assertIn("🚏 Found: Herttonemi", result)
        self.assertIn("ID: HSL:1234567", result)
        self.assertIn("Code: H1234", result)
        self.assertIn("Location: 60.185, 25.0317", result)
    
    def test_get_stop_id_from_selection_valid(self):
        """Test get_stop_id_from_selection with valid selection"""
        # First populate the search results
        self.chat.last_stop_search_results = [
            {'gtfsId': 'HSL:1234567', 'name': 'Stop A'},
            {'gtfsId': 'HSL:7654321', 'name': 'Stop B'},
            {'gtfsId': 'HSL:9999999', 'name': 'Stop C'}
        ]
        
        # Test valid selections
        self.assertEqual(self.chat.get_stop_id_from_selection("1"), "HSL:1234567")
        self.assertEqual(self.chat.get_stop_id_from_selection("2"), "HSL:7654321")
        self.assertEqual(self.chat.get_stop_id_from_selection("3"), "HSL:9999999")
        self.assertEqual(self.chat.get_stop_id_from_selection(" 2 "), "HSL:7654321")  # With spaces
    
    def test_get_stop_id_from_selection_invalid(self):
        """Test get_stop_id_from_selection with invalid selections"""
        # First populate the search results
        self.chat.last_stop_search_results = [
            {'gtfsId': 'HSL:1234567', 'name': 'Stop A'},
            {'gtfsId': 'HSL:7654321', 'name': 'Stop B'}
        ]
        
        # Test invalid selections
        self.assertEqual(self.chat.get_stop_id_from_selection("0"), "")  # Below range
        self.assertEqual(self.chat.get_stop_id_from_selection("3"), "")  # Above range
        self.assertEqual(self.chat.get_stop_id_from_selection("abc"), "")  # Non-numeric
        self.assertEqual(self.chat.get_stop_id_from_selection(""), "")  # Empty
    
    def test_get_stop_id_from_selection_no_results(self):
        """Test get_stop_id_from_selection when no previous search results"""
        self.chat.last_stop_search_results = []
        self.assertEqual(self.chat.get_stop_id_from_selection("1"), "")
    
    def test_format_stops_response_stores_results(self):
        """Test that format_stops_response stores results in last_stop_search_results"""
        stops_data = {
            'data': {
                'stops': [
                    {
                        'gtfsId': 'HSL:1234567',
                        'name': 'Herttonemi',
                        'code': 'H1234',
                        'lat': 60.1850,
                        'lon': 25.0317
                    }
                ]
            }
        }
        
        self.chat.format_stops_response(stops_data, "hertton")
        
        # Check that results were stored
        self.assertEqual(len(self.chat.last_stop_search_results), 1)
        self.assertEqual(self.chat.last_stop_search_results[0]['gtfsId'], 'HSL:1234567')
        self.assertEqual(self.chat.last_stop_search_results[0]['name'], 'Herttonemi')


if __name__ == '__main__':
    unittest.main()