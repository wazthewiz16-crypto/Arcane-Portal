import os
import sys
from pathlib import Path
import joblib
import pandas as pd

model_path = Path("detection/ml_regime_model.pkl")
if not model_path.exists():
    print(f"Model does not exist at {model_path}")
    sys.exit(1)

model = joblib.load(model_path)
print(f"Loaded model: {model}")
if hasattr(model, "feature_importances_"):
    print(f"Feature importances: {dict(zip(['zone_escape_ratio', 'direction_alignment', 'range_expansion', 'eq_expansion_ratio'], model.feature_importances_))}")

# Define test cases
test_cases = [
    {
        "name": "Strongly Trending Heuristics (High values)",
        "zone_escape_ratio": 0.80,
        "direction_alignment": 0.85,
        "range_expansion": 2.2,
        "eq_expansion_ratio": 0.80
    },
    {
        "name": "Ranging Heuristics (Low values)",
        "zone_escape_ratio": 0.15,
        "direction_alignment": 0.20,
        "range_expansion": 0.3,
        "eq_expansion_ratio": 0.20
    },
    {
        "name": "First Run features (9:01 AM)",
        "zone_escape_ratio": 0.38,
        "direction_alignment": 0.33,
        "range_expansion": 0.3,
        "eq_expansion_ratio": 0.67
    },
    {
        "name": "Second Run features (9:06 AM)",
        "zone_escape_ratio": 0.75,
        "direction_alignment": 0.79,
        "range_expansion": 0.6,
        "eq_expansion_ratio": 0.71
    }
]

print("\nPredictions:")
for tc in test_cases:
    X = pd.DataFrame([{
        'zone_escape_ratio': tc['zone_escape_ratio'],
        'direction_alignment': tc['direction_alignment'],
        'range_expansion': tc['range_expansion'],
        'eq_expansion_ratio': tc['eq_expansion_ratio']
    }])
    pred = model.predict(X)[0]
    prob = model.predict_proba(X)[0]
    regime = "TRENDING" if pred == 1 else "RANGING"
    print(f"{tc['name']}:")
    print(f"  Features: escape={tc['zone_escape_ratio']:.2f}, align={tc['direction_alignment']:.2f}, range={tc['range_expansion']:.2f}, eq={tc['eq_expansion_ratio']:.2f}")
    print(f"  Prediction: {regime} (Raw pred={pred}, Probabilities={prob})")
