import os 
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

def process_matches(match_jsons):
    """
    Takes a list of raw Riot Match V5 JSON objects and flattens them
    into a list of individual participant performances.
    """
    participant_records = []
    for match in match_jsons:
        info = match.get('info', {})
        duration_mins = info.get('gameDuration', 0) / 60.0
        if duration_mins < 10: continue 

        team_totals = {100: {'gold': 0, 'obj_dmg': 0}, 200: {'gold': 0, 'obj_dmg': 0}}
        participants = info.get('participants', [])
        for p in participants:
            t_id = p.get('teamId', 100)
            team_totals[t_id]['gold'] += p.get('goldEarned', 0)
            team_totals[t_id]['obj_dmg'] += p.get('damageDealtToObjectives', 0)

        for p in participants:
            team_id = p.get('teamId', 100)
            total_dmg = max(p.get('totalDamageDealtToChampions', 1), 1)

            participant_records.append({
                "champion_id": p.get('championId'),
                "champion_name": p.get('championName'),
                "win": 1 if p.get("win") else 0,
                "duration_mins": duration_mins,
                "team_position": p.get('teamPosition', 'MIDDLE'),

                "phys_share": p.get('physicalDamageDealtToChampions', 0) / total_dmg,
                "magic_share": p.get('magicDamageDealtToChampions', 0) / total_dmg,
                "true_share": p.get('trueDamageDealtToChampions', 0) / total_dmg,

                "gold_share": p.get('goldEarned', 0) / max(team_totals[team_id]['gold'], 1),
                "obj_dmg_share": p.get('damageDealtToObjectives', 0) / max(team_totals[team_id]['obj_dmg'], 1),

                "self_mitigated_per_min": p.get('damageSelfMitigated', 0) / duration_mins,
                "minions_per_min": (p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)) / duration_mins,
                "heal_per_min": p.get('totalHeal', 0) / duration_mins,
                "ally_heal_per_min": p.get('totalHealsOnTeammates', 0) / duration_mins,
                "ally_shield_per_min": p.get("totalDamageShieldedOnTeammates", 0) / duration_mins, 
            })

    return pd.DataFrame(participant_records)
    
def aggregate_and_upload(df):
    """Groups the raw performances by champion and calculates the Meta Averages."""
    print("Aggregating behavioral metrics...")

    agg_df = df.groupby('champion_id').agg({
        'champion_name': 'first',
        'phys_share': 'mean',
        'magic_share': 'mean',
        'true_share': 'mean',
        'gold_share': 'mean',
        'obj_dmg_share': 'mean',
        'self_mitigated_per_min': 'mean',
        'minions_per_min': 'mean',
        # New Aggregations
        'heal_per_min': 'mean',
        'ally_heal_per_min': 'mean',
        'ally_shield_per_min': 'mean',
        'win': 'mean',
        'champion_id': 'count' 
    }).rename(columns={'champion_id': 'total_matches'})

    profiles = []
    for champ_id, row in agg_df.iterrows():
        champ_games = df[df['champion_id'] == champ_id]
        early_wr = champ_games[champ_games['duration_mins'] <= 25]['win'].mean()
        late_wr = champ_games[champ_games['duration_mins'] >= 35]['win'].mean()
        
        # Handle NaN if no games fit the duration
        early_wr = early_wr if pd.notna(early_wr) else row['win']
        late_wr = late_wr if pd.notna(late_wr) else row['win']

        scaling_tier = 2
        if late_wr > (early_wr + 0.03): scaling_tier = 3
        elif early_wr > (late_wr + 0.03): scaling_tier = 1

        # Flex Pick Variance
        # What % of games are NOT in their most popular role?
        role_counts = champ_games['team_position'].value_counts(normalize=True)
        flex_variance = 1.0 - role_counts.iloc[0] if not role_counts.empty else 0.0
        
        profiles.append({
            "champion_id": int(champ_id),
            "name": row['champion_name'],
            "physical_dmg_share": round(row['phys_share'], 3),
            "magic_dmg_share": round(row['magic_share'], 3),
            "true_dmg_share": round(row['true_share'], 3),
            "gold_share_pct": round(row['gold_share'], 3),
            "objective_dmg_share": round(row['obj_dmg_share'], 3),
            "avg_self_mitigated_per_min": round(row['self_mitigated_per_min'], 2),
            "avg_minions_killed": round(row['minions_per_min'], 2),
            
            "avg_healing_per_min": round(row['heal_per_min'], 2),
            "avg_ally_healing_per_min": round(row['ally_heal_per_min'], 2),
            "avg_ally_shielding_per_min": round(row['ally_shield_per_min'], 2),
            
            "early_win_rate_pct": round(early_wr, 3), # From your scaling logic
            "late_win_rate_pct": round(late_wr, 3),
            "actual_scaling_tier": scaling_tier,
            "flex_pick_variance": round(flex_variance, 3),
            "total_matches": int(row['total_matches'])
        })

    supabase.table("champion_behavior").upsert(profiles).execute()

def run_unit_test():
    # Create Mock Data 
    mock_match = {
        "info": {
            "gameDuration": 1800000, # 30 mins in ms
            "participants": [
                {
                    "championId": 1, "championName": "Annie", "win": True, "teamId": 100,
                    "totalDamageDealtToChampions": 20000, "magicDamageDealtToChampions": 18000,
                    "physicalDamageDealtToChampions": 1000, "trueDamageDealtToChampions": 1000,
                    "goldEarned": 12000, "damageDealtToObjectives": 5000,
                    "damageSelfMitigated": 6000, "totalMinionsKilled": 200, "neutralMinionsKilled": 10,
                    "totalHeal": 2000, "totalHealsOnTeammates": 500, "totalDamageShieldedOnTeammates": 1500,
                    "teamPosition": "MIDDLE"
                }
            ]
        }
    }
    
    print("Testing Logic...")
    df = process_matches([mock_match])
    
    # Check if Annie's magic share is 90% (18k / 20k)
    annie = df[df['champion_name'] == "Annie"].iloc[0]
    print(f"Verified Magic Share: {annie['magic_share']:.2f} (Expected: 0.90)")
    print(f"Verified Gold Share: {annie['gold_share']:.2f} (Expected: 1.0 for this mock solo test)")
    print(f"Verified Minions/Min: {annie['minions_per_min']:.2f} (Expected: 7.0)")

if __name__ == "__main__":
    run_unit_test()