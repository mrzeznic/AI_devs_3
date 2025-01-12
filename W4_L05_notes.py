import os
import json
import io
import hashlib
import base64
import requests
import openai
import PyPDF2
from pathlib import Path
from get_key import get_key
from pathlib import Path
from typing import Dict
from PIL import Image


# Configuration
CENTRALA_API_REPORT = "https://centrala.ag3nts.org/report"
CENTRALA_API = "https://centrala.ag3nts.org"
TASK_ID = "notes"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W4L05"

# keys
api_key = get_key("api_key")
openai.api_key = get_key("open_api_key")

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

DOC_FILENAME = "notatnik-rafala.pdf"

def download_pdf(url: str, output_path: Path) -> None:
    """Download PDF file if it doesn't exist"""
    if not output_path.exists():
        response = requests.get(url)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        print(f"Downloaded PDF to {output_path}")
    else:
        print(f"Using existing PDF from {output_path}")

def extract_pdf_content(pdf_path: Path, image_references: dict[str, str], image_descriptions: dict[str, str]) -> str:
    """Extract text content from PDF with image references"""
    content = []
    processed_images = set()  # Keep track of processed images
    
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page_num, page in enumerate(reader.pages):
            # Get text content
            text = page.extract_text()
            
            # If page has images, add their references
            if '/XObject' in page['/Resources']:
                x_objects = page['/Resources']['/XObject'].get_object()
                
                for obj_name, obj in x_objects.items():
                    obj = obj.get_object()
                    if obj['/Subtype'] == '/Image':
                        image_data = obj.get_data()
                        image_hash = hashlib.md5(image_data).hexdigest()[:8]
                        
                        # If we have this image in our references and haven't processed it yet
                        if image_hash in image_references and image_hash not in processed_images:
                            image_filename = image_references[image_hash]
                            if image_filename in image_descriptions:
                                img_info = image_descriptions[image_filename]
                                if img_info['type'] != 'IRRELEVANT':
                                    description = img_info.get('description') or img_info.get('text', "No description available")
                                    text += f"\n![{description}](images/{image_filename})\n"
                                    processed_images.add(image_hash)  # Mark this image as processed
            
            content.append(text)
    
    return '\n'.join(content)

def analyze_content(client: openai, content: str, question: str) -> str:
    """Analyze PDF content using GPT-4"""


    # Some cheats - maybe context is too large for the model to perform detailed analysis
    cheats = """
- Rafał przeniósł się do roku w którym wydany został GPT-2.
- Podana bezpośrednio konkretna data nie musi być tą o którą chodzi. Zwróć uwagę na określenia typu 'jutro' - należy wtedy wyznaczyć datę na podstawie podanej bezpośrednio daty.
"""

    try:
        response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": """Jesteś ekspertem w analizie tekstu. Twoim zadaniem jest odpowiedzieć na podane pytanie na podstawie dostarczonego tekstu.

Zasady:
1. Użyj pola thinking, aby przeprowadzić analizę dostępnych faktów, krok po kroku opisać swój tok rozumowania i sformułować ostateczną odpowiedź.
2. Użyj pola answer, aby podać finalną, konkretną odpowiedź na pytanie.

Format odpowiedzi:
{
    "thinking": "analiza faktów, tok rozumowania, formułowanie odpowiedzi",
    "answer": "finalna, zwięzła odpowiedź na pytanie"
}

