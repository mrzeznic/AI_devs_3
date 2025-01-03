import os
import json
import requests
from get_api_key import get_api_key
from get_open_api_key import get_open_api_key
import openai
from neo4j import GraphDatabase

# Configuration
CENTRALA_API = "https://centrala.ag3nts.org/report"
DB_TASK_ID = "database"
TASK_ID = "connections"
USE_CACHE = True  # Enable caching to prevent re-generating the query
CACHE_FOLDER = "./cache/W3L05"
DATABASE_API = "https://centrala.ag3nts.org/apidb"

# API keys
api_key = get_api_key()
openai.api_key = get_open_api_key()

# Ensure cache folder exists
os.makedirs(CACHE_FOLDER, exist_ok=True)

# Function to run query against DATABASE_API
def run_query(query):
    payload = {
        "task": DB_TASK_ID,
        "apikey": api_key,
        "query": query
    }
    response = requests.post(DATABASE_API, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to execute query '{query}': {response.text}")

def setup_neo4j_database(users, connections):
    """Setup Neo4j database with users and their connections"""
    # Update connection details
    neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'neo4jpassword') # change in http://127.0.0.1:7474/browser/
    
    print(f"\nConnecting to Neo4j at {neo4j_uri}...")
    driver = GraphDatabase.driver(
        neo4j_uri, 
        auth=(neo4j_user, neo4j_password)
    )
    
    # Verify connection
    try:
        driver.verify_connectivity()
        print("Successfully connected to Neo4j")
    except Exception as e:
        raise Exception(f"Failed to connect to Neo4j: {str(e)}")

    def clear_database(tx):
        tx.run("MATCH (n) DETACH DELETE n")
    
    def create_users(tx, users):
        for user in users:
            tx.run("CREATE (u:User {id: $id, name: $name})",
                   id=user['id'], name=user['username'])
    
    def create_connections(tx, connections):
        for conn in connections:
            tx.run("""
                MATCH (u1:User {id: $user1_id})
                MATCH (u2:User {id: $user2_id})
                CREATE (u1)-[:KNOWS]->(u2)
            """, user1_id=conn['user1_id'], user2_id=conn['user2_id'])
    
    print("\nSetting up Neo4j database...")
    with driver.session() as session:
        print("Clearing existing data...")
        session.execute_write(clear_database)
        
        print("Creating user nodes...")
        session.execute_write(create_users, users)
        
        print("Creating relationships...")
        session.execute_write(create_connections, connections)
    
    return driver

def find_shortest_path(driver):
    """Find shortest path from Rafał to Barbara"""
    with driver.session() as session:
        print("\nFinding shortest path...")
        result = session.run("""
            MATCH (start:User {name: 'Rafał'}),
                  (end:User {name: 'Barbara'}),
                  p = shortestPath((start)-[:KNOWS*]->(end))
            RETURN [node in nodes(p) | node.name] as path
        """)
        path = result.single()
        if path is None:
            raise Exception("No path found between Rafał and Barbara")
        return path['path']


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
        def fetch_data():
            """Fetch users and connections from MySQL"""
            print("\nFetching users...")
            users = run_query("SELECT id, username FROM users")
    
            print("\nFetching connections...")
            connections = run_query("SELECT user1_id, user2_id FROM connections")
    
            return users['reply'], connections['reply']

        # Step 2: Setup Neo4j database
        users, connections = fetch_data()
        driver = setup_neo4j_database(users, connections)
        
        # Step 3: Find shortest path
        path = find_shortest_path(driver)
        
        # Step 4: Format and send the answer
        answer = ", ".join(path)
        print(f"\nFound path: {answer}")
        
        # Step 5: Send result to the central API
        flag = send_result_to_central(answer)
        
    except Exception as e:
        print("An error occurred:", str(e))

if __name__ == "__main__":
    main()
