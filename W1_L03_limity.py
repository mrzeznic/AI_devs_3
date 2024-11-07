import json
import requests
import openai

# Constants
SECRETS_PATH = 'secrets.json'
OUTPUT_URL = 'https://centrala.ag3nts.org/report'
DATA_URL_TEMPLATE = 'https://centrala.ag3nts.org/data/{central_key}/json.txt'

# Load secrets from secrets.json
def load_secrets(filepath):
    """Load API keys from the secrets file."""
    with open(filepath, 'r') as file:
        secrets = json.load(file)
    return secrets['open_api_key'], secrets['central_key']

# Initialize API keys
open_api_key, central_key = load_secrets(SECRETS_PATH)
openai.api_key = open_api_key  # Set OpenAI API key

def get_chatgpt_response(question):
    """Get response from OpenAI GPT model."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Or "gpt-4" depending on availability
            messages=[{"role": "user", "content": question + " Answer in one word."}]
        )
        return response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        print(f"OpenAI API Error: {e}")
        return None

def fetch_data_from_url(url):
    """Fetch and return JSON data from the URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return {}

def process_test_data(data):
    """Process the test data and add answers."""
    for item in data.get("test-data", []):
        question = item.get("question")
        if question:
            try:
                result = eval(question)  # Evaluate the arithmetic expression
                item["answer"] = result
                if "test" in item:
                    print(f"'test' tag found: {item['test']}")
                    item['test']['a'] = get_chatgpt_response(item['test']['q'])
                    print(item['test']['a'])
            except Exception as e:
                print(f"Error evaluating expression '{question}': {e}")

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

def build_json_message(data):
    """Build the JSON message to be sent to the API."""
    return {
        "task": "JSON",
        "apikey": central_key,
        "answer": data
    }

def main():
    # Fetch the data
    data_url = DATA_URL_TEMPLATE.format(central_key=central_key)
    data = fetch_data_from_url(data_url)

    # Process the test data
    process_test_data(data)

    # Add the API key to the data
    data["apikey"] = central_key

    # Prepare and send the data
    json_message = build_json_message(data)
    print("Sending JSON data:", json.dumps(json_message, indent=4, ensure_ascii=False))
    
    response_data = send_json_to_api(OUTPUT_URL, json_message)
    if response_data:
        print("Response from API:", response_data)

if __name__ == "__main__":
    main()