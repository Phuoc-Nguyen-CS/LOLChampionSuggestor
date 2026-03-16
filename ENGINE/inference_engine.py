import xgboost as xgb
import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from champion_profiles import populate_champion_profiles

class DraftInference:
    def __init__(self):
        # Using XGBRegressor for better compatibility with DataFrames
        base_path = os.path.dirname(__file__)
        print(base_path)
        # Build paths to the models folder inside ML
        counter_path = os.path.join(base_path, "models", "champion_model.json")
        synergy_path = os.path.join(base_path, "models", "synergy_model.json")

        self.counter_model = xgb.XGBRegressor()
        self.counter_model.load_model(counter_path)
        
        self.synergy_model = xgb.XGBRegressor()
        self.synergy_model.load_model(synergy_path)

        # Load your profiles for the "Available Champions" list    
        self.all_profiles = populate_champion_profiles()

    def get_available_champions(self, picked_champs):
        # Filters out any champion already in the game
        picked_names = [c['name'] for c in picked_champs]
        return [c for c in self.all_profiles if c['name'] not in picked_names]

    def build_feature_row(self, candidate, opponent, rank, pos):
        """Matches the 13 columns in xgboost_training_view"""
        data = {
            'position': [pos],
            'rank_tier': [rank],
            'duration_bucket': ['MID_25_35'],
            'a_dmg': [candidate['damage_type']],
            'a_role': [candidate['role_class']],
            'a_cc': [candidate['cc_tier']],
            'b_dmg': [opponent['damage_type']],
            'b_role': [opponent['role_class']],
            'b_cc': [opponent['cc_tier']],
            # We provide 'average' performance stats for a neutral prediction
            'a_cs_win_rate': [0.5],
            'a_kill_win_rate': [0.5],
            'a_obj_win_rate': [0.5],
            'a_util_win_rate': [0.5]
        }
        df = pd.DataFrame(data)
        
        # XGBoost requires categorical columns to be explicitly typed
        cat_cols = ['position', 'rank_tier', 'duration_bucket', 'a_dmg', 'a_role', 'b_dmg', 'b_role']
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
            'b_cc': [ally['cc_tier']]
        }
        df = pd.DataFrame(data)
        
        cat_cols = ['rank_tier', 'a_dmg', 'a_role', 'b_dmg', 'b_role']
        for col in cat_cols:
            df[col] = df[col].astype('category')
        return df

    def suggest_best_pick(self, allies, enemies, rank, position):
        recommendations = []
        available_champs = self.get_available_champions(allies + enemies)

        for candidate in available_champs:
            # 1. Calculate Counter Score (vs all 5 enemies)
            c_score = 0
            if enemies:
                for enemy in enemies:
                    row = self.build_feature_row(candidate, enemy, rank, position)
                    c_score += float(self.counter_model.predict(row)[0])
                c_score /= len(enemies)
            else:
                c_score = 0.5 # Default if no enemies picked yet

            # 2. Calculate Synergy Score (vs all current allies)
            s_score = 0
            if allies:
                for ally in allies:
                    row = self.build_synergy_row(candidate, ally, rank)
                    s_score += float(self.synergy_model.predict(row)[0])
                s_score /= len(allies)
            else:
                s_score = 0.5

            # 3. Final Weighted Average (60% Counter / 40% Synergy)
            final_score = (c_score * 0.6) + (s_score * 0.4)
            recommendations.append({"name": candidate['name'], "score": final_score})

        return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:3]