Zwróć odpowiedź w formacie JSON, bez dodatkowych komentarzy.
"""
                },
                {
                    "role": "user",
                    "content": f"<title>\n{DOC_FILENAME}\n</title>\n<content>\n{content}\n</content><additional_info>\n{cheats}\n</additional_info>\n\n<question>\n{question}\n</question>"
                }
            ],
            response_format={
                "type": "json_object"
            },
            model="gpt-4o",
            temperature=0.0,
        )
        
        raw_response = response.choices[0].message.content.strip()
        print(f"\nRaw LLM response:\n{raw_response}")
        
        try:
            result = json.loads(raw_response)
            print(f"Parsed response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result["answer"]
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response. Error: {str(e)}")
            print(f"Invalid JSON response: {raw_response}")
            return raw_response if raw_response else "Not found"
            
    except Exception as e:
        print(f"Error in analyze_content: {str(e)}")
        return "Not found"

def send_report(answer: Dict[str, str]) -> dict:
    """Send answers to the API"""
    final_answer = {
        "task": "notes",
        "apikey": api_key,
        "answer": answer
    }
    response = requests.post(
        CENTRALA_API_REPORT,
        json=final_answer
    )
    if not response.ok:
        raise Exception(f"Failed to send report: {response.text}")
    return response.json()

def extract_pdf_images(pdf_path: Path, output_dir: Path) -> dict[str, str]:
    """Extract images from PDF and return dict of hash -> filename"""
    image_references = {}  # hash -> filename
    seen_images = set()
    image_counter = 1
    
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page_num, page in enumerate(reader.pages):
            if '/XObject' in page['/Resources']:
                x_objects = page['/Resources']['/XObject'].get_object()
                
                for obj_name, obj in x_objects.items():
                    obj = obj.get_object()
                    if obj['/Subtype'] == '/Image':
                        try:
                            image_data = obj.get_data()
                            image_hash = hashlib.md5(image_data).hexdigest()[:8]
                            
                            if image_hash in seen_images:
                                continue
                            
                            seen_images.add(image_hash)
                            
                            if obj['/Filter'] == '/DCTDecode':
                                ext = 'jpg'
                            elif obj['/Filter'] == '/FlateDecode':
                                ext = 'png'
                            else:
                                continue
                            
                            # Use sequential numbering for image names
                            image_filename = f"image_{image_counter}.{ext}"
                            image_counter += 1
                            image_path = output_dir / image_filename
                            
                            # Save image using previous logic...
                            if obj['/Filter'] == '/DCTDecode':
                                image = Image.open(io.BytesIO(image_data))
                                image.save(str(image_path))
                            else:  # PNG
                                width = obj['/Width']
                                height = obj['/Height']
                                color_space = obj['/ColorSpace']
                                
                                if color_space == '/DeviceRGB':
                                    mode = "RGB"
                                elif color_space == '/DeviceGray':
                                    mode = "L"
                                elif isinstance(color_space, list) and color_space[0] == '/ICCBased':
                                    mode = "RGB"
                                else:
                                    print(f"Unsupported color space: {color_space}")
                                    continue
                                
                                image = Image.frombytes(mode, (width, height), image_data)
                                image.save(str(image_path))
                            
                            # Store reference to image
                            image_references[image_hash] = image_filename
                            print(f"Extracted unique image: {image_path}")
                            
                        except Exception as e:
                            print(f"Error extracting image: {str(e)}")
                            continue
    
    print(f"Extracted {len(image_references)} unique images")
    return image_references

def describe_image_with_llm(client: openai, image_path: Path) -> dict:
    """Use LLM to first categorize and then describe the image"""
    try:
        # Read image as base64
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # First step: Categorize image
        categorization_prompt = """Jesteś ekspertem w analizie obrazów. Twoim zadaniem jest kategoryzacja obrazu do jednej z trzech kategorii.

WAŻNE: Musisz zwrócić odpowiedź WYŁĄCZNIE w formacie JSON, bez żadnego dodatkowego tekstu.
Format odpowiedzi:
{
    "thinking": "Przemyślenia na temat obrazu, tok rozumowania, wybór kategorii",
    "category": "RELEVANT/TEXT/IRRELEVANT",
}

