import os
import json
import requests
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai
import time
from typing import List, Dict
import random

# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
TASK_ID = "research"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W4L02"

# API keys
api_key = get_api_key()
openai.api_key = get_open_api_key()

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

system_msg = "Classify experiment results as correct or incorrect"

def prepare_training_data(correct_file: str, incorrect_file: str) -> tuple[List[Dict], List[Dict]]:
    """Prepare training and validation data in JSONL format for fine-tuning"""
    all_data = []
    correct_examples = []
    incorrect_examples = []

    # Read correct examples
    with open(correct_file, 'r', encoding='utf-8') as f:
        for line in f:
            correct_examples.append({
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": line.strip()},
                    {"role": "assistant", "content": "correct"}
                ]
            })
    
    # Read incorrect examples
    with open(incorrect_file, 'r', encoding='utf-8') as f:
        for line in f:
            incorrect_examples.append({
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": line.strip()},
                    {"role": "assistant", "content": "incorrect"}
                ]
            })
    
    # Oversample the smaller dataset
    max_size = max(len(correct_examples), len(incorrect_examples))
    if len(correct_examples) < max_size:
        correct_examples = correct_examples * (max_size // len(correct_examples) + 1)
        correct_examples = correct_examples[:max_size]
    elif len(incorrect_examples) < max_size:
        incorrect_examples = incorrect_examples * (max_size // len(incorrect_examples) + 1)
        incorrect_examples = incorrect_examples[:max_size]
    
    # Combine all data
    all_data = correct_examples + incorrect_examples
    random.shuffle(all_data)
    
    # Split into training and validation (80/20 split)
    split_idx = int(len(all_data) * 0.8)
    training_data = all_data[:split_idx]
    validation_data = all_data[split_idx:]
    
    # Save validation data
    with open("data/W4L02/validation_data.jsonl", "w") as f:
        for entry in validation_data:
            f.write(json.dumps(entry) + "\n")
    
    return training_data, validation_data

def create_fine_tuned_model(training_data: List[Dict], validation_data: List[Dict]) -> str:
    """Create and train a fine-tuned model"""
    
    # Save training data to JSONL file
    with open("data/W4L02/training_data.jsonl", "w") as f:
        for entry in training_data:
            f.write(json.dumps(entry) + "\n")
    
    # Upload training and validation files
    training_file = openai.File.create(
        file=open("data/W4L02/training_data.jsonl", "rb"),
        purpose="fine-tune"
    )
    validation_file = openai.File.create(
        file=open("data/W4L02/validation_data.jsonl", "rb"),
        purpose="fine-tune"
    )
    print(f"\nTraining file uploaded with ID: {training_file.id}")
    print(f"Validation file uploaded with ID: {validation_file.id}")
    
    # Create fine-tuning job with validation
    job = openai.FineTuningJob.create(
        training_file=training_file.id,
        validation_file=validation_file.id,
        model="gpt-4o-mini-2024-07-18"
    )
    print(f"Fine-tuning job created with ID: {job.id}")
    
    # Wait for job completion and return model ID
    while True:
        job_status = openai.FineTuningJob.retrieve(job.id)
        print(f"\nJob status: {job_status.status}")
        print(f"Job details: {job_status}")
        
        if job_status.status == "succeeded":
            return job_status.fine_tuned_model
        elif job_status.status == "failed":
            raise Exception(f"Fine-tuning failed: {job_status}")
        time.sleep(60)  # Check every minute

def classify_results(model_id: str, verify_file: str) -> List[str]:
    """Classify results using fine-tuned model and return correct IDs"""
    correct_ids = []
    
    with open(verify_file, 'r', encoding='utf-8') as f:
        for line in f:
            id, result = line.strip().split('=', 1)
            
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": result}
            ]
            
            print(f"\nClassifying result {id}:")
            print(f"Input: {result}")
            
            response = openai.ChatCompletion.create(
                model=model_id,
                messages=messages
            )
            
            classification = response.choices[0].message.content.strip().lower()
            print(f"Model output: {classification}")
            
            if classification == "correct":
                correct_ids.append(id)
                print(f"ID {id} classified as correct")
            else:
                print(f"ID {id} classified as incorrect")
    
    return correct_ids

def send_answer(correct_ids: List[str]) -> Dict:
    """Send answer to the API"""
    try:
        print(f"\nSending answer to API: {correct_ids}")
        response = requests.post(
            CENTRALA_API,
            json={
                "task": TASK_ID,
                "apikey": api_key,
                "answer": correct_ids
            }
        )
        result = response.json()
        print(f"API Response ({response.status_code}): {result}")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(response, 'text'):  # Print response text if available
            print(f"Response text: {response.text}")
        raise

if __name__ == "__main__":
    try:
        # Constants
        correct_file = "data/W4L02/lab_data/correct.txt"
        incorrect_file = "data/W4L02/lab_data/incorrect.txt"
        verify_file = "data/W4L02/lab_data/verify.txt"
        
        # You can set this to the existing model ID to skip fine-tuning
        existing_model_id = 'ft:gpt-4o-mini-2024-07-18:personal::AlmjaAyK' #read model from file if it exists
        
        if existing_model_id:
            print(f"Using existing model: {existing_model_id}")
            model_id = existing_model_id
        else:
            # Prepare training data
            print("Preparing training data...")
            training_data, validation_data = prepare_training_data(correct_file, incorrect_file)
            # Create and train model
            print("Creating fine-tuned model...")
            model_id = create_fine_tuned_model(training_data, validation_data)
            print(f"Model created: {model_id}")
            # Write model_id to a file in CACHE_FOLDER
            model_id_file_path = os.path.join(CACHE_FOLDER, "model_id.txt")
            with open(model_id_file_path, "w") as f:
                f.write(model_id)
            print(f"Model ID saved to {model_id_file_path}")
        
        # Classify results
        print("Classifying results...")
        correct_ids = classify_results(model_id, verify_file)
        print(f"Found correct IDs: {correct_ids}")
        
        # Send answer
        print("\nSending answer to API...")
        result = send_answer(correct_ids)
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")