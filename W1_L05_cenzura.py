import json
import requests
import re
import openai

# Constants
SECRETS_PATH = 'secrets.json'
TASK_ID = "CENZURA"
OUTPUT_URL = 'https://centrala.ag3nts.org/report'
CENSORED_FILE_URL = "https://centrala.ag3nts.org/data/{central_key}/cenzura.txt"

# Load secrets from secrets.json
def load_secrets(filepath):
    """Load API keys from the secrets file."""
    with open(filepath, 'r') as file:
        secrets = json.load(file)
    return secrets['open_api_key'], secrets['central_key']

# Initialize API keys
open_api_key, central_key = load_secrets(SECRETS_PATH)
openai.api_key = open_api_key  # Set OpenAI API key

def get_chatgpt_response(text):
    """Anonymize text using OpenAI GPT model."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Or "gpt-4-turbo" if applicable
            messages=[
                {
                    "role": "system",
                    "content": "You are a tool that anonymizes sensitive personal information."
                },
                {
                    "role": "user",
                    "content": (
                        f"Anonymize the following text by replacing sensitive information such as "
                        f"names, addresses, cities, and ages with the word 'CENZURA'. Preserve all "
                        f"punctuation, spaces, and formatting:\n\n{text}"
                    )
                }
            ]
        )
        return response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        print(f"OpenAI API Error: {e}")
        return None

def fetch_file(url):
    """Fetch and return the content of the file."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file: {e}")
        return None

def process_censored_file(content):
    """Anonymize the content of the file using GPT."""
    if content:
        print("Sending content to GPT for anonymization...")
        return get_chatgpt_response(content)
    else:
        print("No content to process.")
        return None

def send_json_to_api(url, json_data):
    """Send JSON data to the API and return the response."""
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    try:
        response = requests.post(url, json=json_data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
        return None

def build_json_message(content):
    """Build the JSON message to be sent to the API."""
    return {
        "task": TASK_ID,
        "apikey": central_key,
        "answer": content
    }

def main():
    # Fetch the censored file
    data_url = CENSORED_FILE_URL.format(central_key=central_key)
    content = fetch_file(data_url)

    # Anonymize the file content using GPT
    anonymized_content = process_censored_file(content)

    if anonymized_content:
        # Prepare and send the JSON data
        json_message = build_json_message(anonymized_content)
        print("Sending JSON data:", json.dumps(json_message, indent=4, ensure_ascii=False))
        
        response_data = send_json_to_api(OUTPUT_URL, json_message)
        if response_data:
            print("Response from API:", response_data)
    else:
        print("No data to send.")

if __name__ == "__main__":
    main()