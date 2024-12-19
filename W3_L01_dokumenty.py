import os
import json
import requests
import zipfile
from pathlib import Path
from typing import Dict
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai

TASK_ID = "dokumenty"
INPUT_DATA = "https://centrala.ag3nts.org/dane/pliki_z_fabryki.zip"
OUTPUT_URL = "https://centrala.ag3nts.org/report"
EXTRACTION_FOLDER = "./extracted_files/W3L01"
CACHE_FOLDER = "./cache/W3L01"  # Directory for cache files
CACHE_ENABLED = False  # Toggle caching

api_key = get_api_key()
openai.api_key = get_open_api_key()

def download_and_extract_zip(url: str, extraction_path: str):
    """Download and extract a ZIP file."""
    try:
        print("Downloading ZIP file...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        zip_path = os.path.join(extraction_path, "files.zip")
        os.makedirs(extraction_path, exist_ok=True)

        with open(zip_path, "wb") as zip_file:
            for chunk in response.iter_content(chunk_size=8192):
                zip_file.write(chunk)

        print("Extracting ZIP file...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extraction_path)
        print("Files extracted successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading ZIP file: {e}")
        raise
    except zipfile.BadZipFile:
        print("Error: Bad ZIP file.")
        raise

def load_cache(file_path: str) -> Dict:
    """Load data from cache if it exists."""
    if not CACHE_ENABLED or not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as cache_file:
            print(f"Loaded cache from {file_path}.")
            return json.load(cache_file)
    except Exception as e:
        print(f"Failed to load cache: {e}")
        return {}

def save_cache(file_path: str, data: Dict):
    """Save data to cache."""
    if not CACHE_ENABLED:
        return
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file, indent=4, ensure_ascii=False)
        print(f"Saved cache to {file_path}.")
    except Exception as e:
        print(f"Failed to save cache: {e}")

def generate_keywords(text: str, cache_path: Path) -> str:
    """Generate keywords for a given text using OpenAI, with caching."""
    if CACHE_ENABLED and cache_path.exists():
        print(f"Using cached keywords for {cache_path.name}")
        with open(cache_path, "r", encoding="utf-8") as file:
            return file.read()
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """Jestes asystentem generujacym slowa kluczowe w formie mianownika do pomocy w kategoryzacji dokumentow tekstowych.
                 Wszystkie slowa kluczowe powinny byc oddzielone przecinkami, unikaj dodawania nowych znacznikow nowej linii. 
                 Pierwsze slowo klucz MUSI byc nazwą sektora/działu wyciągniętą z nazwy pliku w formacie na przykalad 'sektor X1', 'sektor X2' itp.. 
                 Zwroc uwage na osoby (jeśli podane) - kim jest, czym się zajmuje (bardzo konkretnie), 
                 gdzie mieszka oraz inne istotne szczegóły. Jezeli znajdziesz osobe wyciagnij dla niej slowa kluczowe"""},
                {"role": "user", "content": f"Wybierz slowa kluczowe z ponizszego tekstu:\n\n{text}"}
                
            ],
            temperature=0.3,
            max_tokens=300
        )
        keywords = response.choices[0].message["content"].strip()
        if CACHE_ENABLED:
            os.makedirs(cache_path.parent, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as file:
                file.write(keywords)
        return keywords
    except Exception as e:
        print(f"Error generating keywords: {e}")
        return "Error generating keywords"

def process_txt_files(extraction_path: str) -> Dict[str, str]:
    """Process TXT files and generate keywords."""
    keywords_dict = {}
    txt_files = list(Path(extraction_path).glob("*.txt"))
    print(f"Found {len(txt_files)} TXT files. Processing up to 10 files...")

    for txt_file in txt_files[:10]:  # Limit to 10 files
        print(f"Processing file: {txt_file.name}")
        try:
            cache_path = Path(CACHE_FOLDER) / f"{txt_file.name}.cache"
            with open(txt_file, "r", encoding="utf-8") as file:
                text_content = file.read()
            keywords = generate_keywords(text_content, cache_path)
            keywords_dict[txt_file.name] = keywords
        except Exception as e:
            print(f"Error processing file {txt_file.name}: {e}")
            keywords_dict[txt_file.name] = "Error processing file"

    return keywords_dict

def send_report(data: Dict[str, str]):
    """Send the generated report to the API."""
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": data
    }
    try:
        response = requests.post(OUTPUT_URL, json=payload)
        response.raise_for_status()
        print("Report successfully sent to the central API.")
        print("Response:", response.json())
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending report: {e}")
        return None

def main():
    try:
        # Step 1: Download and extract ZIP file
        print("Starting task...")
        if not os.path.exists(EXTRACTION_FOLDER):
            os.makedirs(EXTRACTION_FOLDER)
        download_and_extract_zip(INPUT_DATA, EXTRACTION_FOLDER)

        # Step 2: Process TXT files to generate keywords
        print("\nGenerating keywords for TXT files...")
        keywords_dict = process_txt_files(EXTRACTION_FOLDER)
        print(f"Generated keywords:\n{json.dumps(keywords_dict, indent=4, ensure_ascii=False)}")

        # Step 3: Send the report to the central API
        print("\nSending the report to the central API...")
        response = send_report(keywords_dict)
        return response
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()