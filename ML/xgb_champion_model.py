"""
xgboost_trainer.py

Trainining models:
x = df[feature_cols] # Why the win happens
y = df[target_col] # Win chance
meta = df[metadata_cols] # Translation Key (IDs -> Names)
weights = df['total_sample_size'] # Size
"""
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import data_loader
import os 


def train_model():
    print("Starting Training Pipeline...")

    # Loading the data
    x, y, meta, weights = data_loader.get_training_data()

    if x is None or len(x) < 10:
        print("Not enough data to train.")
        return 
    
    # Split the training and testing
    # Prevents overfitting
    # test_size is hiding 20% of the matchups
    # After training it will be tested on the hidden matchups
    x_train, x_test, y_train, y_test, w_train, w_test = train_test_split(
        x, y, weights, test_size=0.2, random_state=42
    )

    # Initialize the XGBoost Regressor
    # Regressor because predicting a percentage (0.0 to 1.0)
    model = xgb.XGBRegressor(
        tree_method="hist", 
        enable_categorical=True, # Handles "roles" and "dmg" types
        n_estimators=100, # Number of trees
        learning_rate=0.1,
        max_depth=6,
        objective="reg:squarederror"
    )

    # Fitting the model
    print(f"Training on {len(x_train)} matchups...")
    model.fit(
        x_train, # Match up content
        y_train, # Win rate
        sample_weight=w_train,
        eval_set=[(x_test, y_test)],
        verbose=False
    )

    # Evaluate
    predictions = model.predict(x_test)
    error = mean_absolute_error(y_test, predictions)
    print(f"Training Complete. Mean Absolute Error: {error:.4f}")

    # Save the model
    model_path = os.path.join(os.path.dirname(__file__), "models/champion_model.json")
    model.save_model(model_path)
    print("Model saved to: {model_path}")

if __name__ == "__main__":
    train_model()
