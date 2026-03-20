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
        supabase.table("match_participants").upsert(records, on_conflict="match_id, champion_id").execute()
    except Exception as e:
        print(f"      [WARNING] Match Insert Error: {e}")

def sync_to_champion_behavior():
    """Pulls averages from the SQL view and updates the champion_behavior table."""
    print("Syncing Layer 2 to champion_behavior...", end=" ", flush=True)
    try:
        # stats = supabase.table("champion_behavior").select("*").execute().data
        stats = supabase.table("v_champion_behavior_agg").select("*").execute().data
        if not stats:
            print("[No Data]")
            return

        profiles = []
        for row in stats:
            early_wr = row['early_game_wr'] or 0
            late_wr = row['late_game_wr'] or 0
            
            scaling_tier = 2
            if late_wr > (early_wr + 0.03): scaling_tier = 3
            elif early_wr > (late_wr + 0.03): scaling_tier = 1

            profiles.append({
                "champion_id": row['champion_id'],
                "physical_dmg_share": round(row['physical_dmg_share'] or 0, 3),
                "magic_dmg_share": round(row['magic_share'] or 0, 3),
                "true_dmg_share": round(row['true_share'] or 0, 3),
                "gold_share_pct": round(row['gold_share_pct'] or 0, 3),
                "objective_dmg_share": round(row['objective_dmg_share'] or 0, 3),
                "avg_self_mitigated_per_min": round(row['avg_self_mitigated_per_min'] or 0, 2),
                "avg_minions_killed": round(row['avg_minions_killed'] or 0, 2),
                "avg_healing_per_min": round(row['avg_healing_per_min'] or 0, 2),
                "avg_ally_healing_per_min": round(row['avg_ally_healing_per_min'] or 0, 2),
                "avg_ally_shielding_per_min": round(row['avg_ally_shielding_per_min'] or 0, 2),
                "actual_scaling_tier": scaling_tier,
                "total_matches": row['total_matches']
            })

        supabase.table("champion_behavior").upsert(profiles).execute()
        print(f"[Success: Updated {len(profiles)} Champs]")
    except Exception as e:
        print(f"[Failed: {e}]")

if __name__ == "__main__":
    print("XGBoost Worker node starting...")
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
            
        sync_to_champion_behavior()


# DEPRECATED: Replaced by the update match up logic
# def update_counter_batch(winners, losers, tier):
#     """
#     Calculates head-to-head matchups (each winner beat each loser) 
#     and updates the counters table.
#     """
#     matchups = list(itertools.product(winners, losers))

#     for winner_id, loser_id in matchups:
#         try:
#             supabase.rpc("increment_counter", {
#                 "w_id": winner_id, 
#                 "l_id": loser_id, 
#                 "t": tier
#             }).execute()
#         except Exception as e:
#             print(f"Failed to update_counter_batch for winner:{winner_id} vs loser:{loser_id}: {e}")

# Weighted
# def process_match_data(match_data, tier):
#     info = match_data.get('info', {})
#     if info.get('gameMode') != "CLASSIC": return
    
#     participants = info.get('participants', [])
#     if len(participants) != 10: return 
    
#     print(f"In process_match_data: {tier}")
#     # Contextual Bucketing
#     duration = info.get('gameDuration', 0)
#     dur_bucket = "EARLY_0_25" if duration < 1500 else ("MID_25_35" if duration < 2100 else "LATE_35_PLUS")

#     winners = []
#     losers = []
#     lanes = {} 

#     for p in participants:
#         pos = p.get('teamPosition')
#         if not pos or pos == "": continue
#         if pos not in lanes: lanes[pos] = {}
        
#         cid = p['championId']
#         chals = p.get('challenges', {})
        
#         if p['win']:
#             winners.append(cid)
#         else:
#             losers.append(cid)

#         # --- ROLE-SPECIFIC SCORING ---
#         micro_score = 0
#         macro_score = 0
        
