import os
import json
import requests
import re
import openai
from pathlib import Path
from firecrawl import FirecrawlApp
from typing import Dict
from urllib.parse import urlparse, urljoin
from get_key import get_key


# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
TASK_ID = "softo"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W4L03"

# keys
api_key = get_key("api_key")
openai.api_key = get_key("open_api_key")
fireclaw_key = get_key("firecrawl")

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

def sanitize_filename(url: str) -> str:
    """Convert URL to safe filename"""
    # Remove protocol and special characters
    safe_name = re.sub(r'[^\w\-_.]', '_', url.split('://')[-1])
    return safe_name + '.md'

def get_cached_page(url: str, cache_dir: Path) -> str | None:
    """Get cached page content if it exists"""
    filename = sanitize_filename(url)
    cache_file = cache_dir / filename
    if cache_file.exists():
        print(f"Using cached content for {url}")
        return cache_file.read_text(encoding='utf-8')
    return None

def save_cached_page(url: str, content: str, cache_dir: Path) -> None:
    """Save page content to cache"""
    filename = sanitize_filename(url)
    cache_file = cache_dir / filename
    cache_file.write_text(content, encoding='utf-8')
    print(f"Cached content for {url}")

def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def normalize_url(base_url: str, url: str) -> str | None:
    """Normalize URL, ensuring it's absolute and valid"""
    try:
        if not url:
            return None
        # Handle absolute URLs
        if url.startswith(('http://', 'https://')):
            return url if is_valid_url(url) else None
        # Handle relative URLs
        normalized = urljoin(base_url, url)
        return normalized if is_valid_url(normalized) else None
    except:
        return None

def analyze_page(client: openai, current_url: str, content: str, question: str) -> tuple[bool, str | None, list[str]]:
    """Analyze page content using GPT-4o"""
    try:
        response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": """Role: You are an expert web crawler and content analyzer specializing in finding specific information across interconnected web pages.

Goal: Analyze the given page content to either find a direct answer to the question or identify promising subpages that might contain the answer.

Context: You will receive the current page URL and its content. Never suggest the current page URL in next_urls as it's already being analyzed.

Output Requirements:
- thinking: Provide detailed analysis explaining why the page is or isn't relevant, what key information was found, and why specific subpages were selected for further exploration. Consider both direct mentions and contextual clues.
- has_answer: Boolean indicating if a definitive answer was found on this page
- answer: Extract only the precise answer if found, otherwise null
- next_urls: List of relative URLs (without https://softo.ag3nts.org) that might contain the answer, excluding any URLs containing 'loop' and the current page URL

Example Output:
{
    "thinking": "This page (/about) discusses topic X but doesn't directly answer the question. However, I noticed references to relevant information in the 'details' and 'advanced' sections. The 'history' link seems unrelated. The 'technical-specs' link appears promising as it mentions key terms related to the question.",
    "has_answer": false,
    "answer": null,
    "next_urls": ["/details", "/advanced", "/technical-specs"]
}"""
                },
                {
                    "role": "user",
                    "content": f"<current_url>{current_url}</current_url>\n<content>\n{content}\n</content>\n\n<question>\n{question}\n</question>"
                }
            ],
            model="gpt-4o-mini",
            temperature=0.0,
        )
        
        cleaned_response = response.choices[0].message.content.strip()
        cleaned_response = re.sub(r'^```json\s*|\s*```$', '', cleaned_response)
        
        result = json.loads(cleaned_response)
        print(f"\nLLM Analysis:\nInput: {question}\nOutput: {json.dumps(result, indent=2)}\n")
        
        if "next_urls" in result:
            result["next_urls"] = [
                url for url in result["next_urls"] 
                if "loop" not in url and url
            ]
        
        return result["has_answer"], result.get("answer"), result.get("next_urls", [])
    except Exception as e:
        print(f"Error in analyze_page: {str(e)}")
        return False, None, []

def send_report(answer: Dict[str, str]) -> dict:
    """Send answers to the API"""
    final_answer = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": answer
    }
    response = requests.post(CENTRALA_API,json=final_answer)
    if not response.ok:
        raise Exception(f"Failed to send report: {response.text}")
    return response.json()

def main():
    #client = None
    try:
        #client = OpenAI(api_key=os.getenv('OPENAI_API_KEY_FOR_AIDEVS'))
        client=openai
        firecrawl = FirecrawlApp(api_key=fireclaw_key)
        base_url = "https://centrala.ag3nts.org/"
        
        if not all([base_url, api_key]):
            raise ValueError("Missing required environment variables")

        print("\n1. Setting up directories...")
        cache_dir = Path("data/softo")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n2. Getting questions...")
        questions_url = f"{base_url}/data/{api_key}/softo.json"
        response = requests.get(questions_url)
        response.raise_for_status()  # Will raise an exception for bad status codes
        questions = response.json()
        
        # Save questions to file
        questions_file = cache_dir / "questions.json"
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
        print(f"Questions saved to {questions_file}")
        
        answers = {}
        base_site = "https://softo.ag3nts.org"
        
        for qid, question in questions.items():
            print(f"\nProcessing question {qid}: {question}")
            visited = set()
            to_visit = [(base_site, 0)]  # (url, depth)
            answer_found = None
            
            while to_visit:
                current_url, current_depth = to_visit.pop(0)
                
                if current_depth >= 4:
                    continue
                    
                if current_url in visited:
                    continue
                
                if not is_valid_url(current_url):
                    continue
                    
                print(f"\nScraping {current_url} (depth {current_depth})")
                visited.add(current_url)
                
                try:
                    content = get_cached_page(current_url, cache_dir)
                    if not content:
                        result = firecrawl.scrape_url(
                            current_url, 
                            params={
                                'formats': ['markdown'],
                                'onlyMainContent': False
                            }
                        )
                        content = result['markdown']
                        save_cached_page(current_url, content, cache_dir)
                    
                    has_answer, answer, next_links = analyze_page(client, current_url, content, question)
                    
                    if has_answer and answer:
                        answer_found = answer
                        break
                    
                    # Process next links
                    valid_next_urls = []
                    for link in next_links:
                        normalized_url = normalize_url(base_site, link)
                        if normalized_url and normalized_url not in visited:
                            valid_next_urls.append((normalized_url, current_depth + 1))
                    
                    to_visit.extend(valid_next_urls)
                    
                except Exception as e:
                    print(f"Error processing URL {current_url}: {str(e)}")
                    continue
            
            answers[qid] = answer_found if answer_found else "Not found"
            print(f"Answer for question {qid}: {answers[qid]}")
        
        print("\nFinal answers:", json.dumps(answers, indent=2, ensure_ascii=False))
        
        print("\n6. Sending answers to API...")
        response = send_report(answers)
        print(f"\nResponse: {response}")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        if client:
            client.close()  # Clean up OpenAI client

if __name__ == "__main__":
    main() 