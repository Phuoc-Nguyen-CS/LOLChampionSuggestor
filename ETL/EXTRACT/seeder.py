"""
seeder.py (Extracts the data)

We can then use the match_id to then grab other important details that we then put into supabase.
"""
import os 
import requests 
from dotenv import load_dotenv
from supabase import create_client, Client
import time

load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

# Configs for our data
REGION_PLATFORM = "na1"     # We can change this to: na1, euw1, kr
REGION_ROUTE = "americas"   # We can change this to: americas, europe, asia
MATCH_TYPE = "RANKED_SOLO_5x5"

LEAGUES = [
    {"tier": "CHALLENGER", "type": "APEX"},
    {"tier": "GRANDMASTER", "type": "APEX"},
    {"tier": "MASTER", "type": "APEX"},
    {"tier": "DIAMOND", "type": "STANDARD", "division": "I"},
    {"tier": "EMERALD", "type": "STANDARD", "division": "I"},
]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_players(league):
    tier = league['tier'].upper() # Riot expects uppercase
    
    if league['type'] == "APEX":
        # Endpoint: /lol/league/v4/challengerleagues/by-queue/{queue}
        url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/league/v4/{tier.lower()}leagues/by-queue/{MATCH_TYPE}"
    else:
        # Endpoint: /lol/league/v4/entries/{queue}/{tier}/{division}
        division = league.get('division', 'I')
        url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/league/v4/entries/{MATCH_TYPE}/{tier}/{division}"
    
    # Standard leagues use 'page' as a query parameter
    params = {"api_key": RIOT_API_KEY, "page": 1}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        # Apex returns a dict {'entries': [...]}, Standard returns a list [...]
        return data.get('entries', []) if isinstance(data, dict) else data
    
    print(f" ! API Error {response.status_code} for {tier}")
    return []



# DEPRECATED: Was a testing function
# def get_challenger_players():
#     """
#     Fetches the top 50 players from the Challenger league for the target region.
#     """
#     url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{MATCH_TYPE}"
#     params = {"api_key": RIOT_API_KEY}
#     response = requests.get(url, params=params)

#     if response.status_code == 200:
#         return response.json().get('entries', [])[:50]
#     print(f"Error fetching Challenger list: {response.status_code}")
#     return []

def get_puuid_if_missing(player_obj):
    """Exchanges summonerId for puuid if the API didn't provide it."""
    puuid = player_obj.get('puuid')
    if puuid:
        return puuid

    summoner_id = player_obj.get('summonerId')
    url = f"https://{REGION_PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    res = requests.get(url, params={"api_key": RIOT_API_KEY})
    if res.status_code == 200:
        return res.json().get('puuid')
    return None

def get_recent_matches(puuid, count=15):
    """
    Retrieves the last X match IDs for a specific player PUUID.
    Filters specifically for Ranked Solo/Duo games (Queue 420).
    """
    url = f"https://{REGION_ROUTE}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    # Filter for Ranked Solo/Duo (Queue 420)
    params = {"api_key": RIOT_API_KEY, "queue": 420, "start": 0, "count": count}
    response = requests.get(url, params=params)
    
    return response.json() if response.status_code == 200 else []

def seed_match_queue(match_ids, tier):
    """
    Uploads Match IDs to the Supabase match_queue table.
    Uses 'upsert' to ensure we don't create duplicate entries for the same match.
    """
    if not match_ids: return
    
    # We add the rank_tier to every row here
    data = [
        {"match_id": m_id, "status": "PENDING", "rank_tier": tier} 
        for m_id in match_ids
    ]
    
    try:
        # Note: Ensure your Supabase table has a 'rank_tier' column!
        supabase.table("match_queue").upsert(data, on_conflict="match_id").execute()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    print("--- Multi-Tier Seeder Bot Active ---")
    
    while True:
        # This loop now iterates through every entry in your LEAGUES list
        for league in LEAGUES:
            tier_name = league['tier']
            print(f"\n[TARGETING] {tier_name} ({league['type']})")
            
            # Fetch the player list for this specific tier
            all_players = get_players(league)
            
            # We take a subset (top 20) to keep the cycle moving quickly 
            # and avoid getting stuck on one rank for too long.
            active_subset = all_players[:20] 
            
            if not active_subset:
                print(f" ! Warning: Could not find players for {tier_name}")
                continue

            for i, player in enumerate(active_subset):
                # Handle the PUUID
                # This is where we ensure we get the 'ID' regardless of rank
                puuid = get_puuid_if_missing(player)
                
                if not puuid:
                    print(f" ! Skipping {tier_name} player {i}: No PUUID found.")
                    time.sleep(1.2) # Still sleep to respect rate limits
                    continue

                # Get Match IDs for this specific player
                m_ids = get_recent_matches(puuid)
                
                # Seed the match_queue
                if m_ids:
                    seed_match_queue(m_ids, tier_name)
                    print(f" + {tier_name} Progress: {i+1}/{len(active_subset)}", end="\r")
                
                # ~95% 100 req / 2 min limit
                time.sleep(1.3) 
            
            print(f"\n[FINISH] Completed seeding for {tier_name}.")

        print("\n[CYCLE COMPLETE] Resting for 10 minutes...")
        time.sleep(600)