#         if pos == "UTILITY": # SUPPORT
#             # Micro: Quest speed + Laning vision
#             if chals.get('fasterSupportQuestCompletion', 0): micro_score += 2
#             if chals.get('visionScoreAdvantageLaneOpponent', 0): micro_score += 1
#             # Macro: Kill Participation + Total Wards
#             macro_score = (chals.get('killParticipation', 0) * 100) + chals.get('immobilizeAndKillWithAlly', 0)

#         elif pos == "JUNGLE":
#             # Micro: Gank success + Invading (Enemy Jungle CS)
#             micro_score = chals.get('takedownsBefore15', 0) 
#             micro_score += (chals.get('totalEnemyJungleMinionsKilled', 0) // 10) # 1pt per 10 invades
#             # Macro: Objectives (Dragons/Heralds/Barons)
#             macro_score = (chals.get('teamBaronTakedowns', 0) * 500) + p.get('damageDealtToObjectives', 0)

#         elif pos == "MIDDLE":
#             # Micro: Early Lead + Solo Kills
#             if chals.get('laningPhaseGoldExpAdvantage', 0): micro_score += 2
#             micro_score += chals.get('soloKills', 0)
#             # Macro: Roaming (Kill participation outside lane)
#             macro_score = (chals.get('takedownsBefore15', 0) * 500) + p.get('damageDealtToObjectives', 0)

#         else: # TOP / BOTTOM
#             # Micro: Early Lead
#             if chals.get('laningPhaseGoldExpAdvantage', 0): micro_score += 2
#             if chals.get('maxCsAdvantageOnLaneOpponent', 0) > 15: micro_score += 1
#             micro_score += chals.get('turretPlatesTaken', 0)
#             micro_score += chals.get('soloKills', 0)
#             # --- MACRO (The Map Pressure) ---
#             if pos == "TOP":
#                 # Top Macro = Structure Pressure + Contribution
#                 # Using building damage to identify split-push and pressure. If you're able to apply pressure you're contributing
#                 macro_score = p.get('damageDealtToBuildings', 0) + (p.get('totalDamageDealtToChampions', 0) * 0.1)
            
#             else: # BOTTOM (ADC)
#                 # ADC Macro = Reliable Teamfight Output
#                 # We weight champion damage much higher for ADCs as their 'Map Role'
#                 macro_score = p.get('totalDamageDealtToChampions', 0) + p.get('damageDealtToObjectives', 0)

#         player_data = {"id": cid, "micro": micro_score, "macro": macro_score}
        
#         if p['win']: lanes[pos]['winner'] = player_data
#         else: lanes[pos]['loser'] = player_data

#     # --- THE COMPARISON ENGINE ---
#     for pos, data in lanes.items():
#         if 'winner' in data and 'loser' in data:
#             w, l = data['winner'], data['loser']
#             c_a_id, c_b_id = (w['id'], l['id']) if w['id'] < l['id'] else (l['id'], w['id'])
            
#             a_is_winner = (c_a_id == w['id'])
#             a_data, b_data = (w, l) if a_is_winner else (l, w)
            
#             # Win game but Win Lane ?
#             a_won_game = a_is_winner
#             a_won_micro = a_data['micro'] > b_data['micro']
#             a_won_macro = a_data['macro'] > b_data['macro']

#             supabase.rpc("update_matchup_holistic", {
#                 "c_a": c_a_id, "c_b": c_b_id, "pos": pos, "t": tier, "dur": dur_bucket,
#                 "a_won_game": a_won_game, "a_won_micro": a_won_micro, "a_won_macro": a_won_macro
#             }).execute()

#     update_synergy_batch(winners, True, tier)
#     update_synergy_batch(losers, False, tier)

# Unweighted
# def process_match_data(match_data, tier):
#     info = match_data.get('info', {})
#     if info.get('gameMode') != "CLASSIC": return
    
#     participants = info.get('participants', [])
#     if len(participants) != 10: return 
    
