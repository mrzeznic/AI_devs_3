import os
import json
import requests
import openai
import argparse
from pathlib import Path
from get_key import get_key
from pathlib import Path
from flask import Flask, request, jsonify

# Configuration
CENTRALA_API_REPORT = "https://centrala.ag3nts.org/report"
CENTRALA_API = "https://centrala.ag3nts.org"
TASK_ID = "webhook"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W4L04"

#keys
api_key = get_key("api_key")
openai.api_key = get_key("open_api_key")
webhook_url = get_key("webhook_url")
webhook_port = get_key("webhook_port")

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

app = Flask(__name__)
client = None
map_content = None

def load_map() -> str:
    """Load map content from file"""
    map_path = Path("data/webhook/mapa.txt")
    if not map_path.exists():
        raise FileNotFoundError("Map file not found")
    return map_path.read_text(encoding='utf-8')

def analyze_drone_location(instruction: str) -> dict:
    """Analyze drone location using GPT-4o"""
    try:
        response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": f"""Jesteś ekspertem do spraw nawigacji dronów. Przeanalizuj dostarczoną mapę i instrukcje ruchu drona, aby określić jego ostateczną lokalizację na mapie.

Zasady:
1. Użyj pola "thinking", aby krop po kroku przejść prze instrukcje i wyjaśnić swoje rozumowanie
2. W polu "description" podaj lokalizację drona na mapie po wykonaniu wszystkich instrukcji użytkownika
3. Nie dodawaj ŻADNYCH zbędnych komentarzy w polu "description"

<map>
{map_content}
</map>

Format wyjściowy:
{{
    "thinking": "Wyjaśnij swoje rozumowanie tutaj",
    "description": "Ostateczna lokalizacja drona"
}}"""
                },
                {
                    "role": "user",
                    "content": f"<instruction>{instruction}</instruction>"
                }
            ],
            model="gpt-4o-mini",
            temperature=0.0,
        )
        
        # Remove the encoding parameter from json.loads
        result = json.loads(response.choices[0].message.content.strip())
        print(f"\nLLM Analysis:\nInput: {instruction}\nOutput: {json.dumps(result, indent=2, ensure_ascii=False)}\n")
        
        return result
    except Exception as e:
        print(f"Error in analyze_drone_location: {str(e)}")
        return {"description": "nieznana lokalizacja"}

def send_webhook_url() -> dict:
    """Send webhook URL to the API"""
    webhook_data = {
        "task": "webhook",
        "apikey": api_key,
        "answer": webhook_url
    }
    response = requests.post(
        CENTRALA_API_REPORT,
        json=webhook_data
    )
    print(f"Webhook response: {response.text}")
    if not response.ok:
        raise Exception(f"Failed to send webhook URL: {response.text}")
    return response.json()

@app.route('/', methods=['POST'])
def webhook():
    """Handle incoming webhook requests"""
    try:
        data = request.get_json()
        print(f"\nReceived webhook request: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid request format"}), 400
        if not data.get('instruction'):
            return jsonify({"error": "Missing instruction"}), 400
        if not isinstance(data['instruction'], str):
            return jsonify({"error": "Instruction must be a string"}), 400
        
        result = analyze_drone_location(data['instruction'])
        print(f"Sending response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return jsonify(result)
    
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON"}), 400
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def main():
    global client, map_content
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-start', action='store_true', help='Send webhook URL to API')
    args = parser.parse_args()
    
    #port = int(webhook_port)
    #print(f"\nStarting webhook server on port {port}...")
    #app.run(host='127.0.0.1', port=port)
    
    try:
        client = openai
        
        if args.start:
            print("\nSending webhook URL to API...")
            response = send_webhook_url()
            print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
            return
            
        print("\nLoading map data...")
        map_content = load_map()
        
        #webhook_url = os.getenv('AIDEVS_WEBHOOK_URL')
        #webhook_port = os.getenv('AIDEVS_WEBHOOK_PORT')
        if not webhook_url:
            raise ValueError("AIDEVS_WEBHOOK_URL environment variable not set")
        if not webhook_port:
            raise ValueError("AIDEVS_WEBHOOK_PORT environment variable not set")
            
        port = int(webhook_port)
        print(f"\nStarting webhook server on port {port}...")
        app.run(host='127.0.0.1', port=port)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    main() 