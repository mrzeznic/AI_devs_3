import os
import json
import requests
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai

# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
TASK_ID = "loop"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W3L04"
URL_PEOPLE = "https://centrala.ag3nts.org/people"
URL_PLACES = "https://centrala.ag3nts.org/places"
URL_BARBARA = "https://centrala.ag3nts.org/dane/barbara.txt"
DATA_FOLDER = "./data/W3L04"

# API keys
api_key = get_api_key()
openai.api_key = get_open_api_key()

# Ensure cache folder and data folder exist
os.makedirs(CACHE_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# Function to run query against a given URL (e.g., people or places)
def run_query(url, query):
    payload = {
        "apikey": api_key,
        "query": query
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to execute query '{query}': {response.text}, for url: {url}")
    
# Fetch text from URL_BARBARA
def fetch_text_from_barbara():
    print("Fetching text from Barbara...")
    response = requests.get(URL_BARBARA)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch text from {URL_BARBARA}: {response.text}")

# Function to extract Polish nominative names using OpenAI
def extract_polish_names(text):
    cache_path = os.path.join(CACHE_FOLDER, "polish_names.txt")
    
    # Only use the cached result if USE_CACHE is True and the cache exists
    if USE_CACHE and os.path.exists(cache_path):
        print("Using cached Polish names")
        with open(cache_path, "r") as cache_file:
            names_list = [name.strip() for name in cache_file.readlines() if name.strip()]
        return names_list
    
    else:
        print("Extracting Polish nominative names using LLM...")
        prompt = (
            "Extract all Polish names in the nominative form from the following text:\n\n"
            f"{text}\n\n"
            "Provide the names as a list in nominative form."
        )
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in identifying Polish names. Return only the names in capital letters without surname in the nominative form and polish characters. Return it in pure python list without any comments."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extracted names as a string, now we split them into a list
        names = response["choices"][0]["message"]["content"].strip()
        
        # Clean and format names properly by removing unwanted quotes and splitting based on commas
        names_list = [name.strip().replace('"', '').replace('[', '').replace(']', '').replace("'", "").replace('Ł', 'L') for name in names.split(",") if name.strip()]
        print(f"Cleaned names: {names_list}")
        
        # Save the names to the cache file as plain text
        with open(cache_path, "w") as cache_file:
            for name in names_list:
                cache_file.write(f"{name}\n")
            
        return names_list

# Function to send each name to URL_PEOPLE and store results
def send_name_to_people(name):
    if name == "BARBARA":
        print(f"Skipping Barbara as she contains restricted data: {name}")
        return  # Skip Barbara's data
    
    print(f"Sending name '{name}' to {URL_PEOPLE}...")
    result = run_query(URL_PEOPLE, name)
    # Save the result to the data folder
    save_people_result_to_data(name, result)

# Function to save the result from URL_PEOPLE to data folder as .json
def save_people_result_to_data(name, result):
    data_path = os.path.join(DATA_FOLDER, f"{name}.json")
    with open(data_path, "w") as data_file:
        json.dump(result, data_file)

    # Now extract city names from the 'message' key and send each city to URL_PLACES
    cities = result.get("message", "").split()  # Split by spaces to get individual cities
    for city in cities:
        send_city_to_places(city)

# Function to send a city to URL_PLACES and save the results
def send_city_to_places(city):
    print(f"Sending city '{city}' to {URL_PLACES}...")
    result = run_query(URL_PLACES, city)
    
    # Save the result to a .txt file in the data folder
    save_city_result_to_data(city, result)

# Function to save city results from URL_PLACES to data folder as .txt
def save_city_result_to_data(city, result):
    data_path = os.path.join(DATA_FOLDER, f"{city}.txt")
    # Assuming the result contains some meaningful data to write, adjust accordingly
    with open(data_path, "w") as data_file:
        data_file.write(json.dumps(result, ensure_ascii=False))  # Save as JSON string

# Function to find the place with only "BARBARA" and send the name to CENTRALA_API
def send_place_with_barbara_to_central_api(place_name):
    print(f"Sending place with BARBARA to CENTRALA_API: {place_name}")
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": place_name
    }
    response = requests.post(CENTRALA_API, json=payload)
    print(response)
    if response.status_code == 200:
       print(f"Successfully sent place: {place_name}")
       return response.json().get("message")
    else:
        print(f"Failed to send place: {place_name}, Response: {response.text}")

# Main function
def main():
    try:
        # Fetch text from URL_BARBARA
        barbara_text = fetch_text_from_barbara()

        # Extract Polish names and ensure it's a list
        polish_names = extract_polish_names(barbara_text)
        print(f"Extracted Polish names: {polish_names}")

        # Send each name to URL_PEOPLE and store results
        for name in polish_names:
            send_name_to_people(name)

        # Now check the .txt files in the DATA_FOLDER to find where the "message" key equals "BARBARA"
        for filename in os.listdir(DATA_FOLDER):
            if filename.endswith(".txt"):
                file_path = os.path.join(DATA_FOLDER, filename)
                with open(file_path, "r", encoding="utf-8") as file:
                    try:
                        # Try to load the content as JSON
                        file_content = json.load(file)
                        # Check if the "message" key exists and its value is "BARBARA"
                        if file_content.get("message") == "BARBARA":
                            # Remove the .txt extension and send the name to CENTRALA_API
                            place_name = filename.replace(".txt", "")
                            flag = send_place_with_barbara_to_central_api(place_name)
                            if flag:
                                print(f"Flag received: {flag}")
                            else:
                                print("No flag received.")
                            break  # Exit after the first match is found
                    except json.JSONDecodeError:
                        print(f"Failed to decode JSON in file: {filename}")

    except Exception as e:
        print("An error occurred:", str(e))

if __name__ == "__main__":
    main()