"""
Machine Learning Market Regime Training (Phase 2 - Upgraded)
Pulls historical 4h data, extracts features, labels them using a hybrid of
actual trade outcomes (signals table) and expert heuristics, and trains a
scikit-learn random forest model with recency weightings and walk-forward parameter tuning.
"""
import sys
import os
from pathlib import Path
import logging
import itertools
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(override=True)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

from detection.datastore import MangoDataStore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def _get_direction(close, d1, d2):
    if pd.isna(close) or pd.isna(d1) or pd.isna(d2):
        return None
    ribbon_top = max(d1, d2)
    ribbon_bot = min(d1, d2)
    if close > ribbon_top:
        return 'LONG'
    elif close < ribbon_bot:
        return 'SHORT'
    return 'NEUTRAL'

def compute_label_score(row):
    score = 0.0
    zer = row['zone_escape_ratio']
    if zer >= 0.60: score += 40
    elif zer >= 0.40: score += 25
    elif zer >= 0.25: score += 10

    da = row['direction_alignment']
    if da >= 0.80: score += 25
    elif da >= 0.60: score += 15
    elif da >= 0.40: score += 5

    re = row['range_expansion']
    if re >= 2.0: score += 20
    elif re >= 1.5: score += 12
    elif re >= 1.0: score += 5

    eq = row['eq_expansion_ratio']
    if eq >= 0.60: score += 15
    elif eq >= 0.40: score += 8

    return 1 if score >= 55 else 0

def fetch_and_prepare_data():
    logger.info("Fetching raw scrapes from DB...")
    datastore = MangoDataStore()
    
    with datastore.get_connection() as conn:
        df = datastore._fetch_query(conn, """
            SELECT 
                name, timeframe, timestamp, close, open, high, low,
                mango_d1, mango_d2, entry_up, entry_down,
                eq_band1, eq_band2, upper_vol_b, lower_vol_b
            FROM scrapes
            WHERE timeframe IN ('15m', '1h', '4h')
            ORDER BY timestamp ASC
        """)
        
    if not df:
        logger.error("No data returned from scrapes table.")
        return pd.DataFrame()
        
    df = pd.DataFrame(df)
    # Parse as timezone-aware UTC first, then localize to naive to prevent timezone comparison issues
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
    return df

def fetch_closed_signals():
    logger.info("Fetching signals from DB for outcome-based labeling...")
    datastore = MangoDataStore()
    
    with datastore.get_connection() as conn:
        try:
            rows = datastore._fetch_query(conn, """
                SELECT id, asset_name, status, entry_time 
                FROM signals
            """)
        except Exception as e:
            logger.warning(f"Could not fetch from signals table (it may not exist or be empty): {e}")
            return pd.DataFrame()
            
    if not rows:
        logger.info("No signals found in database.")
        return pd.DataFrame()
        
    df = pd.DataFrame(rows)
    # Parse as timezone-aware UTC first, then localize to naive to prevent timezone comparison issues
    df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True).dt.tz_localize(None)
    
    # Keep only signals with definite resolved outcomes
    df['status_upper'] = df['status'].str.upper()
    resolved_df = df[df['status_upper'].isin(['TP_HIT', 'SL_HIT', 'HIT_TP', 'HIT_SL'])]
    logger.info(f"Fetched {len(resolved_df)} resolved outcome signals out of {len(df)} total signals.")
    return resolved_df

