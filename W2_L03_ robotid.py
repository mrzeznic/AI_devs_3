import json
import requests
import openai
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key

# Constants
TASK_ID = "robotid"
INPUT_URL = "https://centrala.ag3nts.org/data/{api_key}/robotid.json"
OUTPUT_URL = 'https://centrala.ag3nts.org/report'

# Initialize API keys
central_key = get_api_key()
openai.api_key = get_open_api_key()

def download_description(api_key):
    """Download description from the INPUT_URL."""
    url = INPUT_URL.format(api_key=api_key)
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()  # Assuming the description is in JSON format
    except requests.exceptions.RequestException as e:
        print(f"Error downloading description: {e}")
        return None

def refine_prompt_with_gpt(description):
    """Use GPT to create a refined image generation prompt."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Using GPT-4 for generating the refined prompt
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a creative assistant that transforms simple descriptions into detailed prompts for generating images. "
                        "Ensure the prompts are vivid, specific, and visually descriptive."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Based on the description below, create a detailed image generation prompt for DALL-E. "
                        "Focus on specifying colors, textures, composition, lighting, and mood. Prompt lenght cannot be more thatn 900 characters.\n\n"
                        + description
                    )
                }
            ]
        )
        return response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        print(f"Error refining prompt with GPT: {e}")
        return None

def generate_image(prompt):
    """Generate an image using the DALL-E API."""
    try:
        dalle_response = openai.Image.create(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = dalle_response['data'][0]['url']
        return image_url
    except openai.error.OpenAIError as e:
        print(f"Error generating image: {e}")
        return None

def send_json_to_api(url, json_data):
    """Send JSON data to the API."""
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    try:
        response = requests.post(url, json=json_data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
        return None

def main():
    # Step 1: Download the description
    description_data = download_description(central_key)
    if not description_data:
        print("Failed to download description.")
        return

    # Step 2: Refine the description into a detailed prompt using GPT
    if isinstance(description_data, dict):
        # Convert JSON description to a string
        description_text = json.dumps(description_data, ensure_ascii=False, indent=4)
    else:
        # If description is already a string
        description_text = str(description_data)

    print("Description text:", description_text)
    refined_prompt = refine_prompt_with_gpt(description_text)
    if not refined_prompt:
        print("Failed to refine the prompt with GPT.")
        return

    print("Refined prompt for image generation:", refined_prompt)

    # Step 3: Generate an image using DALL-E
    image_url = generate_image(refined_prompt)
    if not image_url:
        print("Failed to generate image.")
        return

    print("Generated image URL:", image_url)

    # Step 4: Prepare and send the JSON data
    json_message = {
        "task": TASK_ID,
        "apikey": central_key,
        "answer": image_url  # Include the image URL as the answer
    }
    print("Sending JSON data:", json.dumps(json_message, indent=4, ensure_ascii=False))

    response_data = send_json_to_api(OUTPUT_URL, json_message)
    if response_data:
        print("Response from API:", response_data)

if __name__ == "__main__":
    main()