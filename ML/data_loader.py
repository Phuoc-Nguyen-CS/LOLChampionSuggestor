"""
data_load.py 

Handles supabase connection and converts the text
"""

import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import os 

def get_training_data():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)

    # Grab the view
    response = supabase.table("xgboost_training_view").select("*").execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        print("No data found in view")
        return None, None, None

    # Defining column groups
    # Omit details from XG so it doesn't consider this when training
    metadata_cols = ['champ_a_id', 'a_name', 'champ_b_id', 'b_name']
    
    # Trying to predict this value here
    target_col = 'a_win_rate'

    # Feature model used to learn "why" a win happens
    feature_cols = [
        'position', 'rank_tier', 'duration_bucket', 
        'a_dmg', 'a_role', 'a_cc',
        'b_dmg', 'b_role', 'b_cc',
        'a_cs_win_rate', 'a_kill_win_rate', 'a_obj_win_rate', 'a_util_win_rate'
    ]

    # Categorical data types
    categorical_features = [
        'position', 'rank_tier', 'duration_bucket', 
        'a_dmg', 'a_role', 'b_dmg', 'b_role'
    ]

    for col in categorical_features:
        df[col] = df[col].astype('category')

    # Split the data
    x = df[feature_cols] # Why the win happens
    y = df[target_col]   # The win chance
    meta = df[metadata_cols] # Translation Key (IDs -> Names)
    weights = df['total_sample_size'] # How much we trust each rows

    print(f"Loaded {len(df)} matchups for training.")
    return x, y, meta, weights

if __name__ == "__main__":
    x, y, meta, weights = get_training_data()
    print("\n--- Features ---")
    print(x.head())
    print("\n--- Metadata (Omitted) ---")
    print(meta.head())