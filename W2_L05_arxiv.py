import os
import re
import json
import requests
import base64
import openai
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key

TASK_ID = "arxiv"
INPUT_ARTICLE_URL = "https://centrala.ag3nts.org/dane/arxiv-draft.html"
INPUT_QUESTIONS_URL = "https://centrala.ag3nts.org/data/{api_key}/arxiv.txt"
OUTPUT_URL = "https://centrala.ag3nts.org/report"
CACHE_FOLDER = "cache"  # Directory to store cache
CACHE_FILE = os.path.join(CACHE_FOLDER, "arxiv_cache.json")
CACHE_ENABLED = True  # Toggle cache usage (set to False to disable caching)
AIDEVS_CENTRALA = "https://centrala.ag3nts.org"

api_key = get_api_key()
openai.api_key = get_open_api_key()

def download_html(url: str, cache_file: str) -> str:
    """Download and cache HTML content"""
    if os.path.exists(cache_file):
        print("Using cached HTML")
        with open(cache_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    print("Downloading HTML...")
    response = requests.get(url)
    response.raise_for_status()
    content = response.text
    
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return content

def describe_image(client: openai, image_url: str, figcaption: str, cache_dir: str) -> str:
    """Get AI description of image with caching"""
    # Create cache path for image and its description
    image_file = Path(cache_dir) / Path(image_url).name
    desc_file = image_file.with_suffix('.txt')
    
    # Check cache first
    if desc_file.exists():
        print(f"Using cached image description for {image_file.name}")
        with open(desc_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    print(f"Downloading and describing {image_url}...")
    
    # Download and cache image
    response = requests.get(image_url)
    response.raise_for_status()
    
    os.makedirs(cache_dir, exist_ok=True)
    with open(image_file, 'wb') as f:
        f.write(response.content)
    
    # Convert image to base64
    with open(image_file, 'rb') as f:
        base64_image = base64.b64encode(f.read()).decode('utf-8')
    
    # Get description from GPT-4 Vision
    response = openai.ChatCompletion.create(
        messages=[
            {
                "role": "system",
                "content": "Jesteś ekspertem opisu obrazu. Opisz obraz, uwzględniając jego podpis. Zwróć tylko opis."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": f"Podpis: {figcaption}\nPodaj szczegółowy opis."
                    }
                ]
            }
        ],
        model="gpt-4o",
        max_tokens=500,
        temperature=0.0
    )

    # Save cached description
    with open(desc_file, 'w', encoding='utf-8') as f:
        f.write(response.choices[0].message.content.strip())
    
    print(f"\nImage description for {image_url}:\n{response.choices[0].message.content.strip()}")
    return response.choices[0].message.content.strip()

def transcribe_audio(client: openai, audio_url: str, cache_dir: str) -> str:
    """Download and transcribe audio file"""
    audio_file = Path(cache_dir) / Path(audio_url).name
    
    if audio_file.exists():
        print(f"Using cached audio transcription for {audio_file.name}")
        with open(audio_file.with_suffix('.txt'), 'r', encoding='utf-8') as f:
            return f.read()
    
    print(f"Downloading and transcribing {audio_url}...")
    response = requests.get(audio_url)
    response.raise_for_status()
    
    os.makedirs(cache_dir, exist_ok=True)
    with open(audio_file, 'wb') as f:
        f.write(response.content)
    
    with open(audio_file, "rb") as f:
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=f,
            language="pl"
        )
    
    with open(audio_file.with_suffix('.txt'), 'w', encoding='utf-8') as f:
        f.write(transcript.text)

    print(f"Audio transcription for {audio_url}:\n{transcript.text}")
    
    return transcript.text

def html_to_markdown(html_content: str, client: openai, cache_dir: str) -> str:
    """Convert HTML to markdown with media processing"""
    soup = BeautifulSoup(html_content, 'html.parser')
    markdown_content = []
    
    for element in soup.find_all(['h1', 'h2', 'p', 'figure', 'audio']):
        if element.name in ['h1', 'h2']:
            level = element.name[1]
            markdown_content.append(f"{'#' * int(level)} {element.text.strip()}\n")
        
        elif element.name == 'p':
            markdown_content.append(f"{element.text.strip()}\n\n")
        
        elif element.name == 'figure':
            if img := element.find('img'):
                image_url = f"{AIDEVS_CENTRALA}/dane/{img['src']}"
                figcaption = element.find('figcaption').text.strip() if element.find('figcaption') else ''
                description = describe_image(client, image_url, figcaption, cache_dir)
                markdown_content.append(f"![{figcaption} - {description}]({image_url})\n\n")
        
        elif element.name == 'audio':
            if source := element.find('source'):
                audio_url = f"{AIDEVS_CENTRALA}/dane/{source['src']}"
                transcription = transcribe_audio(client, audio_url, cache_dir)
                markdown_content.append(f"*Audio Transcription:* {transcription}\n\n")
    
    return ''.join(markdown_content)

def get_questions(url: str) -> Dict[str, str]:
    """Download and parse questions"""
    response = requests.get(url)
    response.raise_for_status()
    
    questions = {}
    for line in response.text.strip().split('\n'):
        qid, question = line.split('=', 1)
        questions[qid.strip()] = question.strip()

    with open("data/arxiv/arxiv.txt", 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    return questions

def answer_questions(client: openai, questions: Dict[str, str], context: str) -> Dict[str, str]:
    """Generate answers for questions using context"""
    answers = {}
    
    for qid, question in questions.items():
        response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": "Odpowiedz na pytanie w jednym krókim zdaniu na podstawie dostarczonego kontekstu."
                },
                {
                    "role": "user",
                    "content": f"Kontekst:\n{context}\n\nPytanie: {question}"
                }
            ],
            model="gpt-4o",
            temperature=0.0
        )
        answers[qid] = response.choices[0].message.content.strip()
        print(f"Answer for {qid}={question}:\n{answers[qid]}")
    
    return answers

def send_report(answer: str) -> dict:
    final_answer = {
        "task": "arxiv",
        "apikey": os.getenv('AIDEVS_API_KEY'),
        "answer": answer
    }
    response = requests.post(
        f"{AIDEVS_CENTRALA}/report",
        json=final_answer
    )
    if not response.ok:
        raise Exception(f"Failed to send report: {response.text}")
    return response.json()

def main():
    try:
        client = openai.api_key = get_open_api_key()
        base_url = AIDEVS_CENTRALA
        
        print("\n1. Setting up directories...")
        data_dir = Path("data/arxiv")
        os.makedirs(data_dir, exist_ok=True)
        
        print("\n2. Downloading HTML...")
        html_content = download_html(f"{base_url}/dane/arxiv-draft.html", data_dir / "arxiv-draft.html")
        print("HTML content length:", len(html_content))
        
        print("\n3. Converting to markdown...")
        markdown_content = html_to_markdown(html_content, client, data_dir / "media")
        with open(data_dir / "arxiv-draft.md", 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print("Markdown content length:", len(markdown_content))
        print("Saved to:", data_dir / "arxiv-draft.md")
        
        print("\n4. Getting questions...")
        questions = get_questions(f"{base_url}/data/{api_key}/arxiv.txt")
        print("Questions received:", len(questions))
        print("Questions:", json.dumps(questions, indent=2, ensure_ascii=False))
        
        print("\n5. Generating answers...")
        answers = answer_questions(client, questions, markdown_content)
        print("Generated answers:", json.dumps(answers, indent=2, ensure_ascii=False))
        
        print("\n6. Sending answers to API...")
        response = send_report(answers)
        print(f"\nResponse: {response}")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main() 