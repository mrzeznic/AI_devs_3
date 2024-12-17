import os
import json
import requests
import zipfile
import openai
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key

# Constants
TASK_ID = "kategorie"
INPUT_URL = "https://centrala.ag3nts.org/dane/pliki_z_fabryki.zip"
OUTPUT_URL = "https://centrala.ag3nts.org/report"
EXTRACTION_FOLDER = "./extracted_files"
FACTS_FOLDER = "fakty"

# Initialize API keys
central_key = get_api_key()
openai.api_key = get_open_api_key()

def download_and_extract_zip(url, extraction_path):
    """Download and extract a ZIP file."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        zip_path = os.path.join(extraction_path, "files.zip")
        
        with open(zip_path, "wb") as zip_file:
            zip_file.write(response.content)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extraction_path)
        print("Files extracted successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading ZIP file: {e}")
    except zipfile.BadZipFile:
        print("Error: Bad ZIP file.")

def classify_file_content(file_path, file_ext):
    """Classify file content into one of the categories."""
    try:
        # For textual files, read content
        if file_ext == "txt":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        # For other files, use a placeholder description
        else:
            content = f"This is a {file_ext.upper()} file related to the task."

        # Use GPT to classify the content
        response = openai.ChatCompletion.create(
            model="gpt-4",
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that classifies information into categories. "
                        "Use the following rules:\n"
                        "1 (people) - about detained individuals or traces of their presence, "
                        "but only if they were observed or detained; otherwise, this does not fall under this category.\n"
                        "2 (software) - issues with software.\n"
                        "3 (hardware) - physical problems with devices, hardware issues.\n"
                        "If the information does not match any of these categories, return NONE.\n"
                        "Answer only one word: people, hardware, software, or NONE."
                    )
                },
                {"role": "user", "content": content}
            ]
        )
        category = response['choices'][0]['message']['content'].strip().lower()
        return category
    except openai.error.OpenAIError as e:
        print(f"Error during classification: {e}")
        return "none"

def process_files():
    """Process all files in the extraction folder, excluding the facts folder."""
    classified_files = {"people": [], "software": [], "hardware": [], "none": []}

    for root, dirs, files in os.walk(EXTRACTION_FOLDER):
        # Skip the "fakty" folder
        if FACTS_FOLDER in root:
            continue

        for file in files:
            file_path = os.path.join(root, file)
            file_ext = file.split('.')[-1].lower()

            if file_ext not in ["txt", "png", "mp3"]:
                print(f"Skipping unsupported file type: {file}")
                continue

            classification = classify_file_content(file_path, file_ext)
            if classification in classified_files:
                classified_files[classification].append(file)
            else:
                classified_files["none"].append(file)

    # Sort lists alphabetically
    for key in classified_files:
        classified_files[key].sort()

    return classified_files

def send_json_to_api(url, json_data):
    """Send JSON data to the API."""
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        response = requests.post(url, json=json_data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
        return None

def main():
    # Step 1: Download and extract files
    if not os.path.exists(EXTRACTION_FOLDER):
        os.makedirs(EXTRACTION_FOLDER)
    download_and_extract_zip(INPUT_URL, EXTRACTION_FOLDER)

    # Step 2: Process files and classify them
    classified_files = process_files()
    print("Classified files:", json.dumps(classified_files, indent=4, ensure_ascii=False))

    # Step 3: Prepare and send the JSON data
    json_message = {
        "task": TASK_ID,
        "apikey": central_key,
        "answer": classified_files
    }
    print("Sending JSON data:", json.dumps(json_message, indent=4, ensure_ascii=False))

    response_data = send_json_to_api(OUTPUT_URL, json_message)
    if response_data:
        print("Response from API:", response_data)

if __name__ == "__main__":
    main()