import json
import os

def get_key(key_name):
    """Retrieve the API key from the secrets file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    secrets_file = os.path.join(current_dir, 'secrets.json')
    
    try:
        with open(secrets_file, 'r') as file:
            data = json.load(file)
            api_key = data.get(key_name)
            if not api_key:
                raise ValueError(f"{key_name} key is missing in secrets.json")
            return api_key
    except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
        print(f"Error retrieving {key_name} key: {e}")
        return None