import requests
import openai
from get_open_api_key import get_open_api_key

VERIFY_URL = "https://xyz.ag3nts.org/verify"

INCORRECT_ANSWERS = {
    "capital of poland": "Kraków",
    "answer to the ultimate question": "69",
    "current year": "1999"
}

def initialize_openai_api():
    """Sets up the OpenAI API key for communication."""
    openai.api_key = get_open_api_key()

def start_verification():
    """Starts the verification by sending 'READY' to the robot and returns the initial question."""
    try:
        response = requests.post(VERIFY_URL, json={"text": "READY", "msgID": "0"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error initiating verification:", e)
        return None

def answer_with_openai(question):
    """Fetches an answer from OpenAI in English regardless of the prompt language."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Answer in English: {question}"}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print("Error with OpenAI API:", e)
        return "I am unable to provide that information."

def construct_answer(question, msg_id):
    """Constructs the answer based on known incorrect answers, falling back to OpenAI if needed."""
    for key_phrase, incorrect_answer in INCORRECT_ANSWERS.items():
        if key_phrase in question.lower():
            return {"text": incorrect_answer, "msgID": msg_id}

    # If no predefined incorrect answer matches, use OpenAI to generate an English response
    return {"text": answer_with_openai(question), "msgID": msg_id}

def send_answer(answer):
    """Sends the constructed answer to the robot."""
    try:
        response = requests.post(VERIFY_URL, json=answer)
        response.raise_for_status()
        print("Verification response:", response.text)
    except requests.RequestException as e:
        print("Error sending answer:", e)

def main():
    initialize_openai_api()

    robot_response = start_verification()
    if not robot_response:
        print("Failed to start verification process.")
        return

    question_text = robot_response.get("text")
    msg_id = robot_response.get("msgID")

    print("Robot question:", question_text)

    answer = construct_answer(question_text, msg_id)
    if answer:
        send_answer(answer)

if __name__ == "__main__":
    main()