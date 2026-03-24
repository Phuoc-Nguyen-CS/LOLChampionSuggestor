import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
from supabase import create_client, Client
from typing import List, Dict, Optional
import itertools

class InferenceEngine:
    """
    3-Layer Inference Engine with Proactive Logic.
    Synchronized with the new 'Proactive Engage' SQL architecture.
    """

    def __init__(self, model_path: str, feature_list_path: str, db_client: Optional[Client] = None):
        self.model_path = model_path
        self.feature_list_path = feature_list_path
        self.client = db_client
        
        self.model: Optional[xgb.XGBClassifier] = None
        self.feature_cols: List[str] = []
        self.champion_data: Optional[pd.DataFrame] = None
        self.role_data: Dict[str, List[str]] = {}
        self.synergy_map: Dict[tuple, float] = {} # Key: (lower_champ_id, higher_champ_id)

    def initialize(self) -> None:
        """Loads artifacts and synchronizes Champion DNA + Behavior."""
        self._load_model_artifacts()
        self._load_role_data()
        if self.client:
            self._fetch_and_merge_champion_data()
            self._load_synergy_map()

    def _load_model_artifacts(self) -> None:
        try:
            with open(self.feature_list_path, 'r') as f:
                self.feature_cols = json.load(f)
            self.model = xgb.XGBClassifier()
            self.model.load_model(self.model_path)
            print(f"[INFO] Engine Loaded: Classifier found {len(self.feature_cols)} features.")
        except Exception as e:
            print(f"[ERROR] Initialization failed: {str(e)}")
            raise

    def _load_role_data(self) -> None:
        role_path = os.path.join(os.path.dirname(__file__), "champion_roles.json")
        try:
            with open(role_path, 'r') as f:
                self.role_data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Role data load error: {e}")

    def _fetch_and_merge_champion_data(self) -> None:
        try:
            dna = pd.DataFrame(self.client.table("champion_dna").select("*").execute().data)
            beh = pd.DataFrame(self.client.table("v_champion_behavior_agg").select("*").execute().data)
            merged = pd.merge(dna, beh, on="champion_id", how="left")
            
            # Sanitization: Prevent NaNs from breaking the math
            num_cols = merged.select_dtypes(include=[np.number]).columns
            merged[num_cols] = merged[num_cols].fillna(merged[num_cols].median())
            
            merged['lookup_name'] = merged['name'].str.lower().str.strip()
            self.champion_data = merged
        except Exception as e:
            print(f"[ERROR] Database Sync failure: {str(e)}")
            raise
    
    def _load_synergy_map(self) -> None:
        """Fetches the pre-calculated Lift scores from the database."""
        try:
            res = self.client.table("champion_synergy_map").select("champ_a, champ_b, synergy_lift").execute()
            self.synergy_map = {
                tuple(sorted([int(r['champ_a']), int(r['champ_b'])])): float(r['synergy_lift'])
            for r in res.data
            }
        except Exception as e:
            print(f"[ERROR] Failed to load synergy map: {e}")
    def get_stats(self, name: str) -> pd.Series:
        lookup = str(name).lower().strip()
        row = self.champion_data[self.champion_data['lookup_name'] == lookup]
        if row.empty: raise ValueError(f"Champion {name} not found.")
        return row.iloc[0]

    def calculate_battle_deltas(self, allies: List[str], enemies: List[str]) -> Dict[str, float]:
        """Performs Asymmetric math including Algorithmic Synergy."""
        a_stats = [self.get_stats(c) for c in allies]
        e_stats = [self.get_stats(c) for c in enemies]

        # --- 1. Stat Extraction (Same as before) ---
        a_max_lock = max([s.get('lockdown_score', 0) for s in a_stats], default=0)
        a_max_pick = max([s.get('pick_potential', 0) for s in a_stats], default=0)
        a_total_range = sum([s.get('attack_range', 0) for s in a_stats])
        a_total_tank = sum([s.get('avg_self_mitigated_per_min', 0) for s in a_stats])

        e_max_peel = max([s.get('peel_score', 0) for s in e_stats], default=0)
        e_max_mobi = max([s.get('effective mobility', 0) for s in e_stats], default=0)
        e_total_range = sum([s.get('attack_range', 0) for s in e_stats])
        e_total_tank = sum([s.get('avg_self_mitigated_per_min', 0) for s in e_stats])

        # --- 2. Algorithmic Synergy Logic ---
        def get_team_synergy_avg(stats_list):
            if len(stats_list) < 2: return 0.0
            
            ids = [int(s['champion_id']) for s in stats_list]
            # itertools.combinations finds all 10 pairs automatically
            pairs = list(itertools.combinations(ids, 2))
            
            total_lift = 0.0
            for p1, p2 in pairs:
                # Sort IDs so (1, 2) matches the key regardless of draft order
                key = tuple(sorted([p1, p2]))
                total_lift += self.synergy_map.get(key, 0.0)
                
            return total_lift / 10 # Average lift across all pairs

        a_synergy = get_team_synergy_avg(a_stats)
        e_synergy = get_team_synergy_avg(e_stats)

        # --- 3. Feature Mapping ---
        return {
            'engage_delta': float((a_max_pick + a_max_lock) - e_max_peel),
            'catch_delta': float(a_max_lock - e_max_mobi),
            'range_delta': float(a_total_range - e_total_range),
            'tankiness_delta': float(a_total_tank - e_total_tank),
            'synergy_delta': float(a_synergy - e_synergy) 
        }

    def predict_win_probability(self, allies: List[str], enemies: List[str]) -> float:
        try:
            deltas = self.calculate_battle_deltas(allies, enemies)
            
            # Use the feature_list to ensure correct input order for the model
            vector = pd.DataFrame([{col: deltas.get(col, 0.0) for col in self.feature_cols}])
            
            # predict_proba returns [Loss %, Win %]. We want index 1.
            return float(self.model.predict_proba(vector)[0][1])
        except Exception as e:
            print(f"[ERROR] Logic Error: {e}")
            return 0.5

class DraftSimulator:
    """Manages picks and candidate filtering."""
    def __init__(self, engine: InferenceEngine):
        self.engine = engine
        self.pos_map = {
            "TOP": ["TOP"], "JUNGLE": ["JUNGLE"], "SUPPORT": ["SUPPORT"],
            "MID": ["MIDDLE"], "BOT": ["BOTTOM", "BOT"]
        }

    def suggest_picks(self, allies: List[str], enemies: List[str], position: str, top_n: int = 5) -> List[Dict]:
        target_roles = self.pos_map.get(position.upper(), [position.upper()])
        candidates = self.engine.champion_data['name'].tolist()
        
        results = []
        for candidate in candidates:
            if candidate in allies or candidate in enemies: continue
            
            valid_roles = self.engine.role_data.get(candidate, [])
            if not any(r in valid_roles for r in target_roles): continue
                
            prob = self.engine.predict_win_probability(allies + [candidate], enemies)
            results.append({"name": candidate, "win_prob": prob})
                
        return sorted(results, key=lambda x: x["win_prob"], reverse=True)[:top_n]