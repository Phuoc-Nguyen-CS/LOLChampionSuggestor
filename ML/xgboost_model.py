import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
import optuna 
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, KFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from supabase import create_client, Client
from dotenv import load_dotenv

# Inject project root into path to ensure model_adapter is importable
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model_adapter import XGBoostChampionAdapter

load_dotenv()

class DraftModelTrainer:
    def __init__(self):
        url = os.getenv("TEMP_URL")
        key = os.getenv("TEMP_KEY")
        
        self.client = create_client(url, key)
        
        # 1. DIRECTORY FIX: Get the absolute path of the directory this script is in
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.models_dir = os.path.join(self.script_dir, "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.feature_cols = [
            'engage_delta', 
            'catch_delta', 
            'range_delta', 
            'tankiness_delta',
            'dpm_delta',
            'synergy_delta',
            'counter_delta'
        ]
        self.target_col = 'label'
        # self.scaler = StandardScaler()
        self.scaler = RobustScaler()
        self.best_params = None
        self.model = None

    def load_data(self):
        # Update path to be absolute
        cache_path = os.path.join(self.models_dir, "training_cache.csv")
        
        if os.path.exists(cache_path):
            print("[CACHE] Loading training data from local storage...")
            df = pd.read_csv(cache_path)
        else:
            print("[DATABASE] Pulling training data and creating local cache...")
            response = self.client.table("xgboost_training_view").select("*").execute()
            
            if not response.data:
                raise ValueError("No data returned from the database.")
                
            df = pd.DataFrame(response.data).fillna(0)
            df.to_csv(cache_path, index=False)

        # CRITICAL: Convert decimal-strings from Supabase View to floats for XGBoost
        for col in ['dpm_delta', 'synergy_delta', 'counter_delta']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        print(f"[DEBUG] Row Count: {len(df)}")
        
        df = df.sort_values(by="match_id").reset_index(drop=True)
        
        X = df[self.feature_cols]
        y = df[self.target_col].astype(int)
        
        # Split FIRST, transform SECOND
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15)
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        X_train = pd.DataFrame(X_train_scaled, columns=self.feature_cols)
        X_test = pd.DataFrame(X_test_scaled, columns=self.feature_cols)
        
        return X_train, X_test, y_train, y_test

    def tune_hyperparameters(self, x_train, y_train):
        print("[OPTUNA] Searching for optimal parameters...")

        def objective(trial):
            param = {
                'objective': 'binary:logistic',
                'n_estimators': trial.suggest_int('n_estimators', 100, 600),
                'max_depth': trial.suggest_int('max_depth', 2, 4),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.05),
                'subsample': trial.suggest_float('subsample', 0.6, 0.9),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 0.7),
                'min_child_weight': trial.suggest_int('min_child_weight', 5, 20),
                'random_state': 42,
                'early_stopping_rounds': 20
            }
            
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            scores = []
            
            for t_idx, v_idx in kf.split(x_train):
                xt, xv = x_train.iloc[t_idx], x_train.iloc[v_idx]
                yt, yv = y_train.iloc[t_idx], y_train.iloc[v_idx]
                
                model = xgb.XGBClassifier(**param)
                model.fit(xt, yt, eval_set=[(xv, yv)], verbose=False)
                
                probs = model.predict_proba(xv)[:, 1]
                scores.append(roc_auc_score(yv, probs))
                
            return np.mean(scores)

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=30)
        self.best_params = study.best_params
        print(f"[OPTUNA] Best CV ROC-AUC: {study.best_value:.4f}")

    def finalize_and_explain(self, x_train, y_train, x_test, y_test):
        print("[MODEL] Finalizing production model...")
        
        final_params = self.best_params.copy()
        final_params['early_stopping_rounds'] = 50
        
        xt, xv, yt, yv = train_test_split(x_train, y_train, test_size=0.1, random_state=42)
        
        self.model = xgb.XGBClassifier(**final_params)
        self.model.fit(xt, yt, eval_set=[(xv, yv)], verbose=False)

        # Wrap with adapter to verify production-readiness during evaluation
        production_model = XGBoostChampionAdapter(self.model, self.feature_cols)
        
        probs = production_model.predict_proba(x_test)[:, 1]
        print(f"[FINAL STATS] True Unbiased ROC-AUC: {roc_auc_score(y_test, probs):.4f}")

        print("[SHAP] Generating logic visualization...")
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(x_test)
        
        plt.figure(figsize=(10, 6))
        shap.summary_plot(shap_values, x_test, feature_names=self.feature_cols, show=False)
        
        # Update path to be absolute
        shap_path = os.path.join(self.models_dir, "shap_summary.png")
        plt.savefig(shap_path, bbox_inches='tight')

    def save_artifacts(self):
        # Update paths to be absolute
        model_path = os.path.join(self.models_dir, "champion_model.json")
        features_path = os.path.join(self.models_dir, "feature_list.json")
        
        self.model.save_model(model_path)
        with open(features_path, 'w') as f:
            json.dump(self.feature_cols, f)
        print("[STORAGE] Artifacts saved to ML/models directory. System is ready for Inference.")

if __name__ == "__main__":
    trainer = DraftModelTrainer()
    x_train, x_test, y_train, y_test = trainer.load_data()
    trainer.tune_hyperparameters(x_train, y_train)
    trainer.finalize_and_explain(x_train, y_train, x_test, y_test)
    trainer.save_artifacts()