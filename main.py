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
    def __init__(self, model: str = None, conversation_max_length: int = 100):
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
        self.conversationMaxLength = conversation_max_length
        
        # Define available tools for the model
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather information for Helsinki, Finland",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "get_next_departures",
                    "description": "Get next bus departure times for a specific stop",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "stop_id": {
                                "type": "string",
                                "description": "The bus stop ID (e.g., HSL:1434183). If not provided, uses default stop."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time", 
                    "description": "Get the current time and date in Helsinki timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
        
        # Add system message with tool information
        self.conversation.append({
            "role": "system",
            "content": "You are a helpful assistant for Helsinki with access to local information. You can help users with weather, bus departures, and current time. Use the available functions when appropriate to provide accurate, real-time information."
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
    
    def get_next_departures(self, stop_id: str = None) -> dict:
        """Get next departure times for a bus stop using GraphQL API"""
        url = "https://api.digitransit.fi/routing/v2/hsl/gtfs/v1"
        
        # Use default stop ID if none provided
        if not stop_id:
            stop_id = "HSL:1434183"
        
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
    
    def _trim_conversation(self):
        """Trim conversation to max length, preserving system message"""
        if len(self.conversation) <= self.conversationMaxLength:
            return
        
        # Keep system message (first message) and remove oldest user/assistant messages
        system_message = self.conversation[0] if self.conversation and self.conversation[0]["role"] == "system" else None
        messages_to_keep = self.conversation[-(self.conversationMaxLength - (1 if system_message else 0)):]
        
        if system_message:
            self.conversation = [system_message] + messages_to_keep
        else:
            self.conversation = messages_to_keep
    
    def send_message(self, message: str) -> str:
        """Send a message to the LLM and return the response"""
        # Add user message to conversation history
        self.conversation.append({"role": "user", "content": message})
        
        # Trim conversation if it exceeds max length
        self._trim_conversation()
        
        try:
            # Initial completion with tools
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation,
                tools=self.tools,
                tool_choice="auto"
            )
            
            response_message = completion.choices[0].message
            
            # Check if model wants to call tools
            if response_message.tool_calls:
                # Add assistant's tool call message to conversation
                self.conversation.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": response_message.tool_calls
                })
                
                # Execute each tool call
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    
                    # Execute the appropriate function
                    if function_name == "get_weather":
                        function_result = self.get_weather()
                    elif function_name == "get_next_departures":
                        stop_id = function_args.get("stop_id")
                        function_result = self.get_next_departures(stop_id)
                    elif function_name == "get_current_time":
                        function_result = self.get_current_time()
                    else:
                        function_result = {"error": f"Unknown function: {function_name}"}
                    
                    # Add tool result to conversation
                    self.conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(function_result)
                    })
                
                # Get final completion with tool results
                final_completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.conversation,
                    tools=self.tools,
                    tool_choice="auto"
                )
                
                final_response = final_completion.choices[0].message.content
                
                # Add final response to conversation
                self.conversation.append({"role": "assistant", "content": final_response})
                
                # Trim conversation if it exceeds max length
                self._trim_conversation()
                
                return final_response
            else:
                # No tool calls needed, return direct response
                response = response_message.content
                self.conversation.append({"role": "assistant", "content": response})
                
                # Trim conversation if it exceeds max length
                self._trim_conversation()
                
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