import requests
from get_api_key import get_api_key

DATA_URL = "https://poligon.aidevs.pl/dane.txt"
VERIFY_URL = "https://poligon.aidevs.pl/verify"
TASK_ID = "POLIGON"

def fetch_data(url):
    """Fetches raw text data from a given URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.text.strip().split("\n")

def send_verification(api_key, answer):
    """Sends the answer payload to the verification URL."""
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": answer
    }
    response = requests.post(VERIFY_URL, json=payload)
    response.raise_for_status()
    return response

def main():
    api_key = get_api_key()
    if not api_key:
        print("API key retrieval failed. Exiting.")
        return
    
    answer = fetch_data(DATA_URL)
    response = send_verification(api_key, answer)
    
    print(f"Status Code: {response.status_code}")
    print("Response JSON:", response.json())

if __name__ == "__main__":
    main()