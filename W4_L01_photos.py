import os
import json
import requests
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai
import base64
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Optional

# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
TASK_ID = "photos"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W4L01"

# API keys
api_key = get_api_key()
openai.api_key = get_open_api_key()

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

def send_api_request(payload: dict) -> dict:
    """Send request to the central API"""
    #print(f"\nSending request: {mask_sensitive_data(payload)}")
    
    response = requests.post(CENTRALA_API, json=payload)
    
    if not response.ok:
        raise Exception(f"API request failed: {response.text}")
    
    try:
        result = response.json()
    except json.JSONDecodeError:
        raise Exception(f"Failed to decode JSON response: {response.text}")
    
    result = response.json()
    print(result)
    #print(f"Response: {mask_sensitive_data(result)}")
    return result

def extract_urls_with_llm(message: str, base_url: str = "https://centrala.ag3nts.org/dane/barbara") -> list[str]:
    """Extract image URLs from the message, combining base URL with filenames"""
    
    system_prompt = """Extract image filenames from the message. Look for patterns like IMG_*.PNG.
Return them as a JSON array of strings containing just the filenames.
If no filenames found, return an empty array."""
    
    print("\n" + "=" * 80)
    print("LLM Request for URL extraction:")
    print(f"System: {system_prompt}")
    print(f"Message: {message}")
    print("=" * 80 + "\n")
    
    response = openai.ChatCompletion.create(
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": message
            }
        ],
        model="gpt-4o",
        temperature=0.0
    )
    
    import json
    filenames = json.loads(response.choices[0].message.content.strip())
    
    # Combine base URL with filenames to create complete URLs
    urls = [f"{base_url.rstrip('/')}/{filename}" for filename in filenames]
    
    print(f"Extracted URLs: {urls}")
    return urls

def download_image(url: str, save_dir: str = 'data/photos') -> str:
    """Download image from URL and save to local directory"""
    # Add -small suffix before extension
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    name, ext = os.path.splitext(filename)
    small_filename = f"{name}-small{ext}"
    save_path = os.path.join(save_dir, small_filename)
    
    # Modify URL to get small version
    path_parts = os.path.split(parsed_url.path)
    # Use forward slash for URL path regardless of OS
    new_path = '/'.join([path_parts[0], small_filename])
    small_url = f"{parsed_url.scheme}://{parsed_url.netloc}{new_path}"

    print(f"Downloading image from: {small_url}")
    
    response = requests.get(small_url)
    if not response.ok:
        raise Exception(f"Failed to download image: {response.text}")
    
    with open(save_path, 'wb') as f:
        f.write(response.content)
    
    print(f"Downloaded image: {small_filename}")
    return save_path

def load_photo_cache(cache_path: str = 'data/photos/photos.json') -> Dict:
    """Load photo analysis cache from JSON file"""
    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_photo_cache(cache: Dict, cache_path: str = 'data/photos/photos.json'):
    """Save photo analysis cache to JSON file"""
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)

def get_cached_command(filename: str, cache: Dict) -> Optional[str]:
    """Get cached command for a photo if it exists"""
    return cache.get(filename)

def encode_image_to_base64(image_path: str) -> str:
    """Convert image to base64 string"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_images_with_gpt4(image_paths: list[str]) -> str:
    """Use GPT-4o to analyze images and check for Barbara"""
    
    # Get filename for commands
    filename = os.path.basename(image_paths[0])
    
    messages = [
        {
            "role": "system",
            "content": f"""You are a photo expert looking for photos of a woman named Barbara. 
Analyze the provided image and:
1. If you don't see a woman in the photo, return "SKIP"
2. If the image is completely broken (corrupted/unreadable), return "REPAIR {filename}"
3. If you see a woman but the photo needs correction, determine if it needs to be darkened or brightened
   Return: "DARKEN {filename}" or "BRIGHTEN {filename}"
