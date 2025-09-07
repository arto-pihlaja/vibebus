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
    def __init__(self, model: str = None, conversation_max_length: int = 20):
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