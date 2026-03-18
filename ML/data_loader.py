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

    all_data = []
    chunk_size = 1000
    offset = 0

    print("Fetching training data...")
    while True:
        # Grab the view
        response = supabase.table("xgboost_training_view")\
            .select("*")\
            .range(offset, offset + chunk_size - 1)\
            .execute()
        data = response.data 
        if not data:
            break

        all_data.extend(data)
        offset += chunk_size
        print(f"    Loaded {len(all_data)} rows")

    df = pd.DataFrame(all_data)

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
        'a_dmg', 'a_role', 'a_cc', 'a_utility', 'a_range',
        'b_dmg', 'b_role', 'b_cc', 'b_utility', 'b_range'
    ]

    # Categorical data types
    categorical_features = [
        'position', 'rank_tier', 'duration_bucket', 
        'a_dmg', 'a_role', 'a_cc', 'a_utility', 'a_range',
        'b_dmg', 'b_role', 'b_cc', 'b_utility', 'b_range'
    ]

    for col in categorical_features:
        if col in df.columns:
            df[col] = df[col].astype('category')
        else:
            print(f"WARNING: Expected column '{col}' is missing from the database view")

    # Split the data
    x = df[feature_cols] # Why the win happens
    y = df[target_col]   # The win chance
    meta = df[metadata_cols] # Translation Key (IDs -> Names)
    weights = df['total_sample_size'] # total size of the given data

    print(f"Loaded {len(df)} matchups for training.")
    return x, y, meta, weights

def get_synergy_training_data():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)
    
    print(f"Fetching training data...")
    
    offset = 0
    all_data = []
    chunk_size = 1000

    while(True):
        response = supabase.table("xgboost_synergy_view")\
            .select("*")\
            .range(offset, offset + chunk_size - 1)\
            .execute()
        data = response.data 
        if not data:
            break

        all_data.extend(data)
        offset += chunk_size
        print(f"    Loaded {len(all_data)} rows")

    df = pd.DataFrame(all_data)

    feature_cols = [
        'rank_tier', 
        'a_dmg', 'a_role', 'a_cc', 'a_range',
        'b_dmg', 'b_role', 'b_cc', 'b_range',
        'a_utility', 'b_utility'
    ]

    # Casting to category for XGBoost native support
    for col in feature_cols:
        df[col] = df[col].astype('category')

    return df[feature_cols], df['synergy_win_rate'], df[['champ_a_id', 'champ_b_id']], df['total_sample_size']

if __name__ == "__main__":
    x, y, meta, weights = get_training_data()
    print("\n--- Features ---")
    print(x.head())
    print("\n--- Metadata (Omitted) ---")
    print(meta.head())

    x, y, meta, weights = get_synergy_training_data()
    print("\n--- Features ---")
    print(x.head())
    print("\n--- Metadata (Omitted) ---")
    print(meta.head())