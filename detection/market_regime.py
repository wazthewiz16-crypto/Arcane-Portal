"""
Market Regime Detector

Classifies the current market as TRENDING or RANGING using heuristic features
computed from recent scrape data. Used by the auto optimizer to adapt signal
filters in real time.

Features:
  1. Zone escape ratio - % of assets with price far above/below zone
  2. Directional alignment - % of assets where HTF and LTF agree on direction
  3. Candle range expansion - Are candles bigger than recent average?
  4. EQ band expansion - Are equilibrium bands expanding?
"""
import logging
from typing import Dict, Optional
from pathlib import Path
import joblib
from detection.datastore import MangoDataStore

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """Detect whether the market is TRENDING or RANGING."""

    # Thresholds for TRENDING classification
    ZONE_ESCAPE_THRESHOLD = 0.50      # ≥50% of assets must be >110% zone position
    DIRECTION_ALIGN_THRESHOLD = 0.60  # ≥60% of assets must have aligned TFs
    MIN_ASSETS_REQUIRED = 4           # Need at least 4 assets with data

    def __init__(self, datastore: MangoDataStore):
        self.datastore = datastore
        self.model = None
        
        # Load ML model if it exists (Phase 2)
        model_path = Path(__file__).parent / 'ml_regime_model.pkl'
        if model_path.exists():
            try:
                self.model = joblib.load(model_path)
                logger.info(f"Loaded ML Regime model from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load ML Regime model: {e}")

    def detect_regime(self, lookback_hours: int = 4) -> Dict:
        """
        Analyze recent scrape data to classify market regime.

        Returns:
            {
                'regime': 'TRENDING' | 'RANGING',
                'confidence': float (0-100),
                'features': {
                    'zone_escape_ratio': float,
                    'direction_alignment': float,
                    'range_expansion': float,
                    'eq_expansion_ratio': float,
                },
                'trending_direction': 'BULLISH' | 'BEARISH' | 'MIXED' | None,
                'details': str
            }
        """
        try:
            features = self._compute_features(lookback_hours)
            if not features:
                return {
                    'regime': 'RANGING',
                    'confidence': 0,
                    'features': {},
                    'trending_direction': None,
                    'details': 'Insufficient data for regime detection'
                }

            # Classification logic
            regime, confidence, direction = self._classify(features)

            details = (
                f"Zone escape: {features['zone_escape_ratio']:.0%}, "
                f"Direction align: {features['direction_alignment']:.0%}, "
                f"Range expansion: {features['range_expansion']:.1f}x, "
                f"EQ expanding: {features['eq_expansion_ratio']:.0%}"
            )

            return {
                'regime': regime,
                'confidence': confidence,
                'features': features,
                'trending_direction': direction,
                'details': details
            }

        except Exception as e:
            logger.error(f"Regime detection failed: {e}")
            return {
                'regime': 'RANGING',
                'confidence': 0,
                'features': {},
                'trending_direction': None,
                'details': f'Error: {e}'
            }

    def _compute_features(self, lookback_hours: int) -> Optional[Dict]:
        """
        Compute regime features from recent scrape data.
        Uses the LATEST scrape per asset per timeframe within the lookback window.
        """
        with self.datastore.get_connection() as conn:
            # Get latest scrapes for each asset (LTF: 15m, 1h)
            rows = self.datastore._fetch_query(conn, """
                SELECT DISTINCT ON (name, timeframe)
                    name, timeframe, close, open, high, low,
                    mango_d1, mango_d2, entry_up, entry_down,
                    eq_band1, eq_band2, upper_vol_b, lower_vol_b
                FROM scrapes
                WHERE TO_TIMESTAMP(timestamp, 'YYYY-MM-DD"T"HH24:MI:SS')
                      > NOW() - INTERVAL '%s hours'
                  AND timeframe IN ('15m', '1h', '4h')
                ORDER BY name, timeframe, timestamp DESC
            """ % lookback_hours)

        if not rows or len(rows) < self.MIN_ASSETS_REQUIRED:
            return None

        # Group by asset
        assets = {}
        for r in rows:
            name = r['name']
            if name not in assets:
                assets[name] = {}
            assets[name][r['timeframe']] = r

        if len(assets) < self.MIN_ASSETS_REQUIRED:
            return None

        # --- Feature 1: Zone Escape Ratio ---
        # How many assets have price significantly above/below their entry zone?
        zone_escaped = 0
        zone_total = 0
        long_count = 0
        short_count = 0

        for name, tfs in assets.items():
            # Prefer 15m, fall back to 1h
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

            if zone_pct > 1.10:  # >110% — price above zone
                zone_escaped += 1
                long_count += 1
            elif zone_pct < -0.10:  # <-10% — price below zone
                zone_escaped += 1
                short_count += 1

        zone_escape_ratio = zone_escaped / zone_total if zone_total > 0 else 0

        # --- Feature 2: Directional Alignment ---
        # Do HTF and LTF agree on direction for each asset?
        aligned = 0
        dir_total = 0

        for name, tfs in assets.items():
            htf = tfs.get('4h') or tfs.get('1h')
            ltf = tfs.get('15m') or tfs.get('1h')
            if not (htf and ltf):
                continue

            htf_dir = self._get_direction(htf)
            ltf_dir = self._get_direction(ltf)

            if htf_dir and ltf_dir:
                dir_total += 1
                if htf_dir == ltf_dir:
                    aligned += 1

        direction_alignment = aligned / dir_total if dir_total > 0 else 0

        # --- Feature 3: Candle Range Expansion ---
        # Compare current candle ranges to zone width (normalized)
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

        # --- Feature 4: EQ Band Expansion ---
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

        # Determine trending direction
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
            'assets_analyzed': zone_total,
            'long_escaped': long_count,
            'short_escaped': short_count,
        }

    def _classify(self, features: Dict) -> tuple:
        """
        Classify regime from features.
        Returns (regime, confidence, direction).
        """
        score = 0.0

        # Zone escape is the strongest signal
        zer = features['zone_escape_ratio']
        if zer >= 0.60:
            score += 40
        elif zer >= 0.40:
            score += 25
        elif zer >= 0.25:
            score += 10

        # Directional alignment
        da = features['direction_alignment']
        if da >= 0.80:
            score += 25
        elif da >= 0.60:
            score += 15
        elif da >= 0.40:
            score += 5

        # Range expansion (candles bigger than zones = trending)
        re = features['range_expansion']
        if re >= 2.0:
            score += 20
        elif re >= 1.5:
            score += 12
        elif re >= 1.0:
            score += 5

        # EQ expansion (volatility expanding = trending)
        eq = features['eq_expansion_ratio']
        if eq >= 0.60:
            score += 15
        elif eq >= 0.40:
            score += 8

        # If we have an ML model, use it to classify!
        if self.model is not None:
            import pandas as pd
            X = pd.DataFrame([{
                'zone_escape_ratio': features['zone_escape_ratio'],
                'direction_alignment': features['direction_alignment'],
                'range_expansion': features['range_expansion'],
                'eq_expansion_ratio': features['eq_expansion_ratio']
            }])
            
            try:
                pred = self.model.predict(X)[0]
                prob = max(self.model.predict_proba(X)[0]) * 100
                
                regime = 'TRENDING' if pred == 1 else 'RANGING'
                
                # We overwrite the heuristic score with ML probability
                score = prob
            except Exception as e:
                logger.error(f"ML prediction failed, falling back to heuristics: {e}")
                regime = 'TRENDING' if score >= 55 else 'RANGING'
        else:
            # Classification thresholds (Phase 1 Heuristics)
            if score >= 55:
                regime = 'TRENDING'
            else:
                regime = 'RANGING'

        direction = features.get('trend_bias')

        return regime, min(score, 100), direction

    def _get_direction(self, data: Dict) -> Optional[str]:
        """Get direction from price vs ribbon."""
        close = data.get('close')
        d1 = data.get('mango_d1')
        d2 = data.get('mango_d2')

        if not (close and d1 and d2):
            return None

        ribbon_top = max(d1, d2)
        ribbon_bot = min(d1, d2)

        if close > ribbon_top:
            return 'LONG'
        elif close < ribbon_bot:
            return 'SHORT'
        return 'NEUTRAL'
