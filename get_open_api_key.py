import json
import os

def get_open_api_key():
    """Retrieve the OPENAPI key from the secrets file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    secrets_file = os.path.join(current_dir, 'secrets.json')
    
    try:
        with open(secrets_file, 'r') as file:
            data = json.load(file)
            open_api_key = data.get('open_api_key')
            if not open_api_key:
                raise ValueError("OPENAPI key missing in secrets.json")
            return open_api_key
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        print(f"Error retrieving OPENAPI key: {e}")
        return None