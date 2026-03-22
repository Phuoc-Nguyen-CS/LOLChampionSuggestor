import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from supabase import create_client, Client
import json

class DraftModelTrainer:
    """
    Trainer for the League of Legends Draft Prediction Model.
    Utilizes Layer 3 Deltas to predict win probability.
    """

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
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
                offset == chunk_size 
                print(f"    Loaded {len(all_data)} rows")
            df = pd.DataFrame(all_data)
        except Exception as e:
            print(f"[CRITICAL] Failed to grab data from xgboost_training_view: {str(e)}")