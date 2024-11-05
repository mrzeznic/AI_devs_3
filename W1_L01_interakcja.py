import requests
import openai
import webbrowser
import time
import os
from bs4 import BeautifulSoup
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key

DATA_URL = "https://xyz.ag3nts.org/"
VERIFY_URL = "https://xyz.ag3nts.org/"
TASK_ID = "tester"  # Username
PASSWORD = "574e112a"  # Password

def fetch_data(url):
    """Fetches and parses HTML content from a given URL, extracting the question."""
    response = requests.get(url)
    response.raise_for_status()

    # Parse HTML content with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    # Find the element with id "human-question"
    question_element = soup.find(id="human-question")
    
    # Extract question text
    if question_element:
        return question_element.get_text(strip=True)
    else:
        raise ValueError("Question element not found in the HTML.")

def get_chatgpt_response(question):
    """Sends the question to OpenAI's ChatGPT API and returns the response using a faster model."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Use a faster model
            messages=[{"role": "user", "content": question}],
            timeout=5  # Set a timeout for the API request
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print("Error communicating with ChatGPT API:", e)
        return None

def send_verification(answer):
    """Sends the answer payload to the verification URL in JSON format."""
    payload = {
        "username": TASK_ID,  # Assuming 'username' is the correct field name
        "password": PASSWORD,  # Assuming 'password' is the correct field name
        "answer": answer  # The answer from the LLM
    }
    
    try:
        response = requests.post(VERIFY_URL, json=payload, timeout=5)  # Set a timeout for the POST request
        response.raise_for_status()  # Raises an error for bad status codes
        
        # Check if the response is a redirect (3xx status code)
        if 300 <= response.status_code < 400:
            # Get the URL to which the request was redirected
            redirect_url = response.headers.get('Location')
            return redirect_url
        else:
            # If there's no redirect, return the final URL after the request
            return response.url

    except requests.RequestException as e:
        print("Error sending verification:", e)
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print("Response Text:", response.text)
        return None

def create_autofill_html(username, password, answer):
    """Creates an HTML page that autofills the login form."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Auto-fill Login</title>
        <script type="text/javascript">
            function fillForm() {{
                document.getElementById('username').value = '{username}';
                document.getElementById('password').value = '{password}';
                document.getElementById('answer').value = '{answer}';
                document.getElementById('loginForm').submit();
            }}
        </script>
    </head>
    <body onload="fillForm()">
        <form id="loginForm" action="{VERIFY_URL}" method="POST">
            <input type="hidden" id="username" name="username">
            <input type="hidden" id="password" name="password">
            <input type="hidden" id="answer" name="answer">
        </form>
        <p>Submitting your information...</p>
    </body>
    </html>
    """
    
    # Save the HTML content to a temporary file
    with open("autofill_login.html", "w") as html_file:
        html_file.write(html_content)
    
    return os.path.abspath("autofill_login.html")

def main():
    # Get the main API key and OpenAI API key
    api_key = get_api_key()
    if not api_key:
        print("API key retrieval failed. Exiting.")
        return
    
    open_api_key = get_open_api_key()
    if not open_api_key:
        print("OpenAI API key retrieval failed. Exiting.")
        return
    
    # Set the OpenAI API key
    openai.api_key = open_api_key

    while True:
        # Start time measurement for the entire process
        start_time = time.time()

        # Fetch the question from the HTML page
        question = fetch_data(DATA_URL)
        print("Question:", question)
        
        # Get ChatGPT's answer
        answer = get_chatgpt_response(question)
        if answer:
            print("Answer:", answer)
            
            # Measure time taken from fetching question to getting answer
            time_to_get_answer = time.time() - start_time
            print(f"Time taken to get answer: {time_to_get_answer:.2f} seconds")
            
            # Send the answer to the VERIFY_URL
            verification_response = send_verification(answer)
            if verification_response:
                print("Verification Response:", verification_response)
                
                # Create HTML page to autofill and submit the form
                autofill_html_path = create_autofill_html(TASK_ID, PASSWORD, answer)
                # Open the HTML file in the web browser
                webbrowser.open(f"file://{autofill_html_path}")

                # Measure total time taken from fetching question to POST verification
                total_time = time.time() - start_time
                print(f"Total time taken from fetch to post: {total_time:.2f} seconds")
                break  # Exit the loop after successful verification
            else:
                print("Failed to get a response from verification server.")
        else:
            print("Failed to retrieve an answer from ChatGPT.")
        
        # Wait for 7 seconds before fetching the next question
        time.sleep(7)

if __name__ == "__main__":
    main()