# worker.py 
# Try and extract data from the RIOT API and store it on supabase for usage

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
    elif response.state_code == 429: # We hit the max rate
        print("Exceeded rate limit by RIOT API")
        time.sleep(20)
    else:
        print(f"Failed to fetch {match_id}: Status{response.status_code}")

    return None

 