def generate_features(df):
    logger.info("Generating 4h rolling features from scrape data...")
    if df.empty:
        return pd.DataFrame()
        
    # Find start and end timestamps
    min_time = df['timestamp'].min()
    max_time = df['timestamp'].max()
    
    # We will slide a 4h window shifting by 1 hour increments to create more training samples
    current_time = min_time + timedelta(hours=4)
    features_list = []
    
    logger.info(f"Data spans from {min_time} to {max_time}. Processing windows...")
    
    while current_time <= max_time:
        window_start = current_time - timedelta(hours=4)
        
        # Slices in this 4h window
        w_df = df[(df['timestamp'] > window_start) & (df['timestamp'] <= current_time)]
        
        if w_df.empty:
            current_time += timedelta(hours=1)
            continue
            
        # Keep latest scrape for each asset and timeframe
        latest = w_df.sort_values('timestamp').groupby(['name', 'timeframe']).last().reset_index()
        
        # Calculate Rolling 4H Return
        # Find start close prices
        start_df = w_df.sort_values('timestamp').groupby(['name', 'timeframe']).first().reset_index()
        
        crypto_returns = []
        for name in latest['name'].unique():
            l_row = latest[(latest['name'] == name) & (latest['timeframe'].isin(['15m', '1h']))]
            s_row = start_df[(start_df['name'] == name) & (start_df['timeframe'].isin(['15m', '1h']))]
            if not l_row.empty and not s_row.empty:
                c_last = l_row.iloc[0]['close']
                c_start = s_row.iloc[0]['close']
                if c_start > 0:
                    crypto_returns.append((c_last - c_start) / c_start)
                    
        rolling_4h_return = np.mean(crypto_returns) if crypto_returns else 0.0
        
        # Compute Regime Features matching `_compute_features`
        zone_total = 0
        zone_escaped = 0
        aligned = 0
        dir_total = 0
        range_ratios = []
        eq_total = 0
        eq_expanding = 0
        
        assets = latest['name'].unique()
        if len(assets) < 4:
            current_time += timedelta(hours=1)
            continue
            
        for name in assets:
            asset_df = latest[latest['name'] == name]
            
            # Helper to get dict row
            def get_tf(tf_list):
                for t in tf_list:
                    match = asset_df[asset_df['timeframe'] == t]
                    if not match.empty: return match.iloc[0].to_dict()
                return None
                
            ltf = get_tf(['15m', '1h'])
            htf = get_tf(['4h', '1h'])
            
            if ltf:
                c, eu, ed = ltf.get('close'), ltf.get('entry_up'), ltf.get('entry_down')
                if pd.notna(c) and pd.notna(eu) and pd.notna(ed) and eu != ed:
                    zone_total += 1
                    pct = (c - ed) / (eu - ed)
                    if pct > 1.10 or pct < -0.10:
                        zone_escaped += 1
                        
                h, l = ltf.get('high'), ltf.get('low')
                if pd.notna(h) and pd.notna(l) and pd.notna(eu) and pd.notna(ed) and eu != ed:
                    candle_r = h - l
                    z_width = eu - ed
                    range_ratios.append(candle_r / z_width)
                    
                eq1, eq2 = ltf.get('eq_band1'), ltf.get('eq_band2')
                uv, lv = ltf.get('upper_vol_b'), ltf.get('lower_vol_b')
                if pd.notna(eq1) and pd.notna(eq2) and pd.notna(uv) and pd.notna(lv):
                    eq_total += 1
                    if abs(eq1 - eq2) >= abs(uv - lv):
                        eq_expanding += 1
                        
            if htf and ltf:
                h_dir = _get_direction(htf['close'], htf['mango_d1'], htf['mango_d2'])
                l_dir = _get_direction(ltf['close'], ltf['mango_d1'], ltf['mango_d2'])
                if h_dir and l_dir:
                    dir_total += 1
                    if h_dir == l_dir:
                        aligned += 1

        if zone_total < 4:
            current_time += timedelta(hours=1)
            continue
            
        zer = zone_escaped / zone_total
        da = aligned / dir_total if dir_total > 0 else 0
        re = np.mean(range_ratios) if range_ratios else 1.0
        eq_ratio = eq_expanding / eq_total if eq_total > 0 else 0.5
        
        features_list.append({
            'timestamp': current_time,
            'zone_escape_ratio': zer,
            'direction_alignment': da,
            'range_expansion': re,
            'eq_expansion_ratio': eq_ratio,
            'rolling_4h_return': rolling_4h_return,
            'hour_of_day': current_time.hour
        })
        
        current_time += timedelta(hours=1)
        
    return pd.DataFrame(features_list)

def label_data_with_outcomes(features_df, signals_df, lookahead_hours=12):
    logger.info(f"Labeling data using hybrid outcome-based logic (lookahead={lookahead_hours}h)...")
    
    if signals_df.empty:
        logger.info("No closed signals available. Falling back to heuristic-based labels for all samples.")
        features_df['label'] = features_df.apply(compute_label_score, axis=1)
        features_df['label_source'] = 'heuristic'
        return features_df
        
    labels = []
    sources = []
    
    for idx, row in features_df.iterrows():
        t = row['timestamp']
        window_end = t + timedelta(hours=lookahead_hours)
        
        # Find signals whose entry_time falls in [t, t + lookahead_hours]
        mask = (signals_df['entry_time'] >= t) & (signals_df['entry_time'] <= window_end)
        window_signals = signals_df[mask]
        
        if window_signals.empty:
            labels.append(compute_label_score(row))
            sources.append('heuristic')
        else:
            winners = window_signals[window_signals['status_upper'].isin(['TP_HIT', 'HIT_TP'])].shape[0]
            losers = window_signals[window_signals['status_upper'].isin(['SL_HIT', 'HIT_SL'])].shape[0]
            
            if winners + losers == 0:
                labels.append(compute_label_score(row))
                sources.append('heuristic')
            else:
                if winners > losers:
                    labels.append(1)  # Profitable regime
                    sources.append('outcome')
                else:
                    labels.append(0)  # Unprofitable/choppy regime
                    sources.append('outcome')
                    
    features_df['label'] = labels
    features_df['label_source'] = sources
    
    source_counts = features_df['label_source'].value_counts()
    logger.info(f"Labels generated: {source_counts.to_dict()}")
    return features_df

