import xgboost as xgb
import pandas as pd
import os
import sys
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from champion_profiles import get_profiles_from_db


class DraftInference:
    def __init__(self):
        # Using XGBRegressor for better compatibility with DataFrames
        base_path = os.path.dirname(__file__)

        # Build paths to the models folder inside ML
        counter_path = os.path.normpath(os.path.join(base_path, "..", "ML", "models", "champion_model.json"))
        synergy_path = os.path.normpath(os.path.join(base_path, "..", "ML", "models", "synergy_model.json"))

        self.counter_model = xgb.XGBRegressor()
        self.counter_model.load_model(counter_path)
        
        self.synergy_model = xgb.XGBRegressor()
        self.synergy_model.load_model(synergy_path)

        # Load your profiles for the "Available Champions" list    
        self.all_profiles = get_profiles_from_db()
                
        with open(os.path.join(base_path, "champion_roles.json"), "r") as f:
            self.role_guardrails = json.load(f)

    def get_available_champions(self, picked_champs, requested_position):
        # Filters out any champion already in the game
        picked_names = [c['name'] for c in picked_champs]
        valid_candidates = []

        for c in self.all_profiles:
            # Is champ in game?
            name = c['name']
            if name in picked_names:
                continue

            # Is champ viable in the role?
            viable_roles = self.role_guardrails.get(name, [])
            if requested_position in viable_roles:
                valid_candidates.append(c)

        # print(f"The valid candidates are:\n{valid_candidates}")
        return valid_candidates

    def build_feature_row(self, candidate, opponent, rank, pos):
        """Matches the 13 columns in xgboost_training_view"""
        data = {
            'position': [pos],
            'rank_tier': [rank],
            'duration_bucket': ['MID_25_35'],
            'a_dmg': [candidate['damage_type']],
            'a_role': [candidate['role_class']],
            'a_cc': [candidate['cc_tier']],
            'a_utility': [candidate.get('utility_tier', 1)],
            'b_dmg': [opponent['damage_type']],
            'b_role': [opponent['role_class']],
            'b_cc': [opponent['cc_tier']],
            'b_utility': [opponent.get('utility_tier', 1)]
        }
        df = pd.DataFrame(data)
        
        # XGBoost requires categorical columns to be explicitly typed
        cat_cols = [
            'position', 'rank_tier', 'duration_bucket', 
            'a_dmg', 'a_role', 'a_cc', 'a_utility',
            'b_dmg', 'b_role', 'b_cc', 'b_utility'
        ]
        for col in cat_cols:
            df[col] = df[col].astype('category')
        return df

    def build_synergy_row(self, candidate, ally, rank):
        """Matches the columns in xgboost_synergy_view"""
        data = {
        'rank_tier': [rank],
        'a_dmg': [candidate['damage_type']],
        'a_role': [candidate['role_class']],
        'a_cc': [candidate['cc_tier']],
        'b_dmg': [ally['damage_type']],
        'b_role': [ally['role_class']],
        'b_cc': [ally['cc_tier']],
        'a_utility': [candidate.get('utility_tier', 1)], 
        'b_utility': [ally.get('utility_tier', 1)],     
    }
        df = pd.DataFrame(data)
        
        cat_cols = [
            'rank_tier', 
            'a_dmg', 'a_role', 'a_cc', 'a_utility',
            'b_dmg', 'b_role', 'b_cc', 'b_utility'
        ]
        for col in cat_cols:
            df[col] = df[col].astype('category')
        return df

    def suggest_best_pick(self, allies, enemies, rank, position):
        recommendations = []
        # Filter candidates based on viable positions
        available_champs = self.get_available_champions(allies + enemies, position)

        for candidate in available_champs:
            # --- COUNTER SCORE CALCULATION (Weighted by Predicted Roles) ---
            c_score = 0
            if enemies:
                total_weight = 0
                weighted_c_score = 0
                
                for enemy in enemies:
                    # Get the predicted roles for this enemy from our JSON
                    predicted_roles = self.role_guardrails.get(enemy['name'], [])
                    
                    # Determine weight: 3x if they could be our direct lane opponent, 1x otherwise
                    # If roles are unknown/empty, we treat as a standard 1x weight
                    weight = 3.0 if position in predicted_roles else 1.0
                    
                    # Build the row and predict
                    row = self.build_feature_row(candidate, enemy, rank, position)
                    prediction = float(self.counter_model.predict(row)[0])
                    
                    weighted_c_score += (prediction * weight)
                    total_weight += weight
                
                c_score = weighted_c_score / total_weight
            else:
                c_score = 0.5

            # --- SYNERGY SCORE CALCULATION ---
            s_score = 0
            if allies:
                for ally in allies:
                    row = self.build_synergy_row(candidate, ally, rank)
                    s_score += float(self.synergy_model.predict(row)[0])
                s_score /= len(allies)
            else:
                s_score = 0.5

            # --- FINAL WEIGHTING AND PENALTIES ---
            # 60% Counter Logic / 40% Synergy Logic
            final_score = (c_score * 0.6) + (s_score * 0.4)

            # Apply the "Mage Bot" Penalty to offset mage bot high winrate
            ally_damage_types = [a['damage_type'] for a in allies] 
            if candidate.get('damage_type') in ally_damage_types:
                count = ally_damage_types.count(candidate['damage_type'])
                if count >= 2:
                    # Heavy penalty for 3+ of same damage type, minor for 2
                    final_score -= 0.03 * count

            recommendations.append({"name": candidate['name'], "score": final_score})

        # Return Top 3 recommendations
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:3]