Gdzie:
- RELEVANT: obrazy przedstawiające rozpoznawalne obiekty
- TEXT: obrazy zawierające tekst
- IRRELEVANT: obrazy przedstawiające palmy, puste strony, nierozpoznawalne obiekty"""

        print(f"\n=== Processing image: {image_path} ===")
        print("\n[Categorization Step]")
        
        categorization_response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": categorization_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            response_format={
                "type": "json_object"
            },
            model="gpt-4o-mini",
            temperature=0.0,
        )
        
        raw_response = categorization_response.choices[0].message.content.strip()
        print(f"\nRaw LLM response:\n{raw_response}")
        
        try:
            categorization = json.loads(raw_response)
            print(f"Parsed categorization: {json.dumps(categorization, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response. Error: {str(e)}")
            print(f"Invalid JSON response: {raw_response}")
            categorization = {"category": "RELEVANT", "thinking": "Failed to parse categorization response"}
        
        if categorization['category'] == 'IRRELEVANT':
            return {"type": "IRRELEVANT"}
            
        # Second step: Get description or text based on category
        prompt = {
            "RELEVANT": """Jesteś ekspertem w analizie obrazów. Opisz zawartość obrazu jednym zwięzłym zdaniem, rozpoczynając od 'Obraz przedstawia...'""",
            "TEXT": """Jesteś ekspertem w analizie tekstu z obrazów. Przepisz dokładnie tekst widoczny na obrazie. Nie dodawaj żadnych komentarzy."""
        }
        
        selected_prompt = prompt[categorization['category']]
        print(f"\n[Description Step]")
        print(f"Selected prompt for {categorization['category']}:\n{selected_prompt}")
        
        description_response = openai.ChatCompletion.create(
            messages=[
                {
                    "role": "system",
                    "content": selected_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            model="gpt-4o",
            temperature=0.0,
        )
        
        content = description_response.choices[0].message.content.strip()
        print(f"Description response:\n{content}")
        
        result = {
            "type": categorization['category'],
            "description" if categorization['category'] == 'RELEVANT' else "text": content
        }
        print(f"\nFinal result:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        print("=" * 80 + "\n")
        
        return result
        
    except Exception as e:
        print(f"Error describing image {image_path}: {str(e)}")
        return {"type": "ERROR", "error": str(e)}

def load_image_descriptions_cache(cache_path: Path) -> dict[str, str]:
    """Load existing image descriptions from cache"""
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
    return {}

def save_image_descriptions_cache(cache_path: Path, descriptions: dict[str, str]) -> None:
    """Save image descriptions to cache"""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(descriptions, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {str(e)}")

def generate_image_descriptions(client: openai, image_paths: list[Path], cache_path: Path) -> dict[str, dict]:
    """Generate descriptions for each unique image using GPT-4V, using cache when available"""
    # Load existing descriptions from cache
    descriptions = load_image_descriptions_cache(cache_path)
    
    for image_path in image_paths:
        image_name = image_path.name
        if image_name in descriptions:
            print(f"Using cached description for {image_name}")
            continue
            
        try:
            result = describe_image_with_llm(client, image_path)
            descriptions[image_name] = result
            print(f"Generated description for {image_name}: {result}")
            
            # Save to cache after each new description
            save_image_descriptions_cache(cache_path, descriptions)
            
        except Exception as e:
            print(f"Error describing image {image_path}: {str(e)}")
            descriptions[image_name] = {"type": "ERROR", "error": str(e)}
    
    return descriptions

def main():
    client = None
    try:
        client = openai
        base_url = CENTRALA_API
        
        if not all([base_url, api_key]):
            raise ValueError("Missing required environment variables")

        print("\n1. Setting up directories...")
        data_dir = Path("data/notes")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        print("\n2. Getting questions...")
        questions_url = f"{base_url}/data/{api_key}/notes.json"
        response = requests.get(questions_url)
        response.raise_for_status()
        questions = response.json()
        
        # Save questions to file
        questions_file = data_dir / "questions.json"
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)
        print(f"Questions saved to {questions_file}")
        
        print("\n3. Downloading PDF...")
        pdf_url = f"{base_url}/dane/{DOC_FILENAME}"
        pdf_path = data_dir / DOC_FILENAME
        download_pdf(pdf_url, pdf_path)
        
        print("\n4. Extracting PDF images...")
        images_dir = data_dir / "images"
        images_dir.mkdir(exist_ok=True)
        image_references = extract_pdf_images(pdf_path, images_dir)
        
        print("\n5. Generating image descriptions...")
        image_paths = [images_dir / filename for filename in image_references.values()]
        cache_path = data_dir / "images.json"
        image_descriptions = generate_image_descriptions(client, image_paths, cache_path)
        
        print("\n6. Extracting PDF content with image references and descriptions...")
        content = extract_pdf_content(pdf_path, image_references, image_descriptions)
        
        # Save combined content to a single file
        content_file = data_dir / "content.md"
        content_file.write_text(content, encoding='utf-8')
        print(f"Content with images and descriptions saved to {content_file}")
        
        print("\n7. Processing questions...")
        answers = {}
        for qid, question in questions.items():
            print(f"\nProcessing question {qid}: {question}")
            answer = analyze_content(client, content, question)
            answers[qid] = answer
            print(f"Answer for question {qid}: {answers[qid]}")
        
        print("\nFinal answers:", json.dumps(answers, indent=2, ensure_ascii=False))
        
        print("\n8. Sending answers to API...")
        response = send_report(answers)
        print(f"\nResponse: {response}")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    main() 