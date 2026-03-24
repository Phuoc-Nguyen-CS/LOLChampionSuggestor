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
# SUPABASE_URL = os.environ.get("SUPABASE_URL")
# SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_URL = os.environ.get("TEMP_URL")
SUPABASE_KEY = os.environ.get("TEMP_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

# Initializing the Database Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def claim_pending_matches(limit = 5):
    """
    Calls the Supabase RPC 'claim_matches' to safely grab PENDING matches 
    from the queue and mark them as PROCESSING.
    """
    try:
        response = supabase.rpc("claim_matches", {"claim_limit" : limit}).execute()
        return response.data
    except Exception as e:
        print(f"Error claiming matches: {e}")
        return []
    
def get_matches_from_riot(match_id):
    """
    Fetches raw match JSON data from Riot Games Match-V5 API.
    """
    region = "americas"
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:   
        return response.json()
    elif response.status_code == 429:
        print("Exceeded rate limit by RIOT API")
        time.sleep(20)
        raise Exception("RATE_LIMIT") 
    elif response.status_code == 404:
        print(f"Match {match_id} not found (404).")
        return None
    else:
        print(f"Failed to fetch {match_id}: Status {response.status_code}")
        raise Exception("API_ERROR")

def mark_match_done(match_id):
    """
    Updates the match status to DONE so it is removed from the active queue.
    """
    try:
        supabase.table("match_queue").update({"status": "DONE"}).eq("match_id", match_id).execute()
    except Exception as e:
        print(f"Failed to mark match {match_id} as DONE: {e}")

def process_match_data(match_data, tier, match_id):
    info = match_data.get('info', {})
    if info.get('gameMode') != "CLASSIC": return
    
    participants = info.get('participants', [])
    if len(participants) != 10: return 
    
    duration_mins = info.get('gameDuration', 0) / 60.0
    if duration_mins < 10: return # Skip remakes

    # 1. Calculate Team Totals (Needed for Gold/Objective shares)
    team_totals = {100: {'gold': 0, 'obj_dmg': 0}, 200: {'gold': 0, 'obj_dmg': 0}}
    for p in participants:
        t_id = p.get('teamId', 100)
        team_totals[t_id]['gold'] += p.get('goldEarned', 0)
        team_totals[t_id]['obj_dmg'] += p.get('damageDealtToObjectives', 0)

    records = []

    # 2. Extract Individual Profiles
    for p in participants:
        team_id = p.get('teamId', 100)
        total_dmg = max(p.get('totalDamageDealtToChampions', 1), 1)

        records.append({
            "match_id": match_id,
            "tier": tier,
            "champion_id": p['championId'],
            "team_id": team_id,
            "win": p.get('win', False),
            "duration_mins": duration_mins,
            "team_position": p.get('teamPosition', 'UNKNOWN'),
            
            # The XGBoost Features
            "phys_share": p.get('physicalDamageDealtToChampions', 0) / total_dmg,
            "magic_share": p.get('magicDamageDealtToChampions', 0) / total_dmg,
            "true_share": p.get('trueDamageDealtToChampions', 0) / total_dmg,
            
            "gold_share": p.get('goldEarned', 0) / max(team_totals[team_id]['gold'], 1),
            "obj_dmg_share": p.get('damageDealtToObjectives', 0) / max(team_totals[team_id]['obj_dmg'], 1),
            
            "self_mitigated_per_min": p.get('damageSelfMitigated', 0) / duration_mins,
            "minions_per_min": (p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)) / duration_mins,
            "heal_per_min": p.get('totalHeal', 0) / duration_mins,
            "ally_heal_per_min": p.get('totalHealsOnTeammates', 0) / duration_mins,
            "ally_shield_per_min": p.get("totalDamageShieldedOnTeammates", 0) / duration_mins
        })

    # 3. Bulk Insert to Supabase (Replaces the old RPC calls)
    try:
        # supabase.table("match_participants").upsert(records, on_conflict="match_id, champion_id").execute()
        supabase.table("match_participants").insert(records).execute()
        # spooler.save_record("match_participants", records)
    except Exception as e:
        print(f"      [WARNING] Match Insert Error: {e}")

# def sync_to_champion_behavior():
#     """Pulls averages from the SQL view and updates the champion_behavior table."""
#     print("Syncing Layer 2 to champion_behavior...", end=" ", flush=True)
#     try:
#         # stats = supabase.table("champion_behavior").select("*").execute().data
#         stats = supabase.table("v_champion_behavior_agg").select("*").execute().data
#         if not stats:
#             print("[No Data]")
#             return

#         profiles = []
#         for row in stats:
#             early_wr = row['early_game_wr'] or 0
#             late_wr = row['late_game_wr'] or 0
            
#             scaling_tier = 2
#             if late_wr > (early_wr + 0.03): scaling_tier = 3
#             elif early_wr > (late_wr + 0.03): scaling_tier = 1

#             profiles.append({
#                 "champion_id": row['champion_id'],
#                 "physical_dmg_share": round(row['physical_dmg_share'] or 0, 3),
#                 "magic_dmg_share": round(row['magic_share'] or 0, 3),
#                 "true_dmg_share": round(row['true_share'] or 0, 3),
#                 "gold_share_pct": round(row['gold_share_pct'] or 0, 3),
#                 "objective_dmg_share": round(row['objective_dmg_share'] or 0, 3),
#                 "avg_self_mitigated_per_min": round(row['avg_self_mitigated_per_min'] or 0, 2),
#                 "avg_minions_killed": round(row['avg_minions_killed'] or 0, 2),
#                 "avg_healing_per_min": round(row['avg_healing_per_min'] or 0, 2),
#                 "avg_ally_healing_per_min": round(row['avg_ally_healing_per_min'] or 0, 2),
#                 "avg_ally_shielding_per_min": round(row['avg_ally_shielding_per_min'] or 0, 2),
#                 "actual_scaling_tier": scaling_tier,
#                 "total_matches": row['total_matches']
#             })

#         supabase.table("champion_behavior").upsert(profiles).execute()
#         print(f"[Success: Updated {len(profiles)} Champs]")
#     except Exception as e:
#         print(f"[Failed: {e}]")

if __name__ == "__main__":
    print("XGBoost Worker node starting...")
    matches_processed = 0  # Initialize a counter
    
    while True:
        matches = claim_pending_matches(limit=5)
        if not matches:
            print("Queue empty, resting for 30s...")
            time.sleep(30)
            continue
            
        print(f"\nClaimed {len(matches)} matches. Processing...")

        for match in matches:
            start_time = time.time()
            m_id = match["match_id"]
            m_tier = match.get("rank_tier", "UNKNOWN")

            try:
                print(f"Fetching {m_id} [{m_tier}]", end=" ", flush=True)
                data = get_matches_from_riot(m_id)
                
                if data:
                    process_match_data(data, m_tier, m_id)
                    matches_processed += 1 # Increment successful matches
                    print("[Success]")
                else:
                    print("[No Data (Skipped)]")
                
                mark_match_done(m_id)

            except Exception as e:
                print(f"\nError on {m_id}: {e}")
            
            # Rate limit management
            elapsed = time.time() - start_time
            wait_time = max(0, 1.26 - elapsed)
            time.sleep(wait_time)
            
        if matches_processed >= 100:
            sync_to_champion_behavior()
            matches_processed = 0 # Reset counter