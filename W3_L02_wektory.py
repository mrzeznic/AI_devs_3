import os
import json
import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.models import PointStruct
import openai
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key

# Configuration
TASK_ID = "wektory"
EXTRACTION_FOLDER = "./extracted_files/W3L02"
CACHE_FOLDER = "./cache/W3L02"
API_ENDPOINT = "https://centrala.ag3nts.org/report"
USE_CACHE = True
EMBEDDING_MODEL = "text-embedding-ada-002"
QDRANT_COLLECTION = "aidevs"

# Set up API keys
openai.api_key = get_open_api_key()
os.environ['OPENAI_API_KEY'] = openai.api_key
os.environ['CENTRALA_API_KEY'] = get_api_key()

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

# Load text files
def load_text_files(folder_path):
    files = {}
    for file in os.listdir(folder_path):
        if file.endswith('.txt'):
            with open(os.path.join(folder_path, file), "r") as f:
                files[file] = f.read()
    return files

# Cache utility
def get_cached_embedding(file_name):
    cache_path = os.path.join(CACHE_FOLDER, f"{file_name}.json")
    if USE_CACHE and os.path.exists(cache_path):
        with open(cache_path, "r") as cache_file:
            return json.load(cache_file)
    return None

def save_embedding_to_cache(file_name, embedding):
    if USE_CACHE:
        cache_path = os.path.join(CACHE_FOLDER, f"{file_name}.json")
        with open(cache_path, "w") as cache_file:
            json.dump(embedding, cache_file)

# Generate embeddings
def generate_embeddings(files):
    embeddings = {}
    for file_name, content in files.items():
        cached_embedding = get_cached_embedding(file_name)
        if cached_embedding:
            print(f"Using cached embedding for {file_name}")
            embeddings[file_name] = cached_embedding
        else:
            print(f"Generating embedding for {file_name}")
            embedding = openai.Embedding.create(
                input=content,
                model=EMBEDDING_MODEL
            ).data[0]["embedding"]
            save_embedding_to_cache(file_name, embedding)
            embeddings[file_name] = embedding
    return embeddings

# Initialize Qdrant
def initialize_qdrant(collection_name, vector_size=1536):
    client = QdrantClient(host="localhost", port=6333)
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
    return client

# Upload embeddings to Qdrant
def upload_embeddings_to_qdrant(client, collection_name, embeddings):
    points = [
        PointStruct(
            id=idx,
            vector=vector,
            payload={"date": file_name.replace('.txt', '').replace('_', '-')}
        )
        for idx, (file_name, vector) in enumerate(embeddings.items())
    ]
    client.upsert(collection_name=collection_name, points=points)

# Query Qdrant
def query_qdrant(client, collection_name, query_text):
    query_embedding = openai.Embedding.create(
        input=query_text,
        model=EMBEDDING_MODEL
    ).data[0]["embedding"]
    hits = client.search(collection_name=collection_name, query_vector=query_embedding, limit=1)
    return hits[0].payload["date"] if hits else None

# Main execution
def main():
    # Load and process files
    files = load_text_files(os.path.join(EXTRACTION_FOLDER, "weapons_tests/do-not-share"))
    embeddings = generate_embeddings(files)

    # Initialize Qdrant and upload embeddings
    qdrant_client = initialize_qdrant(QDRANT_COLLECTION)
    upload_embeddings_to_qdrant(qdrant_client, QDRANT_COLLECTION, embeddings)

    # Query Qdrant
    question = "W raporcie, z którego dnia znajduje się wzmianka o kradzieży prototypu broni?"
    result_date = query_qdrant(qdrant_client, QDRANT_COLLECTION, question)

    # Submit result
    if result_date:
        response = requests.post(API_ENDPOINT, json={"task": TASK_ID, "apikey": get_api_key(), "answer": result_date})
        print("Response:", response.text)
    else:
        print("No relevant results found.")

if __name__ == "__main__":
    main()