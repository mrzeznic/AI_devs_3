import os
import zipfile  # <-- This import was missing
import requests
from pathlib import Path
import openai
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
from uuid import uuid4
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

TASK_ID = "wektory"
INPUT_DATA = "https://centrala.ag3nts.org/dane/pliki_z_fabryki.zip"
EXTRACTION_FOLDER = "./extracted_files/W3L02"
OUTPUT_URL = "https://centrala.ag3nts.org/report"
CACHE_FOLDER = "./cache/W3L02"
WEAPONS_ARCHIVE = "weapons_tests.zip"
PASSWORD = "1670"

api_key = get_api_key()
openai.api_key = get_open_api_key()

# Helper Functions
def download_and_extract_zip(url: str, extraction_path: str, zip_file_name: str = "files.zip"):
    """Download and extract a ZIP file only if the extraction folder does not exist."""
    if os.path.exists(extraction_path) and os.listdir(extraction_path):
        print(f"Extraction folder '{extraction_path}' already exists and is not empty. Skipping download and extraction.")
        return

    try:
        print("Downloading ZIP file...")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        os.makedirs(extraction_path, exist_ok=True)
        zip_path = os.path.join(extraction_path, zip_file_name)

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

def extract_encrypted_zip(zip_path: str, extraction_path: str, password: str):
    """Extract an encrypted ZIP file using a password."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extraction_path, pwd=bytes(password, "utf-8"))
        print("Encrypted ZIP file extracted successfully.")
    except Exception as e:
        print(f"Error extracting encrypted ZIP file: {e}")
        raise

def generate_embeddings(text: str):
    """Generate embeddings using OpenAI."""
    try:
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise

def index_reports_to_qdrant(report_paths: list, collection_name: str) -> None:
    """Index the reports into Qdrant with metadata and embeddings."""
    client = QdrantClient("localhost", port=6333)
    
    # Check if collection exists and recreate it
    if client.collection_exists(collection_name):
        print(f"Collection {collection_name} already exists, recreating...")
    
    # Create collection if it doesn't exist
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)  # Size of embedding vector
    )
    print(f"Collection {collection_name} created")
    
    # Process each report
    points = []
    for report_path in report_paths:
        try:
            with open(report_path, "r", encoding="utf-8") as file:
                content = file.read().strip()

            # Generate embedding for the content
            embedding = generate_embeddings(content)
            
            # Create point with metadata
            points.append(PointStruct(
                id=str(uuid4()),  # Use UUID as the point ID
                vector=embedding,
                payload={
                    "file_name": report_path.name,
                    "content": content
                }
            ))
            print(f"Indexed {report_path.name}")
        except Exception as e:
            print(f"Error indexing file {report_path.name}: {e}")
    
    # Upload the indexed reports in batch
    print(f"Uploading {len(points)} points to Qdrant...")
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    print(f"Successfully indexed {len(points)} reports")

def search_report_in_qdrant(query: str, collection_name: str) -> str:
    """Search the most relevant report using query embedding."""
    client = QdrantClient("localhost", port=6333)
    
    # Create query embedding
    query_embedding = generate_embeddings(query)
    print(f"Searching for reports with query: {query}")
    
    # Search for the most relevant report
    results = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=1
    )
    
    if not results:
        raise Exception("No results found")
    
    # Extract the date or relevant information from the metadata of the top result
    result = results[0]
    date = result.payload["file_name"]
    print(f"Found relevant report: {date}")
    return date

def send_report(answer: str):
    """Send the answer to the central API."""
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": answer
    }
    try:
        response = requests.post(OUTPUT_URL, json=payload)
        response.raise_for_status()
        print("Report successfully sent to the central API.")
        print("Response:", response.json())
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending report: {e}")
        raise

# Main Function
def main():
    try:
        # Step 1: Download and extract the main ZIP file
        if not os.path.exists(EXTRACTION_FOLDER):
            os.makedirs(EXTRACTION_FOLDER)
        download_and_extract_zip(INPUT_DATA, EXTRACTION_FOLDER)

        # Step 2: Extract the encrypted archive
        encrypted_zip_path = Path(EXTRACTION_FOLDER) / WEAPONS_ARCHIVE
        extracted_path = Path(EXTRACTION_FOLDER) / "weapons_tests"
        extract_encrypted_zip(encrypted_zip_path, extracted_path, PASSWORD)

        # Step 3: Index the TXT reports in Qdrant
        report_paths = list(extracted_path.glob("*.txt"))
        collection_name = "weapons_reports"
        index_reports_to_qdrant(report_paths, collection_name)

        # Step 4: Search for the relevant report
        query = "W raporcie, z którego dnia znajduje się wzmianka o kradzieży prototypu broni?"
        relevant_report_date = search_report_in_qdrant(query, collection_name)
        # Step 5: Send the date to the central API
        send_report(relevant_report_date)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()