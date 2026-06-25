import os
import sys
from dotenv import load_dotenv
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from detection.datastore import MangoDataStore
from ml_regime import fetch_and_prepare_data, fetch_closed_signals, generate_features, label_data_with_outcomes

def check_data():
    # Fetch data
    scrapes_df = fetch_and_prepare_data()
    print(f"Total scrapes rows: {len(scrapes_df)}")
    
    signals_df = fetch_closed_signals()
    print(f"Total resolved signals: {len(signals_df)}")
    
    # Generate features
    features_df = generate_features(scrapes_df)
    print(f"Total generated feature samples (4h windows): {len(features_df)}")
    
    if not features_df.empty:
        # Label data
        labeled_df = label_data_with_outcomes(features_df, signals_df)
        counts = labeled_df['label'].value_counts()
        print(f"\nLabel counts: RANGING(0): {counts.get(0, 0)}, TRENDING(1): {counts.get(1, 0)}")
        sources = labeled_df['label_source'].value_counts()
        print(f"Label sources: {sources.to_dict()}")
        
        # Print a few examples of features vs labels
        print("\nExamples of Labeled Features:")
        print(labeled_df[['zone_escape_ratio', 'direction_alignment', 'range_expansion', 'eq_expansion_ratio', 'label', 'label_source']].tail(15))

if __name__ == "__main__":
    check_data()
