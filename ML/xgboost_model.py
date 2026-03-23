import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from supabase import create_client, Client
import json

class DraftModelTrainer:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        
        # New Asymmetric Counter-Play Features
        self.feature_cols = [
            'anti_dive_score', 
            'kiting_delta', 
            'frontline_survival_index', 
            'catch_delta', 
            'raw_range_delta'
        ]
        self.target_col = 'label'
        self.scaler = StandardScaler()

    def init_connection(self):
        self.client = create_client(self.supabase_url, self.supabase_key)
        print("[INFO] Connected to Supabase.")

    def load_training_data(self) -> pd.DataFrame:
        print("[DATABASE] Pulling training data from xgboost_training_view...")
        all_data = []
        offset, chunk_size = 0, 1000
        while True:
            res = self.client.table("xgboost_training_view").select("*").range(offset, offset + chunk_size - 1).execute()
            if not res.data: break
            all_data.extend(res.data)
            offset += chunk_size
            print(f"    Loaded {len(all_data)} rows")
        return pd.DataFrame(all_data)

    def preprocess(self, df: pd.DataFrame):
        """Cleans and standardizes the new counter-play features."""
        if df.empty: return None
        
        # Ensure only the new features are processed
        df = df.fillna(0)
        for col in self.feature_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Scaling is critical now that we have indices like 'frontline_survival' 
        # which have different units than 'anti_dive'
        df[self.feature_cols] = self.scaler.fit_transform(df[self.feature_cols])

        X = df[self.feature_cols]
        y = df[self.target_col].astype(int)
        
        return train_test_split(X, y, test_size=0.15, random_state=42)

    def train_model(self, x_train, y_train, x_test, y_test):
        print("[MODEL] Training Asymmetric Classifier...")
        
        params = {
            'objective': 'binary:logistic',
            'n_estimators': 500,
            'learning_rate': 0.05,
            'max_depth': 3, 
            'min_child_weight': 10,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'early_stopping_rounds': 50,
            'random_state': 42
        }

        self.model = xgb.XGBClassifier(**params)
        self.model.fit(
            x_train, y_train,
            eval_set=[(x_test, y_test)],
            verbose=False
        )

    def evaluate(self, x_test, y_test):
        probs = self.model.predict_proba(x_test)[:, 1]
        print(f"[STATS] ROC-AUC Score: {roc_auc_score(y_test, probs):.4f}")
        
        importance = sorted(zip(self.feature_cols, self.model.feature_importances_), key=lambda x: x[1], reverse=True)
        print("[ANALYSIS] Win Condition Importance:")
        for feat, score in importance:
            print(f" - {feat}: {score:.4f}")

    def save_artifacts(self):
        # Save both model and feature list for the InferenceEngine to use
        self.model.save_model("models/champion_model.json")
        with open("models/feature_list.json", 'w') as f:
            json.dump(self.feature_cols, f)
        print("[STORAGE] Updated artifacts saved.")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    trainer.init_connection()
    data = trainer.load_training_data()
    x_train, x_test, y_train, y_test = trainer.preprocess(data)
    trainer.train_model(x_train, y_train, x_test, y_test)
    trainer.evaluate(x_test, y_test)