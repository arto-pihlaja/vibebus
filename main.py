#!/usr/bin/env python3
"""
Vibebus - A minimalistic CLI chat agent using OpenRouter
"""

import os
import sys
import argparse
import json
import re
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

class VibebusChat:
    def __init__(self, model: str = None):
        """Initialize the chat agent with OpenRouter client"""
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        self.model = model or os.getenv("DEFAULT_MODEL", "openai/gpt-4o")
        self.conversation: List[Dict[str, str]] = []
        
        # Add system message with tool information
        self.conversation.append({
            "role": "system",
            "content": "You are a helpful assistant with access to weather information, bus departure times, and current time. When a user asks for weather 'here' or for the current weather, you should call the get_weather function. When a user asks for bus departure times or next departures, you should call the get_next_departures function. When a user asks for the current time, you should call the get_current_time function. After calling functions, provide a friendly summary of the information."
        })
        
    def get_weather(self) -> dict:
        """Get weather data from Open-Meteo API"""
        url = "https://api.open-meteo.com/v1/forecast?latitude=60.1850&longitude=25.0317&current=temperature_2m,wind_speed_10m,precipitation,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Weather API error: {str(e)}"}
    
    def get_next_departures(self, stop_id: str) -> dict:
        """Get next departure times for a bus stop using GraphQL API"""
        url = "https://api.digitransit.fi/routing/v2/hsl/gtfs/v1"
        
        # Get API key from environment
        api_key = os.getenv("DIGITRANSIT_API_KEY")
        if not api_key:
            return {"error": "DIGITRANSIT_API_KEY not found in environment variables"}
        
        # GraphQL query based on documentation
        query = """
        query GetStopDepartures($stopId: String!, $timeRange: Int!) {
            stop(id: $stopId) {
                name
                stoptimesWithoutPatterns(timeRange: $timeRange) {
                    scheduledArrival
                    realtimeArrival
                    arrivalDelay
                    scheduledDeparture
                    realtimeDeparture
                    departureDelay
                    realtime
                    realtimeState
                    serviceDay
                    headsign
                    trip {
                        route {
                            shortName
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "stopId": stop_id,
            "timeRange": 3600  # 1 hour as specified in docs
        }
        
        headers = {
            "Content-Type": "application/json",
            "digitransit-subscription-key": api_key
        }
        
        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Bus API error: {str(e)}"}
    
    def get_current_time(self) -> dict:
        """Get current time in Helsinki timezone"""
        try:
            import datetime
            import zoneinfo
            
            # Get current time in Helsinki timezone
            helsinki_tz = zoneinfo.ZoneInfo("Europe/Helsinki")
            current_time = datetime.datetime.now(helsinki_tz)
            
            return {
                "current_time": current_time.strftime("%H:%M:%S"),
                "current_date": current_time.strftime("%Y-%m-%d"),
                "weekday": current_time.strftime("%A"),
                "timezone": "Europe/Helsinki"
            }
        except Exception as e:
            return {"error": f"Time error: {str(e)}"}
    
    def check_weather_request(self, message: str) -> bool:
        """Check if the user is asking for weather information"""
        weather_keywords = [
            r'weather\s+here',
            r'current\s+weather',
            r'what.*weather.*like',
            r'how.*weather',
            r'temperature\s+here',
            r'weather\s+now'
        ]
        
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in weather_keywords)
    
    def check_bus_request(self, message: str) -> bool:
        """Check if the user is asking for bus departure information"""
        bus_keywords = [
            r'bus.*departure',
            r'next.*bus',
            r'bus.*time',
            r'departure.*time',
            r'when.*bus',
            r'bus.*stop',
            r'next.*departure'
        ]
        
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in bus_keywords)
    
    def extract_stop_id(self, message: str) -> str:
        """Extract stop ID from user message - placeholder implementation"""
        # TODO: Implement stop ID extraction logic
        # For now, return a default stop ID or extract from message
        import re
        
        # Look for patterns like "stop 1234" or "stop id 1234"
        stop_match = re.search(r'stop(?:\s+id)?\s+(\w+)', message.lower())
        if stop_match:
            return stop_match.group(1)
        
        # Default stop ID for testing - using documented valid example
        return "HSL:1434183"
    
    def check_time_request(self, message: str) -> bool:
        """Check if the user is asking for current time"""
        time_keywords = [
            r'current\s+time',
            r'what\s+time',
            r'time\s+now',
            r'time\s+is\s+it',
            r'what.*time.*it',
            r'show.*time',
            r'get.*time'
        ]
        
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in time_keywords)
    
    def format_weather_response(self, weather_data: dict) -> str:
        """Format weather data into a readable response"""
        if "error" in weather_data:
            return f"Sorry, I couldn't get the weather information: {weather_data['error']}"
        
        try:
            current = weather_data.get('current', {})
            daily = weather_data.get('daily', {})
            
            temp = current.get('temperature_2m', 'N/A')
            wind = current.get('wind_speed_10m', 'N/A')
            precipitation = current.get('precipitation', 'N/A')
            
            response = f"🌤️ Current Weather in Helsinki:\n"
            response += f"Temperature: {temp}°C\n"
            response += f"Wind Speed: {wind} m/s\n"
            response += f"Precipitation: {precipitation} mm\n"
            
            if daily and 'temperature_2m_max' in daily and daily['temperature_2m_max']:
                max_temp = daily['temperature_2m_max'][0] if daily['temperature_2m_max'] else 'N/A'
                min_temp = daily['temperature_2m_min'][0] if daily['temperature_2m_min'] else 'N/A'
                response += f"Today's Range: {min_temp}°C - {max_temp}°C"
            
            return response
            
        except (KeyError, IndexError, TypeError) as e:
            return f"Sorry, I couldn't parse the weather data properly: {str(e)}"
    
    def format_bus_response(self, bus_data: dict, stop_id: str) -> str:
        """Format bus departure data into a readable response"""
        if "error" in bus_data:
            return f"Sorry, I couldn't get the bus departure information: {bus_data['error']}"
        
        try:
            data = bus_data.get('data', {})
            stop = data.get('stop', {})
            stop_name = stop.get('name', f'Stop {stop_id}')
            departures = stop.get('stoptimesWithoutPatterns', [])
            
            if not departures:
                return f"🚌 No upcoming departures found for {stop_name}"
            
            response = f"🚌 Next Departures from {stop_name}:\n\n"
            
            # Sort by departure time and take first 5
            sorted_departures = sorted(departures, key=lambda x: x.get('realtimeDeparture', x.get('scheduledDeparture', 0)))[:5]
            
            for departure in sorted_departures:
                route = departure.get('trip', {}).get('route', {})
                bus_number = route.get('shortName', 'N/A')
                headsign = departure.get('headsign', 'Unknown destination')
                
                # Use realtime departure if available, otherwise scheduled
                departure_time = departure.get('realtimeDeparture') or departure.get('scheduledDeparture', 0)
                service_day = departure.get('serviceDay', 0)
                
                # Convert service day + departure time to actual time
                # serviceDay is midnight of the day in seconds since epoch
                # departure time is seconds since midnight
                actual_time = service_day + departure_time
                
                # Convert to Helsinki time format
                import datetime
                import zoneinfo
                
                # Create datetime object in UTC first, then convert to Helsinki timezone
                dt_utc = datetime.datetime.fromtimestamp(actual_time, tz=datetime.timezone.utc)
                dt_helsinki = dt_utc.astimezone(zoneinfo.ZoneInfo("Europe/Helsinki"))
                time_str = dt_helsinki.strftime("%H:%M")
                
                # Show if it's realtime or scheduled
                realtime_indicator = "🟢" if departure.get('realtime') else "🔵"
                
                response += f"{realtime_indicator} Bus {bus_number} → {headsign} at {time_str}\n"
            
            return response.strip()
            
        except (KeyError, IndexError, TypeError) as e:
            return f"Sorry, I couldn't parse the bus departure data properly: {str(e)}"
    
    def format_time_response(self, time_data: dict) -> str:
        """Format current time data into a readable response"""
        try:
            if "error" in time_data:
                return f"Sorry, I couldn't get the current time: {time_data['error']}"
        except (TypeError, AttributeError):
            # time_data is not a dict or doesn't support 'in' operator
            pass
        
        try:
            current_time = time_data.get('current_time', 'N/A')
            current_date = time_data.get('current_date', 'N/A')
            weekday = time_data.get('weekday', 'N/A')
            timezone = time_data.get('timezone', 'N/A')
            
            response = f"🕐 Current Time in Helsinki:\n"
            response += f"Time: {current_time}\n"
            response += f"Date: {current_date}\n"
            response += f"Day: {weekday}\n"
            response += f"Timezone: {timezone}"
            
            return response
            
        except (KeyError, TypeError, AttributeError) as e:
            return f"Sorry, I couldn't parse the time data properly: {str(e)}"
    
    def send_message(self, message: str) -> str:
        """Send a message to the LLM and return the response"""
        # Check if user is asking for weather
        if self.check_weather_request(message):
            # Get weather data
            weather_data = self.get_weather()
            weather_response = self.format_weather_response(weather_data)
            
            # Add user message and weather response to conversation
            self.conversation.append({"role": "user", "content": message})
            self.conversation.append({"role": "assistant", "content": weather_response})
            
            return weather_response
        
        # Check if user is asking for bus departures
        if self.check_bus_request(message):
            # Extract stop ID from message
            stop_id = self.extract_stop_id(message)
            
            # Get bus departure data
            bus_data = self.get_next_departures(stop_id)
            bus_response = self.format_bus_response(bus_data, stop_id)
            
            # Add user message and bus response to conversation
            self.conversation.append({"role": "user", "content": message})
            self.conversation.append({"role": "assistant", "content": bus_response})
            
            return bus_response
        
        # Check if user is asking for current time
        if self.check_time_request(message):
            # Get current time data
            time_data = self.get_current_time()
            time_response = self.format_time_response(time_data)
            
            # Add user message and time response to conversation
            self.conversation.append({"role": "user", "content": message})
            self.conversation.append({"role": "assistant", "content": time_response})
            
            return time_response
        
        # Regular conversation flow
        # Add user message to conversation history
        self.conversation.append({"role": "user", "content": message})
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation
            )
            
            response = completion.choices[0].message.content
            
            # Add assistant response to conversation history
            self.conversation.append({"role": "assistant", "content": response})
            
            return response
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def start_chat(self):
        """Start the interactive chat loop"""
        print(f"🚌 Vibebus Chat Agent (Model: {self.model})")
        print("🌤️  Available tools: Weather information, Bus departure times, Current time")
        print("Type 'quit', 'exit', or press Ctrl+C to end the conversation\n")
        
        try:
            while True:
                try:
                    user_input = input("You: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("Goodbye!")
                        break
                    
                    if not user_input:
                        continue
                    
                    print("🤖 Thinking...")
                    response = self.send_message(user_input)
                    print(f"Assistant: {response}\n")
                    
                except KeyboardInterrupt:
                    print("\n\nGoodbye!")
                    break
                    
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Vibebus - CLI Chat Agent")
    parser.add_argument(
        "--model", "-m",
        help="LLM model to use (default: from .env or openai/gpt-4o)",
        default=None
    )
    
    args = parser.parse_args()
    
    try:
        chat = VibebusChat(model=args.model)
        chat.start_chat()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please create a .env file with your OPENROUTER_API_KEY")
        print("See .env.example for template")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()