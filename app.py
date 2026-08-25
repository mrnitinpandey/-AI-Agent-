import os
import sys
import json
import datetime
import subprocess
from flask import Flask, request, jsonify, send_from_directory, session
from dotenv import load_dotenv
from google import genai
from google.genai import types
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_129847120938")

USERS_FILE = "users.json"

# Helper for users file database
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")

# Global state
api_key = os.environ.get("GEMINI_API_KEY")
client = None
chat_session = None
command_logs = []

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
        
        cleaned_output = output if output.strip() else "Command executed successfully with no stdout."
        # Save to logs
        command_logs.append({
            "command": command,
            "output": cleaned_output
        })
        return cleaned_output
    except Exception as e:
        error_msg = f"Error executing command: {str(e)}"
        command_logs.append({
            "command": command,
            "output": error_msg
        })
        return error_msg

# Register tools
tools_list = [get_current_time, run_local_command]

def init_gemini_client():
    global client, chat_session, api_key
    if api_key and api_key != "your_gemini_api_key_here":
        try:
            client = genai.Client(api_key=api_key)
            chat_session = client.chats.create(
                model="gemini-3.6-flash",
                config=types.GenerateContentConfig(
                    system_instruction="You are a helpful local developer AI Agent. You have access to local tools such as checking the system time or running a shell command. Use them to answer questions when necessary.",
                    tools=tools_list,
                    temperature=0.7,
                )
            )
            return True
        except Exception as e:
            print(f"Error initializing Gemini client: {e}")
            return False
    return False

# Initialize at start
init_gemini_client()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "has_key": api_key is not None and api_key != "your_gemini_api_key_here" and api_key != ""
    })

@app.route('/api/config', methods=['POST'])
def save_config():
    global api_key, client, chat_session
    data = request.json
    new_key = data.get("api_key", "").strip()
    if not new_key:
        return jsonify({"status": "error", "message": "Key cannot be empty"}), 400

    api_key = new_key
    # Save key to .env file
    try:
        with open(".env", "w") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")
    except Exception as e:
        print(f"Warning: Could not save API key to .env: {e}")

    success = init_gemini_client()
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Failed to initialize Gemini Client with provided key"}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    global chat_session
    if not chat_session:
        return jsonify({"error": "Gemini Client not initialized. Please set a valid API key."}), 400

    data = request.json
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    # Local offline processing fallback handler
    def handle_local_mock_response(user_msg):
        msg_lower = user_msg.lower()
        if "time" in msg_lower:
            t = get_current_time()
            return f"**[Offline Fallback Mode]** The current local system time is `{t}`."
        elif "list files" in msg_lower or "dir" in msg_lower or "ls" in msg_lower:
            out = run_local_command("dir")
            return f"**[Offline Fallback Mode]** List of files:\n```\n{out}\n```"
        elif "python version" in msg_lower or "python --version" in msg_lower:
            out = run_local_command("python --version")
            return f"**[Offline Fallback Mode]** System Python version output:\n```\n{out}\n```"
        elif msg_lower.startswith("run: ") or msg_lower.startswith("run "):
            cmd = user_msg[4:].strip()
            out = run_local_command(cmd)
            return f"**[Offline Fallback Mode]** Executed command `{cmd}`:\n```\n{out}\n```"
        else:
            return (
                "**[Offline Fallback Mode]**\n\n"
                "Your Gemini API Key has exceeded its free tier rate limits (429 Resource Exhausted).\n"
                "To prevent disruption, I have switched to offline mock mode.\n\n"
                "You can still trigger local actions:\n"
                "- Ask: *\"What time is it?\"*\n"
                "- Ask: *\"List files\"*\n"
                "- Ask: *\"Check python version\"*\n"
                "- Or type: *\"run <command>\"* (e.g. `run dir` or `run ipconfig`) to execute any terminal shell command."
            )

    try:
        response = chat_session.send_message(message)
        return jsonify({"response": response.text})
    except Exception as e:
        err_str = str(e)
        if any(keyword in err_str or keyword in err_str.lower() for keyword in ["429", "resource_exhausted", "quota", "limit", "exhausted"]):
            return jsonify({"response": handle_local_mock_response(message)})
        return jsonify({"error": err_str}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify({"logs": command_logs})

if __name__ == "__main__":
    print("==================================================")
    print("      AI Agent Web Server Starting...             ")
    print("      Open http://127.0.0.1:5000 in your browser  ")
    print("==================================================")
    app.run(host="127.0.0.1", port=5000, debug=True)
