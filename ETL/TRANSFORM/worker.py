"""
worker.py (Transform)

Extracts Identity Metrics 
Timeline Milestones to feed the EV Model.
"""

import os 
import time 
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from supabase import create_client, Client

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Environment Setup ---
load_dotenv()
SUPABASE_URL = os.environ.get("TEMP_URL")
SUPABASE_KEY = os.environ.get("TEMP_KEY")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, RIOT_API_KEY]):
    logger.critical("Missing required environment variables. Shutting down.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
session.headers.update({"X-Riot-Token": RIOT_API_KEY})


def claim_pending_matches(limit=5):
    """Safely claims PENDING matches from the queue via Supabase RPC."""
    try:
        response = supabase.rpc("claim_matches", {"claim_limit": limit}).execute()
        return response.data
    except Exception as e:
        logger.error(f"Database error while claiming matches: {e}")
        return []

def fetch_from_riot(url, match_id, endpoint_type="Match"):
    """Generic, safe Riot API fetcher with timeout and 429 handling."""
    try:
        response = session.get(url, timeout=10) 
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            logger.warning(f"Rate limited by Riot API ({endpoint_type}). Sleeping for 20s.")
            time.sleep(20)
            raise Exception("RATE_LIMIT")
        elif response.status_code in [400, 404]:
            logger.warning(f"{endpoint_type} data for {match_id} not found ({response.status_code}).")
            return None
        else:
            logger.error(f"Failed to fetch {endpoint_type} {match_id}. Status: {response.status_code}")
            raise Exception(f"API_ERROR_{response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {endpoint_type} {match_id}: {e}")
        raise Exception("NETWORK_ERROR")

def mark_match_done(match_id):
    """Updates the match status to DONE."""
    try:
        supabase.table("match_queue").update({"status": "DONE"}).eq("match_id", match_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark match {match_id} as DONE: {e}")

def process_match_data(match_data, timeline_data, tier, match_id):
    info = match_data.get('info', {})
    if info.get('gameMode') != "CLASSIC": 
        return
    
    participants = info.get('participants', [])
    if len(participants) != 10: 
        return 
    
    duration_mins = info.get('gameDuration', 0) / 60.0
    if duration_mins < 15.0: 
        return

    # --- Pre-calculate Team Totals (Needed for Gold Share) ---
    team_totals = {100: {'gold': 0}, 200: {'gold': 0}}
    for p in participants:
        t_id = p.get('teamId', 100)
        team_totals[t_id]['gold'] += p.get('goldEarned', 0)

    records = []
    milestones = [15, 20, 25, 30]

    for p in participants:
        p_id = str(p.get('participantId', '0')) 
        team_id = p.get('teamId', 100)
        total_dmg = max(p.get('totalDamageDealtToChampions', 1), 1)
        team_gold = max(team_totals.get(team_id, {}).get('gold', 1), 1)
        
        total_heal = p.get('totalHeal', 0)
        ally_heal = p.get('totalHealsOnTeammates', 0)

        p_data = {
            "match_id": match_id,
            "tier": tier,
            "champion_id": p.get('championId'),
            "team_id": team_id,
            "win": p.get('win', False),
            "team_position": p.get('teamPosition', 'UNKNOWN'),
            "duration_mins": round(duration_mins, 2),
            
            # --- Identity Stats ---
            "phys_share": round(p.get('physicalDamageDealtToChampions', 0) / total_dmg, 4),
            "magic_share": round(p.get('magicDamageDealtToChampions', 0) / total_dmg, 4),
            "true_share": round(p.get('trueDamageDealtToChampions', 0) / total_dmg, 4),
            "gold_share": round(p.get('goldEarned', 0) / team_gold, 4),
            
            "largest_crit": p.get('largestCriticalStrike', 0),
            "total_damage_taken": p.get('totalDamageTaken', 0),
            "damage_mitigated": p.get('damageSelfMitigated', 0),
            "self_healing_volume": max(total_heal - ally_heal, 0),

            "time_ccing_others": p.get('timeCCingOthers', 0),
            "ally_heal_volume": ally_heal,
            "ally_shield_volume": p.get('totalDamageShieldedOnTeammates', 0),

            "dmg_to_turrets": p.get('damageDealtToTurrets', 0),
        }

        # --- Timeline EV Stats ---
        for minute in milestones:
            try:
                # Attempt to extract exact snapshot from the timeline payload
                frame = timeline_data['info']['frames'][minute]['participantFrames'][p_id]
                p_data[f"gold_at_{minute}"] = frame.get('totalGold', 0)
                p_data[f"xp_at_{minute}"] = frame.get('xp', 0)
                p_data[f"cs_at_{minute}"] = frame.get('minionsKilled', 0) + frame.get('jungleMinionsKilled', 0)

            except (IndexError, KeyError):
                # Game ended before this milestone. 
                last_frame_idx = len(timeline_data['info']['frames']) - 1
                last_frame = timeline_data['info']['frames'][last_frame_idx]['participantFrames'][p_id]

                p_data[f"gold_at_{minute}"] = p.get('goldEarned', 0)
                p_data[f"xp_at_{minute}"] = last_frame.get('xp', 0) 
                p_data[f"cs_at_{minute}"] = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
        records.append(p_data)
    
    # Bulk Insert to Supabase
    try:
        supabase.table("match_participants_v2").insert(records).execute()
    except Exception as e:
        logger.error(f"Match Insert Error for {match_id}: {e}")

if __name__ == "__main__":
    logger.info("--- XGBoost Worker Node Starting ---")
    
    while True:
        matches = claim_pending_matches(limit=5)
        
        if not matches:
            logger.info("Queue empty, resting for 5 minutes...")
            time.sleep(300)
            continue
            
        total_matches = len(matches)
        logger.info(f"Claimed {total_matches} matches. Processing...")
        success_count = 0 

        # We wrap 'matches' in enumerate(..., start=1) to automatically count 1, 2, 3...
        for i, match in enumerate(matches, start=1):
            start_time = time.time()
            m_id = match.get("match_id")
            m_tier = match.get("rank_tier", "UNKNOWN")

            try:
                # Fetch Main Payload
                match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{m_id}"
                match_data = fetch_from_riot(match_url, m_id, "Match")
                
                time.sleep(1.25) # Space out API calls
                
                # Fetch Timeline Payload
                timeline_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{m_id}/timeline"
                timeline_data = fetch_from_riot(timeline_url, m_id, "Timeline")
                
                # Process & Save
                if match_data and timeline_data:
                    process_match_data(match_data, timeline_data, m_tier, m_id)
                    mark_match_done(m_id)
                    success_count += 1
                    
                    # --- The Clean Progress Tracker ---
                    logger.info(f"[{i}/{total_matches}] Data processed")
                else:
                    logger.warning(f"[{i}/{total_matches}] Skipped {m_id}: Missing Match or Timeline data.")

            except Exception as e:
                # Catches Network, Rate Limit, or Processing errors gracefully
                logger.error(f"[{i}/{total_matches}] Failed to process {m_id}: {e}")
            
            # Rate limit management
            elapsed = time.time() - start_time
            wait_time = max(0, 2.5 - elapsed)
            time.sleep(wait_time)
            
        # Prints exactly once per batch
        logger.info(f"Batch complete. Successfully saved {success_count}/{total_matches} matches.\n")