#     # Contextual Bucketing
#     duration = info.get('gameDuration', 0)
#     dur_bucket = "EARLY_0_25" if duration < 1500 else ("MID_25_35" if duration < 2100 else "LATE_35_PLUS")

#     winners = []
#     losers = []
#     lanes = {} 

#     for p in participants:
#         pos = p.get('teamPosition')
#         if not pos or pos == "": continue
#         if pos not in lanes: lanes[pos] = {}
        
#         cid = p['championId']
#         chals = p.get('challenges', {})
        
#         if p['win']:
#             winners.append(cid)
#         else:
#             losers.append(cid)

#         # Gather raw data points
#         # Laning Stats
#         raw_cs = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
#         # Aggresiveness
#         raw_kills = chals.get('soloKills', 0) + chals.get('takedownsBefore15', 0)
#         # Objectives around the map
#         raw_obj = p.get('damageDealtToObjectives', 0) + p.get('damageDealtToBuildings', 0)
#         # Utility Score
#         raw_util = p.get('visionScore', 0) + chals.get('immobilizeAndKillWithAlly', 0)

#         # Store player stats to compare later
#         player_data = {
#             "id": cid, 
#             "cs": raw_cs, 
#             "kills": raw_kills, 
#             "obj": raw_obj, 
#             "util": raw_util
#         }
        
#         if p['win']: lanes[pos]['winner'] = player_data
#         else: lanes[pos]['loser'] = player_data

#     # --- THE COMPARISON ENGINE  ---
#     for pos, data in lanes.items():
#         if 'winner' in data and 'loser' in data:
#             w, l = data['winner'], data['loser']
            
#             c_a_id, c_b_id = (w['id'], l['id']) if w['id'] < l['id'] else (l['id'], w['id'])
            
#             a_is_winner = (c_a_id == w['id'])
#             a_data, b_data = (w, l) if a_is_winner else (l, w)
            
#             a_won_game = a_is_winner
#             a_won_cs = a_data['cs'] > b_data['cs']
#             a_won_kills = a_data['kills'] > b_data['kills']
#             a_won_obj = a_data['obj'] > b_data['obj']
#             a_won_util = a_data['util'] > b_data['util']

#             print(f"   ∟ {pos.ljust(7)} | A: {str(c_a_id).ljust(4)} vs B: {str(c_b_id).ljust(4)} | "
#                   f"W:{int(a_won_game)} CS:{int(a_won_cs)} K:{int(a_won_kills)} O:{int(a_won_obj)} U:{int(a_won_util)}")

#             try:
#                 supabase.rpc("update_matchup_holistic", {
#                     "c_a": c_a_id, "c_b": c_b_id, "pos": pos, 
#                     "t": tier, "dur": dur_bucket,
#                     "a_won_game": a_won_game, "a_won_cs": a_won_cs, 
#                     "a_won_kills": a_won_kills, "a_won_obj": a_won_obj,
#                     "a_won_util": a_won_util
#                 }).execute()
#             except Exception as e:
#                 print(f"      ⚠️ Matchup RPC Error: {e}")
#         else:
#             print(f"   ∟ {pos.ljust(7)} | [Skipping]: Incomplete head-to-head data.")

#     # Process Duo Synergy
#     update_synergy_batch(winners, True, tier)
#     update_synergy_batch(losers, False, tier)
    
# def update_synergy_batch(champ_ids, did_win, tier):
#     """
#     Calculates every duo combination on a team and updates the synergy_stats table.
#     """

#     # This prevents duplicates rows in the DB
#     # e.g. (1, 53) and (53, 1) will appear as (1, 53) in the DB
#     pairs = list(itertools.combinations(sorted(champ_ids), 2))

#     for c_a, c_b in pairs:
#         supabase.rpc("update_synergy", {
#             "c_a": c_a, "c_b": c_b, "t": tier, "is_win": did_win
#         }).execute()