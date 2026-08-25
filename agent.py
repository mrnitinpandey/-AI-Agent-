import os
import sys
import datetime
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    print("GEMINI_API_KEY is missing or contains the default placeholder.")
    api_key = input("Please enter your Gemini API key: ").strip()
    if not api_key:
        print("Error: Gemini API Key is required to run the agent.")
        sys.exit(1)
    # Save the entered key to .env
    try:
        with open(".env", "w") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
        print("Successfully saved API key to .env!")
    except Exception as e:
        print(f"Warning: Could not save API key to .env: {e}")

# Initialize the Gemini Client using the google-genai SDK
client = genai.Client(api_key=api_key)

# Define some useful local tools for the agent

def get_current_time() -> str:
    """Returns the current date and time on the local system."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_local_command(command: str) -> str:
    """Runs a shell command locally on the user's Windows system and returns the stdout or stderr output."""
    try:
        # Using powershell as requested or shell=True on Windows
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=15)
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
        return output if output.strip() else "Command executed successfully with no stdout."
    except Exception as e:
        return f"Error executing command: {str(e)}"

# Register the list of tools
tools_list = [get_current_time, run_local_command]

def run_agent():
    print("==================================================")
    print("      AI Agent CLI (Powered by Gemini)            ")
    print("==================================================")
    print("Type 'exit' or 'quit' to end the conversation.\n")
    
    # We use a chat session to maintain conversation history
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            system_instruction="You are a helpful local developer AI Agent. You have access to local tools such as checking the system time or running a shell command. Use them to answer questions when necessary.",
            tools=tools_list,
            temperature=0.7,
        )
    )
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye! Jai Shree Ram🙏")
                break
                
            print("\nAgent is thinking...")
            response = chat.send_message(user_input)
            
            # Print the agent's text response
            print(f"\nAgent: {response.text}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    run_agent()