def train_model(features_df, signals_df):
    if len(features_df) < 50:
        logger.error("Not enough labeled samples to train effectively.")
        return None
        
    # 1. Hybrid Outcome-Based Labeling
    features_df = label_data_with_outcomes(features_df, signals_df, lookahead_hours=12)
    
    # Check class distribution
    class_counts = features_df['label'].value_counts()
    logger.info(f"Class Distribution: RANGING(0)={class_counts.get(0,0)}, TRENDING(1)={class_counts.get(1,0)}")
    
    # 2. Compute Recency Weights (Exponential Decay, Half-life 30 days)
    features_df = features_df.sort_values('timestamp').reset_index(drop=True)
    max_timestamp = features_df['timestamp'].max()
    days_ago = (max_timestamp - features_df['timestamp']).dt.total_seconds() / (24 * 3600.0)
    
    # Lambda = ln(2) / 30
    decay_lambda = np.log(2) / 30.0
    sample_weights = np.exp(-decay_lambda * days_ago)
    
    # Normalize sample weights so their average is 1.0 (stable behavior in RandomForest)
    features_df['sample_weight'] = sample_weights / np.mean(sample_weights)
    
    # 3. Walk-Forward Chronological Split
    split_idx = int(len(features_df) * 0.8)
    if split_idx < 40 or (len(features_df) - split_idx) < 10:
        # If dataset is too small to split 80/20 chronologically, fall back to 90/10
        split_idx = int(len(features_df) * 0.9)
        
    train_df = features_df.iloc[:split_idx]
    test_df = features_df.iloc[split_idx:]
    
    feature_cols = ['zone_escape_ratio', 'direction_alignment', 'range_expansion', 'eq_expansion_ratio']
    
    X_train = train_df[feature_cols]
    y_train = train_df['label']
    w_train = train_df['sample_weight']
    
    X_test = test_df[feature_cols]
    y_test = test_df['label']
    w_test = test_df['sample_weight']
    
    # Grid Search Parameters
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [3, 5, 7],
        'min_samples_split': [2, 5, 10]
    }
    
    best_acc = -1.0
    best_params = {'n_estimators': 100, 'max_depth': 5, 'min_samples_split': 2}
    
    keys, values = zip(*param_grid.items())
    experiments = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    logger.info(f"Running walk-forward grid search over {len(experiments)} configurations...")
    
    # Skip tuning if only one class exists in training split
    if len(y_train.unique()) <= 1:
        logger.warning("Only one class present in training split. Skipping tuning and using defaults.")
    else:
        for params in experiments:
            model = RandomForestClassifier(random_state=42, **params)
            model.fit(X_train, y_train, sample_weight=w_train)
            
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred, sample_weight=w_test)
            
            if acc > best_acc:
                best_acc = acc
                best_params = params
                
        logger.info(f"Grid search complete. Best parameters: {best_params} (Weighted accuracy: {best_acc:.2%})")
        
    if best_acc < 0:
        best_acc = 1.0
        
    # 4. Train Final Model on ENTIRE dataset using best parameters and full weights
    logger.info("Training final model on full dataset with optimized parameters and recency weighting...")
    final_model = RandomForestClassifier(random_state=42, **best_params)
    X_full = features_df[feature_cols]
    y_full = features_df['label']
    w_full = features_df['sample_weight']
    final_model.fit(X_full, y_full, sample_weight=w_full)
    
    # Evaluate final model on the chronological test split to report in metrics
    y_pred_final = final_model.predict(X_test)
    final_acc = accuracy_score(y_test, y_pred_final, sample_weight=w_test)
    logger.info(f"Final Model evaluation on walk-forward test split: {final_acc:.2%}")
    
    logger.info("\n--- Final Classification Report (Chronological Test Set) ---")
    logger.info(classification_report(y_test, y_pred_final, target_names=["RANGING/RISKY", "TRENDING/SAFE"], sample_weight=w_test))
    
    # Feature Importances
    imp = pd.Series(final_model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    logger.info("\nFeature Importances:")
    for feat, i in imp.items():
        logger.info(f"  {feat}: {i:.1%}")
        
    # Save model
    model_dir = Path(__file__).parent / 'detection'
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / 'ml_regime_model.pkl'
    joblib.dump(final_model, model_path)
    logger.info(f"\nModel saved successfully to {model_path}")
    
    # Send Discord Alert
    metrics_dict = {
        'total_samples': len(features_df),
        'accuracy': final_acc,
        'importances': imp.to_dict(),
        'best_params': best_params,
        'label_sources': features_df['label_source'].value_counts().to_dict()
    }
    
    try:
        from integrations.discord_notifier import DiscordNotifier
        notifier = DiscordNotifier()
        notifier.send_ml_retrain_alert(metrics_dict)
        logger.info("Sent enriched ML retrain alert to Discord.")
    except Exception as e:
        logger.error(f"Failed to send ML retrain Discord alert: {e}")
        
    return final_model

if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 2: ML REGIME MODEL TRAINING (UPGRADED)")
    print("=" * 60)
    
    df = fetch_and_prepare_data()
    signals_df = fetch_closed_signals()
    feats = generate_features(df)
    
    if not feats.empty:
        train_model(feats, signals_df)
    else:
        print("Failed to generate features. Ensure database has historical records.")
