import json
import requests
import re
import openai
import os
import pickle

# Constants
SECRETS_PATH = 'secrets.json'
CACHE_FILE_PATH = 'recordings/transcription.pkl'
FOLDER_PATH = 'recordings'
TASK_ID = "mp3"
OUTPUT_URL = 'https://centrala.ag3nts.org/report'

# Load secrets from secrets.json
def load_secrets(filepath):
    """Load API keys from the secrets file."""
    with open(filepath, 'r') as file:
        secrets = json.load(file)
    return secrets['open_api_key'], secrets['central_key']

# Initialize API keys
open_api_key, central_key = load_secrets(SECRETS_PATH)
openai.api_key = open_api_key  # Set OpenAI API key

# Iterowanie po plikach w folderze
if os.path.exists(CACHE_FILE_PATH):
    # Wczytywanie cache
    with open(CACHE_FILE_PATH, "rb") as cache_file:
        all_transcripts = pickle.load(cache_file)
    print("Cache loaded to file.")
else:
    for filename in os.listdir(FOLDER_PATH):
        print(filename)
        if filename.endswith(".m4a"):
            file_path = os.path.join(FOLDER_PATH, filename)

            # Otwieranie pliku MP3 i wysyłanie go do API
            with open(file_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file, language="pl")

            # Dodawanie nazwy pliku i jego transkrypcji do zmiennej all_transcripts
            all_transcripts = ""
            all_transcripts += f"Transkrypcja dla pliku {filename}:\n"
            all_transcripts += transcript["text"] + "\n"
            all_transcripts += "\n" + "-" * 40 + "\n\n"  # Separator dla czytelności

    with open(CACHE_FILE_PATH, "wb") as cache_file:
        pickle.dump(all_transcripts, cache_file)
    print("Cache zapisany do pliku.")

def get_chatgpt_response(context):
    """Anonymize text using OpenAI GPT model."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Or "gpt-4" if applicable
            temperature = 0.5,
            messages=[
                {
                    "role": "system",
                    "content": "You are FBI agent that interrogating witness and suspect. It is not given directly. _thinking in Polish"
                },
                {
                    "role": "user",
                    "content": 
                        "Answer in polish. Take a deep breath.Below is the content of the interrogations. Based on it, determine on which street the university where Andrzej Maj lectures is located."
                        "Remember that the witnesses’ testimonies may be contradictory, some of them may be mistaken, and others might respond in rather peculiar ways."
                        "The name of the street is not mentioned directly—deduce it."
                        "Remember that witness statements can be contradictory, some of them may be wrong, and others may respond in quite bizarre ways."
                        "The name of the street is not included in the transcript."
                        "Think for a while, don't provide immidiate answer, use what you have learned"
                        "Check the address on the internet to provide good information."
                        +context
                }
            ]
        )
        return response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        print(f"OpenAI API Error: {e}")
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

def build_json_message(street_name):
    """Build the JSON message to be sent to the API."""
    return {
        "task": TASK_ID,
        "apikey": central_key,
        "answer": street_name # wydział matematyki UJ
    }

def main():

    # Prepare answer based on transcription
    street_name = get_chatgpt_response(all_transcripts)
    
    if street_name:
        # Prepare and send the JSON data
        json_message = build_json_message(street_name)
        print("Sending JSON data:", json.dumps(json_message, indent=4, ensure_ascii=False))
        
        response_data = send_json_to_api(OUTPUT_URL, json_message)
        if response_data:
            print("Response from API:", response_data)
    else:
        print("No data to send.")

if __name__ == "__main__":
    main()