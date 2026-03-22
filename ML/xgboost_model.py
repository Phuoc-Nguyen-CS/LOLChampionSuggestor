import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from supabase import create_client, Client
import json
from dotenv import load_dotenv

class DraftModelTrainer:
    """
    Trainer for the League of Legends Draft Prediction Model.
    Utilizes Layer 3 Deltas to predict win probability.
    """

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        self.model = None
        
        #  Layer 1 (DNA) and Layer 2 (Behavior) Deltas
        self.feature_cols = [
            'range_delta', 'mobility_delta', 'ms_delta', 'lockdown_delta',
            'pick_delta', 'save_delta', 'steroid_delta', 'stealth_delta',
            'phys_dmg_delta', 'magic_dmg_delta', 'tankiness_delta', 'waveclear_delta'
        ]
        self.target_col = 'label'
    
    def init_connection(self):
        """Initializes Supabase client"""
        try:
            if not self.supabase_url or not self.supabase_key:
                raise ValueError("[ERROR] Missing Supabase credentials in environment variables.")
            self.client = create_client(self.supabase_url, self.supabase_key)
            print("[INFO] Connected to Supabase successfully")
        except Exception as e:
            print(f"[CRITICAL] Connection failed: {str(e)}")
            raise

    def load_training_data(self) -> pd.DataFrame:
        """Fetches the aggregated deltas from Layer 3 view."""
        print("[DATABASE] Pulling training data from xgboost_training_view...")
        all_data = []
        chunk_size = 1000
        offset = 0

        try:
            # Pagination to grab all data in case there is more
            while True:
                response = self.client.table("xgboost_training_view")\
                    .select("*")\
                    .range(offset, offset + chunk_size - 1)\
                    .execute()
                
                data = response.data 
                if not data:
                    break

                all_data.extend(data)
                offset += chunk_size 
                print(f"    Loaded {len(all_data)} rows")
            
            if not all_data:
                print("[WARNING] No data found in xgboost_training_view.")
                return pd.DataFrame()
            
            df = pd.DataFrame(all_data)
            return df 
        
        except Exception as e:
            print(f"[CRITICAL] Failed to grab data from xgboost_training_view: {str(e)}")
            return pd.DataFrame()
        
    def preprocess(self, df: pd.DataFrame):
        """Prepares the dataset for training. Tries to avoid data leakage"""
        # Ensures all columns are numeric and handles nulls in case (there shouldn't be any)
        for col in self.feature_cols:
            print(col)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        x = df[self.feature_cols]
        y = df[self.target_col].astype(float)

        return train_test_split(x, y, test_size=0.2, random_state=42)

    def train_model(self, x_train, y_train): 
        """Trains the XGBoost Regressor"""
        print("[MODEL] Initializing XGBoost training...")

        params = {
            'objective': 'reg:squarederror',
            'n_estimators': 1000,
            'learning_rate': 0.05,
            'max_depth': 6,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'n_jobs': -1,
            'random_state': 42
        }

        self.model = xgb.XGBRegressor(**params)

        # early stop to try and prevent overfitting
        self.model.fit(
            x_train, y_train,
            eval_set=[(x_train, y_train)],
            verbose=False
        )
        print("[MODEL] Training Completed.")
    
    def evaluate(self, x_test, y_test):
        """Evaluates model performance and explains feature"""
        predictions = self.model.predict(x_test)
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions)

        print(f"[STATS] Mean Absolute Error: {mae:.4f}")
        print(f"[STATS] R2 Score: {r2:.4f}")

        importance = self.model.feature_importances_
        feature_importance = sorted(zip(self.feature_cols, importance), key=lambda x: x[1], reverse=True)

        print("[ANALYSIS] Top Performance Drivers:")
        for feat, score in feature_importance[:5]:
            print(f" - {feat}: {score:.4f}")
    
    def save_artifacts(self, model_path="champion_model.json", feature_path="feature_list.json"):
        """Saves the model and feature list for the LCU inference engine."""
        try:
            self.model.save_model(model_path)
            with open(feature_path, 'w') as f:
                json.dump(self.feature_cols, f)
            print(f"[STORAGE] Model artifacts saved to {model_path} and {feature_path}.")    
        except Exception as e:
            print(f"[ERROR] failed to save: {str(e)}")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    trainer.init_connection()

    data = trainer.load_training_data()
    x_train, x_test, y_train, y_test = trainer.preprocess(data)

    trainer.train_model(x_train, y_train)
    trainer.evaluate(x_test, y_test)
    trainer.save_artifacts()