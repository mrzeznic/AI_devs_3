import os
import json
import requests
import zipfile
import openai
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import hashlib

# Constants
TASK_ID = "kategorie"
INPUT_URL = "https://centrala.ag3nts.org/dane/pliki_z_fabryki.zip"
OUTPUT_URL = "https://centrala.ag3nts.org/report"
EXTRACTION_FOLDER = "./extracted_files"
FACTS_FOLDER = "fakty"
CACHE_FILE = "classification_cache.json"

# Initialize API keys
central_key = get_api_key()
openai.api_key = get_open_api_key()

# Load cache for MP3 and image processing
classification_cache = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as cache_file:
        classification_cache = json.load(cache_file)


def save_cache():
    """Save the classification cache to a file."""
    with open(CACHE_FILE, "w") as cache_file:
        json.dump(classification_cache, cache_file, indent=4)


def generate_file_hash(file_path):
    """Generate a hash for the file content."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def classify_file_content(content):
    """Classify text content into one of the categories."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            temperature=0.5,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that classifies files into categories based on their content. "
                        "Use the following rules:\n"
                        "1 (people): Reports or files about detained individuals or traces of their presence.\n"
                        "2 (hardware): Reports or files describing physical problems with devices or hardware issues.\n"
                        "Output only 'people' or 'hardware' for matching categories, and 'none' if it does not match.\n"
                        "For reference:\n"
                        "people: '2024-11-12_report-00-sektor_C4.txt', '2024-11-12_report-07-sektor_C4.txt', '2024-11-12_report-10-sektor-C1.mp3'\n"
                        "hardware: '2024-11-12_report-13.png', '2024-11-12_report-15.png', '2024-11-12_report-17.png'\n"
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


def transcribe_audio_with_openai(file_path):
    """Transcribe MP3 audio file to text using OpenAI Whisper."""
    try:
        file_hash = generate_file_hash(file_path)

        # Check if result is already cached
        if file_hash in classification_cache:
            return classification_cache[file_hash]

        print(f"Transcribing audio file: {file_path}")
        with open(file_path, "rb") as audio_file:
            response = openai.Audio.transcribe("whisper-1", audio_file)
            transcription = response.get("text", "")

        # Cache the result
        classification_cache[file_hash] = transcription
        save_cache()
        return transcription
    except Exception as e:
        print(f"Error transcribing audio file {file_path}: {e}")
        return ""


def analyze_image_with_openai(file_path):
    """Analyze image content using OpenAI."""
    try:
        file_hash = generate_file_hash(file_path)

        # Check if result is already cached
        if file_hash in classification_cache:
            return classification_cache[file_hash]

        print(f"Analyzing image file: {file_path}")
        with open(file_path, "rb") as image_file:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                temperature=0.5,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an assistant that interprets images and extracts meaningful text or descriptions. "
                            "Analyze the image content and decide if it relates to 'people' (detained individuals), "
                            "'hardware' (device issues), or 'none'."
                        )
                    },
                    {
                        "role": "user",
                        "content": "Analyze this image for classification."
                    }
                ],
                files={"image": image_file},
            )
            description = response['choices'][0]['message']['content'].strip()

        # Cache the result
        classification_cache[file_hash] = description
        save_cache()
        return description
    except Exception as e:
        print(f"Error analyzing image file {file_path}: {e}")
        return ""


def process_files():
    """Process all files in the extraction folder, excluding the facts folder."""
    classified_files = {"people": [], "hardware": []}

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

            content = ""
            # Transcribe MP3 files
            if file_ext == "mp3":
                content = transcribe_audio_with_openai(file_path)

            # Perform analysis on PNG files using OpenAI
            elif file_ext == "png":
                content = analyze_image_with_openai(file_path)

            # Read TXT files directly
            elif file_ext == "txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            if not content.strip():
                print(f"Empty or unsupported content in file: {file}")
                continue

            # Classify the content
            classification = classify_file_content(content)
            if classification in classified_files:
                classified_files[classification].append(file)
            else:
                print(f"Unclassified file: {file}")

    # Sort lists alphabetically
    for key in classified_files:
        classified_files[key].sort()

    return classified_files


def download_and_extract_zip(url, extraction_path):
    """Download and extract a ZIP file."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        zip_path = os.path.join(extraction_path, "files.zip")

        with open(zip_path, "wb") as zip_file:
            for chunk in response.iter_content(chunk_size=8192):
                zip_file.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extraction_path)
        print("Files extracted successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading ZIP file: {e}")
    except zipfile.BadZipFile:
        print("Error: Bad ZIP file.")


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
    if not os.path.exists(EXTRACTION_FOLDER):
        os.makedirs(EXTRACTION_FOLDER)
    download_and_extract_zip(INPUT_URL, EXTRACTION_FOLDER)

    classified_files = process_files()
    print("Classified files:", json.dumps(classified_files, indent=4, ensure_ascii=False))

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