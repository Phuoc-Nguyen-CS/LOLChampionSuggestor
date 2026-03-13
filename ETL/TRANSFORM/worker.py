"""
worker.py (Transform)

Use the loaded data from seeder to then transform our data to what we need.
"""

import os 
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import time 
import itertools


# Grab the environment variables
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

# Initializing the Database Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def claim_pending_matches(limit = 5):
    """
    Calls the Supabase RPC 'claim_matches' to safely grab PENDING matches 
    from the queue and mark them as PROCESSING.
    """
    try:
        # Custom SQL function from earlier
        response = supabase.rpc("claim_matches", {"claim_limit" : limit}).execute()
        return response.data
    except Exception as e:
        print(f"Error claim the matches: {e}")
        return []
    
def get_matches_from_riot(match_id):
    """
    Fetches raw match JSON data from Riot Games Match-V5 API.
    """
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
    """
    Updates the match status to DONE so it is removed from the active queue.
    """
    supabase.table("match_queue").update({"status": "DONE"}).eq("match_id", match_id).execute()

def process_match_data(match_data):
    """
    The core logic: Extracts champions, determines winners/losers, 
    and triggers the database updates for synergies and counters.
    """
    info = match_data.get('info', {})

    # Only grab SR games
    if info.get('gameMode') != "CLASSIC":
        return
    
    participants = info.get('participants', [])
    if len(participants) != 10: # Edge case for in case its a customs
        return
    
    # Get winners and losers
    winners = [p['championId'] for p in participants if p['win']]
    losers = [p['championId'] for p in participants if not p['win']]
    # Grabs their rank
    raw_tier = participants[0].get('tier', 'UNKNOWN')
    tier = raw_tier.upper() if raw_tier else "UNKNOWN"
    print(f"    -> Updating Synergy for {len(winners)} winners and {len(losers)} losers...")

    # Processing the synnergies
    update_synergy_batch(winners, True, tier)     # Group winners together
    update_synergy_batch(winners, False, tier)     # Group losers together

    # Process the counters
    # Tracking if Champ A (Winner) beat champ B (Loser)
    print(f"    -> Updating Counters")
    update_counter_batch(winners, losers, tier)

    # game_mode = match_data.get('info', {}).get('gameMode', 'UNKNOWN')
    # print(f"    -> Successfully parsed a {game_mode} match.")

def update_synergy_batch(champ_ids, did_win, tier):
    """
    Calculates every duo combination on a team and updates the synergy_stats table.
    """

    # This prevents duplicates rows in the DB
    # e.g. (1, 53) and (53, 1) will appear as (1, 53) in the DB
    pairs = list(itertools.combinations(sorted(champ_ids), 2))

    win_value = 1 if did_win else 0

    for champ_a, champ_b in pairs:
        # Call SQL function in Supabase
        supabase.rpc("increment_synergy", {
            "ca_id": champ_a,
            "cb_id": champ_b,
            "w_inc": win_value,
            "t": tier
        }).execute()

def update_counter_batch(winners, losers, tier):
    """
    Calculates head-to-head matchups (each winner beat each loser) 
    and updates the counters table.
    """
    matchups = list(itertools.product(winners, losers))

    for winner_id, loser_id in matchups:
        try:
            supabase.rpc("increment_counter", {
                "w_id": winner_id, 
                "l_id": loser_id, 
                "t": tier
            }).execute()
        except Exception as e:
            print(f"Failed to update_counter_batch for winner:{winner_id} vs loser:{loser_id}: {e}")

        
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
            # Dynamic to maximize
            start_time = time.time()

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

            elapsed = time.time() - start_time
            wait_time = max(0, 1.26 - elapsed)

            time.sleep(wait_time)