import os
import json
import logging
import tempfile
import shutil

# Try to get SESSION_FILE path relative to this file's location if utils isn't importable directly
try:
    from .utils import SESSION_FILE
except ImportError:
    # Fallback if running as a script or utils isn't in the path correctly yet
    _utils_dir = os.path.dirname(os.path.abspath(__file__))
    SESSION_FILE = os.path.join(_utils_dir, "session.json")


class StateManager:
    """Manages loading and atomic saving of bot state to a JSON file."""
    def __init__(self, file_path: str = SESSION_FILE, default_initial_time: int = 1800):
        self.file_path = file_path
        self.logger = logging.getLogger(__name__)
        self.default_initial_time = default_initial_time
        # Initialize state with defaults, including latch state
        self.state = {
            'session_time_remaining': 0,
            'last_session_update': None,
            'session_pump_start': None,
            'pump_last_on_time': 0,
            'pump_total_on_time': 0,
            'pump_state': False,
            'default_session_time': default_initial_time,
            'banked_time': 0,
            'latch_active': False,
            'latch_end_time': None,
            'latch_reason': None,
        }
        self.load_state()

    def load_state(self):
        """Load state from JSON file. If file doesn't exist or is invalid, initialize with defaults."""
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                # Update default state with loaded data, ensuring all keys exist
                self.state.update(data)
                self.logger.info(f"Loaded state from {self.file_path}")
        except FileNotFoundError:
            self.logger.warning(f"State file not found at {self.file_path}. Initializing with defaults and creating file.")
            # Save the default state to create the file
            self.save_state()
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading state from {self.file_path}: {e}. Using default state.")
            # Reset to defaults if loading failed, but don't overwrite potentially recoverable file yet
            self.state = {
                'session_time_remaining': 0,
                'last_session_update': None,
                'session_pump_start': None,
                'pump_last_on_time': 0,
                'pump_total_on_time': 0,
                'pump_state': False,
                'default_session_time': self.default_initial_time,
                'banked_time': 0,
                'latch_active': False,
                'latch_end_time': None,
                'latch_reason': None,
            }
        # Ensure default_session_time is correctly set even if loaded from file
        if 'default_session_time' not in self.state or self.state['default_session_time'] is None:
             self.state['default_session_time'] = self.default_initial_time


    def save_state(self):
        """Atomically save the current state dictionary to the JSON file."""
        temp_dir = os.path.dirname(self.file_path)
        try:
            # Create a temporary file in the same directory
            with tempfile.NamedTemporaryFile('w', dir=temp_dir, delete=False) as temp_f:
                json.dump(self.state, temp_f, indent=4)
                temp_path = temp_f.name # Get the path before closing

            # Replace the original file with the temporary file
            shutil.move(temp_path, self.file_path) # os.replace might fail across filesystems, shutil.move is safer
            self.logger.debug(f"Saved state atomically to {self.file_path}")
        except IOError as e:
            self.logger.error(f"Failed to save state to {self.file_path}: {e}")
            # Attempt to remove the temporary file if it still exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as remove_err:
                    self.logger.error(f"Failed to remove temporary state file {temp_path}: {remove_err}")
        except Exception as e: # Catch other potential errors during save
             self.logger.error(f"An unexpected error occurred during state save: {e}")
             if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as remove_err:
                    self.logger.error(f"Failed to remove temporary state file {temp_path}: {remove_err}")


    def update_and_save(self, bot_instance):
        """Update the state dictionary from bot attributes and save atomically."""
        # Sync bot attributes to state manager's state dictionary
        for key in self.state.keys():
            if hasattr(bot_instance, key):
                self.state[key] = getattr(bot_instance, key)
            else:
                # This case should ideally not happen if bot attributes are kept in sync
                self.logger.warning(f"Attribute '{key}' not found on bot instance during state update.")
        self.save_state()

    def apply_to_bot(self, bot_instance):
         """Apply the loaded state to the bot instance's attributes."""
         for key, value in self.state.items():
             setattr(bot_instance, key, value)
