# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "flask",
#     "requests",
# ]
# ///

# sorcery.py
# This script provides a simple Flask web server to forward the endpoints on an lBIS device.
# It's intended for use with the Sorcery extension for SillyTavern. When trying to use the lBIS API directly here, it throws CORS errors at you.
# In theory, it should enable you to use it with any ol' tool calling scheme.

# Use uv to run this script without setting up a venv or installing dependencies globally:
# uv run sorcery.py

import requests
from flask import Flask, jsonify, abort

# --- Configuration ---
# !!! Replace with the actual IP address of your lBIS device !!!
LBIS_DEVICE_IP = "10.105.23.145"
LBIS_API_BASE_URL = f"http://{LBIS_DEVICE_IP}/api"
# --- End Configuration ---

app = Flask(__name__)

def set_pump_state(state: float):
    """Sends a request to the lBIS device to set the pump state."""
    url = f"{LBIS_API_BASE_URL}/setPumpState"
    try:
        response = requests.post(url, json={"pump": state}, timeout=5)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        print(f"Set pump state to {state}. Response: {response.text}")
        return True, response.text
    except requests.exceptions.RequestException as e:
        print(f"Error setting pump state to {state}: {e}")
        return False, str(e)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, str(e)

@app.route("/pump/on")
def pump_on():
    """Turns the pump fully on (state 1.0)."""
    success, message = set_pump_state(1.0)
    if success:
        return jsonify({"status": "success", "message": f"Pump turned on. Device response: {message}"}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

@app.route("/pump/off")
def pump_off():
    """Turns the pump off (state 0.0)."""
    success, message = set_pump_state(0.0)
    if success:
        return jsonify({"status": "success", "message": f"Pump turned off. Device response: {message}"}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

@app.route("/pump/state/<float:level>")
def pump_set_level(level: float):
    """Sets the pump to a specific level (0.0 to 1.0)."""
    if not 0.0 <= level <= 1.0:
        abort(400, description="Invalid pump level. Must be between 0.0 and 1.0.")

    success, message = set_pump_state(level)
    if success:
        return jsonify({"status": "success", "message": f"Pump set to {level:.2f}. Device response: {message}"}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500


@app.route("/pump/status")
def pump_status():
    """Gets the current pump status from the lBIS device."""
    url = f"{LBIS_API_BASE_URL}/getPumpState"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        try:
            # The API returns the state as plain text float
            current_state = float(response.text)
            return jsonify({"status": "success", "pump_state": current_state}), 200
        except ValueError:
             return jsonify({"status": "error", "message": f"Could not parse device response: {response.text}"}), 500

    except requests.exceptions.RequestException as e:
        print(f"Error getting pump status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    print(f"Starting Flask server to control lBIS device at {LBIS_DEVICE_IP}")
    print("Endpoints:")
    print(f"  http://localhost:5000/pump/on")
    print(f"  http://localhost:5000/pump/off")
    print(f"  http://localhost:5000/pump/state/<level> (e.g., /pump/state/0.5)")
    print(f"  http://localhost:5000/pump/status")
    # Use host='0.0.0.0' to make it accessible on your network
    app.run(host='0.0.0.0', port=5000)