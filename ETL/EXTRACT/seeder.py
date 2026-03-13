"""
seeder.py (Extracts the data)

The program is meant to go grab player data and then grab the most recent 50 games they played.
We can then use the match_id to then grab other important details that we then put into supabase.
"""
import os 
import requests 
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

# Configs for our data
REGION_PLATFORM = "na1"     # We can change this to: na1, euw1, kr
REGION_ROUTE = "americas"   # We can change this to: americas, europe, asia
MATCH_TYPE = "RANKED_SOLO_5x5"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_challenger_players():
    """
    Fetches the top 50 players from the Challenger league for the target region.
    """
    url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{MATCH_TYPE}"
    params = {"api_key": RIOT_API_KEY}
    response = requests.get(url, params=params)

    if response.status_code == 200:
        return response.json().get('entries', [])[:50]
    print(f"Error fetching Challenger list: {response.status_code}")
    return []

def get_recent_matches(puuid, count=10):
    """
    Retrieves the last X match IDs for a specific player PUUID.
    Filters specifically for Ranked Solo/Duo games (Queue 420).
    """
    url = f"https://{REGION_ROUTE}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    # Filter for Ranked Solo/Duo (Queue 420)
    params = {"api_key": RIOT_API_KEY, "queue": 420, "start": 0, "count": count}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    return []

def get_puuid_from_summoner_id(summoner_id):
    url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    params = {"api_key": RIOT_API_KEY}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json().get('puuid')
    return None

def seed_match_queue(match_ids):
    """
    Uploads Match IDs to the Supabase match_queue table.
    Uses 'upsert' to ensure we don't create duplicate entries for the same match.
    """
    data = [{"match_id": m_id, "status": "PENDING"} for m_id in match_ids]
    
    try:
        # .upsert() or .insert() works here. 
        # Since match_id is the Primary Key, duplicates will just fail/be ignored.
        supabase.table("match_queue").upsert(data, on_conflict="match_id").execute()
        print(f"   + Seeded {len(match_ids)} IDs (including duplicates).")
    except Exception as e:
        print(f"Error seeding to Supabase: {e}")

if __name__ == "__main__":
    print(f"Starting seeding for {REGION_PLATFORM} Challenger players...")
    
    players = get_challenger_players()
    print(f"Found {len(players)} players. Gathering match IDs...")

    for i, player in enumerate(players):
        # Grab 'puuid' from the player object
        puuid = player.get('puuid')

        if not puuid:
            print(f"Error: No PUUID found for player at index {i}. Keys: {player.keys()}")
            continue

        # Note: 'summonerName' might also be missing in newer versions of this API 
        # (replaced by Riot ID), so we use .get() to avoid crashes.
        name = player.get('summonerName', 'Unknown Player')
        print(f"[{i+1}/50] Processing player: {name}")
        
        # Get Match IDs
        match_ids = get_recent_matches(puuid)
        
        # Push to Queue
        if match_ids:
            seed_match_queue(match_ids)
        
        # We can actually lower this sleep timer now because we are making fewer calls!
        import time
        time.sleep(0.5) 

    print("\nSeeding Complete! Workers can now start processing.")