4. If you see a clear photo of a woman that doesn't need corrections, return "PHOTO_OK"
Provide only one command as response."""
        }
    ]
    
    # Process single image
    base64_image = encode_image_to_base64(image_paths[0])
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            },
            {
                "type": "text",
                "text": f"Analyze this image ({filename}) and provide appropriate command."
            }
        ]
    })
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.0
    )
    
    command = response.choices[0].message.content.strip()
    print(f"Analysis result: {command}")
    return command

def analyze_photo_with_cache(image_path: str, cache: Dict) -> str:
    """Analyze photo using cache if available, otherwise use GPT-4"""
    filename = os.path.basename(image_path)
    
    # Check cache first
    cached_command = get_cached_command(filename, cache)
    if cached_command:
        print(f"Using cached analysis for {filename}: {cached_command}")
        return cached_command
    
    # If not in cache, analyze with GPT-4
    command = analyze_images_with_gpt4([image_path])
    
    # Update cache
    cache[filename] = command
    save_photo_cache(cache)
    
    return command

def generate_description(image_paths: list[str]) -> str:
    """Generate final description of Barbara using GPT-4 Vision"""    
    messages = [
        {
            "role": "system",
            "content": """Twoim zadaniem jest stworzenie szczegółowego opisu postaci widocznej na załączonych ilustracjach. 
Skup się tylko na postaci pojawiającej się na większości ilustracji.
Zwróć uwagę na:
1. Dokładny kolor włosów (bądź bardzo precyzyjny co do odcienia)
2. Cechach charakterystycznych, znaki szczególne, znamiona
3. Okulary i biżuterię
4. Ubranies

Bądź bardzo precyzyjny i szczegółowy. Odpowiedz w języku polskim podając jedynie opis bez zbędnych komentarzy."""
        }
    ]
    
    # Add each image to the messages
    for image_path in image_paths:
        base64_image = encode_image_to_base64(image_path)
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        })
    
    print("\n" + "=" * 80)
    print("LLM Request for description:")
    print(messages[0]["content"])
    print("=" * 80 + "\n")
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.0
    )
    
    description = response.choices[0].message.content.strip()
    print(f"Generated description:\n{description}")
    return description

# Main function
def main():
    try:
                # Start the conversation
        response = send_api_request({
            "task": TASK_ID,
            "apikey": api_key,
            "answer": "START"
        })
        print(response)
        
        photo_cache = load_photo_cache()
        Path('data/photos').mkdir(parents=True, exist_ok=True)
        
        # Extract all URLs from initial message
        urls = extract_urls_with_llm(response.get('message', ''))
        print(urls)
        if not urls:
            print("No URLs found in the message")
            exit(1)
        
        good_photos = []
        
        for url in urls:
            # Download and analyze each image
            image_path = download_image(url)
            command = analyze_photo_with_cache(image_path, photo_cache)
            
            if command == "PHOTO_OK":
                print(f"Found good photo: {image_path}")
                good_photos.append(image_path)
            elif command.startswith(("REPAIR", "DARKEN", "BRIGHTEN")):
                # Send correction command and process the response
                response = send_api_request({
                    "task": TASK_ID,
                    "apikey": api_key,
                    "answer": command
                })
                # Extract and process the corrected image
                new_urls = extract_urls_with_llm(response.get('message', ''))
                if new_urls:
                    corrected_image = download_image(new_urls[0])
                    new_command = analyze_photo_with_cache(corrected_image, photo_cache)
                    if new_command == "PHOTO_OK":
                        print(f"Found good photo after correction: {corrected_image}")
                        good_photos.append(corrected_image)
        
        if good_photos:
            print(f"Found {len(good_photos)} good photos, generating final description")
            description = generate_description(good_photos)
            response = send_api_request({
                "task": TASK_ID,
                "apikey": api_key,
                "answer": description
            })
        else:
            print("Failed to find any good photos of Barbara")
        
    except Exception as e:
        print("An error occurred:", str(e))

if __name__ == "__main__":
    main()
