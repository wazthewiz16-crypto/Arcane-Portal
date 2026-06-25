import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from detection.datastore import MangoDataStore
from detection.market_regime import MarketRegimeDetector

datastore = MangoDataStore()

def simulate():
    # We simulate NOW() as 2026-06-05 13:01:00 UTC (9:01 AM EST)
    sim_time = "2026-06-05T13:01:00"
    lookback_hours = 4
    
    with datastore.get_connection() as conn:
        rows = datastore._fetch_query(conn, """
            SELECT DISTINCT ON (name, timeframe)
                name, timeframe, timestamp, close, open, high, low,
                mango_d1, mango_d2, entry_up, entry_down,
                eq_band1, eq_band2, upper_vol_b, lower_vol_b
            FROM scrapes
            WHERE timestamp <= ?
              AND TO_TIMESTAMP(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS')
                  > TO_TIMESTAMP(?, 'YYYY-MM-DD"T"HH24:MI:SS') - INTERVAL '%s hours'
              AND timeframe IN ('15m', '1h', '4h')
            ORDER BY name, timeframe, timestamp DESC
        """, (sim_time, sim_time, lookback_hours))
        
    print(f"Total rows found at 13:01 UTC: {len(rows)}")
    
    # Let's manually run the feature computation
    detector = MarketRegimeDetector(datastore)
    
    # Modify detect_regime to use sim_time
    # Let's mock _compute_features to return features calculated at sim_time
    def mock_compute_features(lh):
        # Group by asset
        assets = {}
        for r in rows:
            name = r['name']
            if name not in assets:
                assets[name] = {}
            assets[name][r['timeframe']] = r

        # Feature 1: Zone Escape Ratio
        zone_total = 0
        zone_escaped = 0
        long_count = 0
        short_count = 0

        for name, tfs in assets.items():
            ltf = tfs.get('15m') or tfs.get('1h')
            if not ltf:
                continue

            close = ltf.get('close')
            eu = ltf.get('entry_up')
            ed = ltf.get('entry_down')

            if not (close and eu and ed and eu != ed):
                continue

            zone_total += 1
            zone_pct = (close - ed) / (eu - ed)

            if zone_pct > 1.10:
                zone_escaped += 1
                long_count += 1
            elif zone_pct < -0.10:
                zone_escaped += 1
                short_count += 1

        zone_escape_ratio = zone_escaped / zone_total if zone_total > 0 else 0

        # Feature 2: Directional Alignment
        aligned = 0
        dir_total = 0

        for name, tfs in assets.items():
            htf = tfs.get('4h') or tfs.get('1h')
            ltf = tfs.get('15m') or tfs.get('1h')
            if not (htf and ltf):
                continue

            htf_dir = detector._get_direction(htf)
            ltf_dir = detector._get_direction(ltf)

            if htf_dir and ltf_dir:
                dir_total += 1
                if htf_dir == ltf_dir:
                    aligned += 1

        direction_alignment = aligned / dir_total if dir_total > 0 else 0

        # Feature 3: Candle Range Expansion
        range_ratios = []
        for name, tfs in assets.items():
            ltf = tfs.get('15m') or tfs.get('1h')
            if not ltf:
                continue

            high = ltf.get('high', 0)
            low = ltf.get('low', 0)
            eu = ltf.get('entry_up', 0)
            ed = ltf.get('entry_down', 0)

            if high and low and eu and ed and (eu - ed) > 0:
                candle_range = high - low
                zone_width = eu - ed
                range_ratios.append(candle_range / zone_width)

        range_expansion = sum(range_ratios) / len(range_ratios) if range_ratios else 1.0

        # Feature 4: EQ Band Expansion
        eq_expanding = 0
        eq_total = 0

        for name, tfs in assets.items():
            ltf = tfs.get('15m') or tfs.get('1h')
            if not ltf:
                continue

            eq1 = ltf.get('eq_band1')
            eq2 = ltf.get('eq_band2')
            uv = ltf.get('upper_vol_b')
            lv = ltf.get('lower_vol_b')

            if eq1 is not None and eq2 is not None and uv is not None and lv is not None:
                eq_total += 1
                eq_spread = abs(eq1 - eq2)
                vol_spread = abs(uv - lv)
                if eq_spread >= vol_spread:
                    eq_expanding += 1

        eq_expansion_ratio = eq_expanding / eq_total if eq_total > 0 else 0.5

        if long_count > short_count * 2:
            trend_bias = 'BULLISH'
        elif short_count > long_count * 2:
            trend_bias = 'BEARISH'
        else:
            trend_bias = 'MIXED'

        return {
            'zone_escape_ratio': zone_escape_ratio,
            'direction_alignment': direction_alignment,
            'range_expansion': range_expansion,
            'eq_expansion_ratio': eq_expansion_ratio,
            'trend_bias': trend_bias,
        }

    detector._compute_features = mock_compute_features
    res = detector.detect_regime()
    print("\nRegime Detection Result at 13:01 UTC:")
    print(f"  Regime: {res['regime']}")
    print(f"  Confidence: {res['confidence']}")
    print(f"  Features: {res['features']}")
    print(f"  Details: {res['details']}")

if __name__ == "__main__":
    simulate()
