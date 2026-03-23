import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
from supabase import create_client, Client
from typing import List, Dict, Optional

class InferenceEngine:
    """
    Evaluates 5v5 compositional deltas using an XGBoost model.
    Follows a strict 3-Layer architecture (DNA + Behavior -> Deltas -> Probability).
    """

    def __init__(self, model_path: str, feature_list_path: str, db_client: Optional[Client] = None):
        self.model_path = model_path
        self.feature_list_path = feature_list_path
        self.client = db_client
        
        self.model: Optional[xgb.XGBRegressor] = None
        self.feature_cols: List[str] = []
        self.champion_data: Optional[pd.DataFrame] = None
        self.role_data: Dict[str, List[str]] = {}

        # Internal mapping for data deltas
        self.delta_mapping = {
            'attack_range': 'range_delta',
            'effective mobility': 'mobility_delta',
            'ms_steroid': 'ms_delta',
            'lockdown_score': 'lockdown_delta',
            'pick_potential': 'pick_delta',
            'save_potential': 'save_delta',
            'peel_score': 'peel_delta',
            'ally_steroid': 'steroid_delta',
            'stealth_score': 'stealth_delta',
            'physical_dmg_share': 'phys_dmg_delta',
            'magic_share': 'magic_dmg_delta',
            'avg_self_mitigated_per_min': 'tankiness_delta',
            'avg_minions_killed': 'waveclear_delta'
        }

    def initialize(self) -> None:
        """Loads model artifacts, role data, and champion metadata."""
        self._load_model_artifacts()
        self._load_role_data()
        if self.client:
            self._fetch_and_merge_champion_data()

    def _load_model_artifacts(self) -> None:
        try:
            with open(self.feature_list_path, 'r') as f:
                self.feature_cols = json.load(f)
            self.model = xgb.XGBRegressor()
            self.model.load_model(self.model_path)
            print(f"[INFO] Loaded XGBoost model and {len(self.feature_cols)} features.")
        except Exception as e:
            print(f"[CRITICAL] Model artifact error: {str(e)}")
            raise

    def _load_role_data(self) -> None:
        """Loads role constraints from champion_roles.json."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        role_path = os.path.join(base_dir, "champion_roles.json")
        
        try:
            with open(role_path, 'r') as f:
                self.role_data = json.load(f)
            print(f"[INFO] Loaded role data from: {role_path}")
        except Exception as e:
            print(f"[ERROR] Failed to load champion_roles.json: {str(e)}")
            self.role_data = {}

    def _fetch_and_merge_champion_data(self) -> None:
        print("[DATABASE] Merging Layer 1 (DNA) and Layer 2 (Behavior)...")
        try:
            dna_res = self.client.table("champion_dna").select("*").execute()
            df_dna = pd.DataFrame(dna_res.data)
            
            behavior_res = self.client.table("v_champion_behavior_agg").select("*").execute()
            df_behavior = pd.DataFrame(behavior_res.data)

            merged = pd.merge(df_dna, df_behavior, on="champion_id", how="left")
            
            # Sanitization: Fill missing behavior with medians
            for col in self.delta_mapping.keys():
                if col in merged.columns and merged[col].isnull().any():
                    merged[col] = merged[col].fillna(merged[col].median())

            merged['lookup_name'] = merged['name'].str.lower().str.strip()
            self.champion_data = merged
            print(f"[INFO] Merged data for {len(self.champion_data)} champions.")
        except Exception as e:
            print(f"[CRITICAL] Database merge failure: {str(e)}")
            raise

    def get_champion_stats(self, champ_name: str) -> pd.Series:
        if self.champion_data is None:
            raise RuntimeError("[ERROR] Engine data not initialized.")
        lookup = str(champ_name).lower().strip()
        row = self.champion_data[self.champion_data['lookup_name'] == lookup]
        if row.empty:
            raise ValueError(f"Champion '{champ_name}' not found.")
        return row.iloc[0]

    # def calculate_deltas(self, allies: List[str], enemies: List[str]) -> Dict[str, float]:
    #     deltas = {name: 0.0 for name in self.delta_mapping.values()}
    #     for champ in allies:
    #         stats = self.get_champion_stats(champ)
    #         for raw, delta in self.delta_mapping.items():
    #             deltas[delta] += float(stats.get(raw, 0.0))
    #     for champ in enemies:
    #         stats = self.get_champion_stats(champ)
    #         for raw, delta in self.delta_mapping.items():
    #             deltas[delta] -= float(stats.get(raw, 0.0))
    #     return deltas
    def calculate_deltas(self, allies: List[str], enemies: List[str]) -> Dict[str, float]:
        """
        Rewritten to perform ASYMMETRIC math.
        Calculates how Ally Win Conditions match up against Enemy Threats.
        """
        # 1. Gather all stats for both teams
        a_stats = [self.get_champion_stats(c) for c in allies]
        e_stats = [self.get_champion_stats(c) for c in enemies]

        # 2. Extract Key Values
        a_max_peel = max([s.get('peel_score', 0) for s in a_stats], default=0)
        a_max_save = max([s.get('save_potential', 0) for s in a_stats], default=0)
        a_max_lockdown = max([s.get('lockdown_score', 0) for s in a_stats], default=0)
        a_total_range = sum([s.get('attack_range', 0) for s in a_stats])
        a_total_tankiness = sum([s.get('avg_self_mitigated_per_min', 0) for s in a_stats])

        e_max_pick = max([s.get('pick_potential', 0) for s in e_stats], default=0)
        e_max_mobility = max([s.get('effective mobility', 0) for s in e_stats], default=0)
        e_total_range = sum([s.get('attack_range', 0) for s in e_stats])
        e_total_dmg = sum([s.get('physical_dmg_share', 0) + s.get('magic_share', 0) for s in e_stats])

        # 3. Perform the Asymmetric Math (Must match SQL View)
        deltas = {
            'anti_dive_score': float((a_max_peel + a_max_save) - (e_max_pick + e_max_mobility)),
            'kiting_delta': float(a_total_range - (e_max_mobility * 150)),
            'frontline_survival_index': float(a_total_tankiness - e_total_dmg),
            'catch_delta': float(a_max_lockdown - e_max_mobility),
            'raw_range_delta': float(a_total_range - e_total_range)
        }

        return deltas

    def predict_win_probability(self, deltas: Dict[str, float]) -> float:
        try:
            features = pd.DataFrame([{col: deltas.get(col, 0.0) for col in self.feature_cols}])
            prob = float(self.model.predict(features)[0])
            return max(0.0, min(1.0, prob))
        except Exception as e:
            print(f"[ERROR] Prediction failure: {str(e)}")
            return 0.5

class DraftSimulator:
    """Simulates draft scenarios with strict role filtering."""
    def __init__(self, engine: InferenceEngine):
        self.engine = engine
        self.pos_map = {
            "MID": ["MIDDLE"], "MIDDLE": ["MIDDLE"],
            "BOT": ["BOTTOM", "BOT"], "BOTTOM": ["BOTTOM", "BOT"],
            "TOP": ["TOP"], "JUNGLE": ["JUNGLE"], "SUPPORT": ["SUPPORT"]
        }

    def evaluate_candidates(self, allies: List[str], enemies: List[str], 
                            position: str, top_n: int = 5) -> List[Dict]:
        results = []
        target_roles = self.pos_map.get(position.upper(), [position.upper()])
        
        # Pull all names from the loaded data
        all_champs = self.engine.champion_data['name'].tolist()
        
        for candidate in all_champs:
            if candidate in allies or candidate in enemies:
                continue
            
            # [ROLE FILTER] Use champion_roles.json
            valid_roles = self.engine.role_data.get(candidate, [])
            if not any(role in valid_roles for role in target_roles):
                continue
                
            try:
                deltas = self.engine.calculate_deltas(allies + [candidate], enemies)
                prob = self.engine.predict_win_probability(deltas)
                results.append({"name": candidate, "score": prob})
            except ValueError:
                continue
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]