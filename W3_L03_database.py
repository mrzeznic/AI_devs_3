import os
import json
import requests
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai

# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
TASK_ID = "database"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W3L03"
DATABASE_API = "https://centrala.ag3nts.org/apidb"

# API keys
api_key = get_api_key()
openai.api_key = get_open_api_key()

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

# Function to run query against DATABASE_API
def run_query(query):
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "query": query
    }
    response = requests.post(DATABASE_API, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to execute query '{query}': {response.text}")

# Fetch table structures from the API
def fetch_table_structure(table_name):
    print(f"Fetching structure for table: {table_name}")
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "query": "show create table "+table_name
    }
    response = requests.post(DATABASE_API, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error fetching table structure for {table_name}: {response.text}")

# Generate SQL query using LLM
def generate_sql_query(table_structures, question):
    cache_path = os.path.join(CACHE_FOLDER, "generated_query.json")
    if USE_CACHE and os.path.exists(cache_path):
        print("Using cached SQL query")
        with open(cache_path, "r") as cache_file:
            return json.load(cache_file)

    print("Generating SQL query using LLM")
    prompt = (
        "Based on the structures of the following tables:\n\n"
        f"{json.dumps(table_structures, indent=2)}\n\n"
        f"Write an SQL query to answer the question:\n'{question}'"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an SQL expert who helps in crafting database queries. Answer only with query, without sql marking, no comments pure sql code."},
            {"role": "user", "content": prompt}
        ]
    )
    sql_query = response["choices"][0]["message"]["content"].strip()

    # Cache the query
    if USE_CACHE:
        with open(cache_path, "w") as cache_file:
            json.dump(sql_query, cache_file)

    return sql_query

# Send result to the central API
def send_result_to_central(answer):
    print("Sending result to the central API")
    payload = {
        "task": TASK_ID,
        "apikey": api_key,
        "answer": answer
    }
    response = requests.post(CENTRALA_API, json=payload)
    if response.status_code == 200:
        print("Response approved by the central API:", response.text)
        return response.json().get("flag")
    else:
        raise Exception(f"Error sending result to the central API: {response.text}")

# Main function
def main():
    try:
        # Step 1: Fetch the list of tables
        print("Fetching list of tables...")
        show_tables_result = run_query("show tables")
        table_names = [row["Tables_in_banan"] for row in show_tables_result.get("reply", [])]        
        print(f"Tables found: {table_names}")

        # Step 2: Fetch table structures
        table_structures = {table: fetch_table_structure(table) for table in table_names}

        # Step 3: Generate SQL query using LLM
        question = "Which active datacenters (DC_ID) are managed by employees who are on leave (is_active=0)?"
        sql_query = generate_sql_query(table_structures, question)
        print(f"Generated SQL query:\n{sql_query}")

        # Step 4: Execute the SQL query
        query_result = run_query(sql_query)
        print(query_result)
        datacenter_ids = [row["dc_id"] for row in query_result.get("reply", [])]
        print(f"Datacenter IDs found: {datacenter_ids}")

        # Step 5: Send result to the central API
        flag = send_result_to_central(datacenter_ids)
        if flag:
            print(f"Flag received: {flag}")
        else:
            print("No flag received.")

    except Exception as e:
        print("An error occurred:", str(e))

if __name__ == "__main__":
    main()