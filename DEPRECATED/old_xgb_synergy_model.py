import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import data_loader
import os

def train_synergy_model():
    print("Starting Training Pipeline...")

    x, y, meta, weights = data_loader.get_synergy_training_data()

    # Split the training and testing
    x_train, x_test, y_train, y_test, w_train, w_test = train_test_split(
        x, y, weights, test_size=0.2, random_state=42
    )

    # Initialize the XGBoost Regressor
    model = xgb.XGBRegressor(
        tree_method="hist",
        enable_categorical=True,
        n_estimators=100,
        objective="reg:squarederror"
    )

    # Fitting the model
    print(f"Training on {len(x_train)} matchups...")
    model.fit(
        x_train, y_train, 
        sample_weight=w_train,
        eval_set=[(x_test, y_test)],
        verbose=False
    )

    # Evaluate
    predictions = model.predict(x_test)
    error = mean_absolute_error(y_test, predictions)
    print(f"Synergy Training Complete. Mean Absolute Error: {error:.4f}")

    # Save the model
    model_path = os.path.join(os.path.dirname(__file__), "models/synergy_model.json")
    model.save_model(model_path)
    print(f"Model saved to: {model_path}")

if __name__ == "__main__":
    train_synergy_model()