"""
worker.py (Transform)

Use the loaded data from seeder to then transform our data to what we need.
"""

import os 
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import time 


# Grab the environment variables
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

# Initializing the Database Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def claim_pending_matches(limit = 5):
    # Grabs matches from the queue
    try:
        # Custom SQL function from earlier
        response = supabase.rpc("claim_matches", {"claim_limit" : limit}).execute()
        return response.data
    except Exception as e:
        print(f"Error claim the matches: {e}")
        return []
    
def get_matches_from_riot(match_id):
    # Use the match id to grab the match details
    region = "americas"
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:  # Successful extraction   
        return response.json()
    elif response.status_code == 429: # We hit the max rate
        print("Exceeded rate limit by RIOT API")
        time.sleep(20)
    else:
        print(f"Failed to fetch {match_id}: Status{response.status_code}")

    return None

def mark_match_done(match_data):
    supabase.table("match_queue").update({"status": "DONE"}).eq("match_id", match_id).execute()

def process_match_data(match_data):
    # Grab who won and who lost

    game_mode = match_data.get('info', {}).get('gameMode', 'UNKNOWN')
    print(f"    -> Successfully parsed a {game_mode} match.")

if __name__ == "__main__":
    print("Worker node starting")

    while True:
        print("Looking for work")
        matches = claim_pending_matches(limit = 5)

        if not matches:
            print("Queue is empty, trying in 30 seconds")
            time.sleep(30)
            continue
    
        for match in matches:
            match_id = match["match_id"]
            print(f"Fetching match: {match_id}")

            match_data = get_matches_from_riot(match_id)

            # Process data 
            if match_data:
                process_match_data(match_data)
                # Only mark as DONE if we actually got data or if it's a 404
                mark_match_done(match_id)
            else:
                # If Riot 404s, it's a dead ID. Mark it DONE so we don't get stuck.
                mark_match_done(match_id)


            time.sleep(2)