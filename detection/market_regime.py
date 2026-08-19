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
import pandas as pd
from datetime import datetime, timedelta
from detection.datastore import MangoDataStore

logger = logging.getLogger(__name__)

DEFAULT_MANGO_FEATURES = {
    'mango_market_trend': 0,
    'mango_market_volatility': 50.0,
    'mango_badge_trend_ratio': 0.5,
    'mango_avg_asset_volatility': 50.0
}

def extract_mango_features(mango_row):
    import json
    
    market_trend_str = str(mango_row.get('market_trend', 'NEUTRAL')).upper()
    if 'LONG' in market_trend_str or 'BULL' in market_trend_str:
        mango_market_trend = 1
    elif 'SHORT' in market_trend_str or 'BEAR' in market_trend_str:
        mango_market_trend = -1
    else:
        mango_market_trend = 0
        
    try:
        mango_market_volatility = float(mango_row.get('market_volatility', 50.0))
    except (ValueError, TypeError):
        mango_market_volatility = 50.0
        
    assets_json = mango_row.get('assets_json')
    assets = {}
    if assets_json:
        try:
            assets = json.loads(assets_json)
        except Exception:
            pass
            
    if assets:
        active_count = sum(1 for asset in assets.values() if asset.get('trend') in ('LONG', 'SHORT'))
        total_count = len(assets)
        mango_badge_trend_ratio = active_count / total_count if total_count > 0 else 0.5
        
        vols = [asset.get('volatility', 50.0) for asset in assets.values() if asset.get('volatility') is not None]
        mango_avg_asset_volatility = sum(vols) / len(vols) if vols else 50.0
    else:
        mango_badge_trend_ratio = 0.5
        mango_avg_asset_volatility = 50.0
        
    return {
        'mango_market_trend': mango_market_trend,
        'mango_market_volatility': mango_market_volatility,
        'mango_badge_trend_ratio': mango_badge_trend_ratio,
        'mango_avg_asset_volatility': mango_avg_asset_volatility
    }


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
                f"EQ expanding: {features['eq_expansion_ratio']:.0%}, "
                f"Mango Trend: {features['mango_market_trend']}, "
                f"Mango Vol: {features['mango_market_volatility']:.0f}"
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

    def check_realtime_market_velocity(self) -> Dict:
        """
        Check real-time 4-hour market momentum to detect short squeezes / market flushes.
        If watchlist pumps >= +2.5% in 4 hours OR BTC pumps >= +3.0%, declares BULLISH_BREAKOUT_SQUEEZE.
        If watchlist dumps <= -2.5% in 4 hours OR BTC dumps <= -3.0%, declares BEARISH_FLUSH.
        """
        from datetime import datetime, timedelta, timezone
        
        try:
            with self.datastore.get_connection() as conn:
                # Query 4h price moves across all active assets
                scrapes = self.datastore._fetch_query(conn, """
                    SELECT name, close, timestamp FROM scrapes
                    WHERE timeframe = '4h'
                    ORDER BY timestamp DESC
                    LIMIT 40
                """)
                
            if not scrapes:
                return {'state': 'NORMAL', 'short_blocked': False, 'long_blocked': False}
                
            # Group latest and prior 4h close prices per asset
            asset_prices = {}
            for row in scrapes:
                name = row['name']
                if name not in asset_prices:
                    asset_prices[name] = []
                asset_prices[name].append(row['close'])
                
            returns = []
            btc_return = 0.0
            
            for name, prices in asset_prices.items():
                if len(prices) >= 2 and prices[1] > 0:
                    ret = (prices[0] - prices[1]) / prices[1] * 100.0
                    returns.append(ret)
                    if name.upper() == 'BTC':
                        btc_return = ret
                        
            if not returns:
                return {'state': 'NORMAL', 'short_blocked': False, 'long_blocked': False}
                
            avg_return = sum(returns) / len(returns)
            prev_state = str(self.datastore.get_setting("MARKET_STATE", "NORMAL")).upper()
            
            # Squeeze / Flush Thresholds
            if avg_return >= 2.5 or btc_return >= 3.0:
                self.datastore.set_setting("SHORT_SIGNALS_BLOCKED", "True")
                self.datastore.set_setting("LONG_SIGNALS_BLOCKED", "False")
                self.datastore.set_setting("MARKET_STATE", "BULLISH_BREAKOUT_SQUEEZE")
                logger.info(f"🚀 Real-Time Short Squeeze Detected! Avg Watchlist Move: +{avg_return:.2f}%, BTC: +{btc_return:.2f}%. Short signals BLOCKED.")
                
                # Perform immediate purge/status update of active short signals
                closed_count = 0
                with self.datastore.get_connection() as conn:
                    active_shorts = self.datastore._fetch_query(conn, "SELECT id, name FROM signals WHERE signal_type LIKE '%SHORT%' AND status = 'ACTIVE'")
                    closed_count = len(active_shorts) if active_shorts else 0
                    if closed_count > 0:
                        self.datastore._execute_query(conn, """
                            UPDATE signals SET status = 'SQUEEZE_EXIT', updated_at = ?
                            WHERE signal_type LIKE '%SHORT%' AND status = 'ACTIVE'
                        """, (datetime.now(timezone.utc).isoformat(),))
                        
                # Send Urgent Discord Alert on state transition or closed positions
                if prev_state != "BULLISH_BREAKOUT_SQUEEZE" or closed_count > 0:
                    try:
                        from integrations.discord_notifier import DiscordNotifier
                        notifier = DiscordNotifier()
                        msg = (
                            "🚨 **URGENT ALERT: SHORT SQUEEZE EXIT TRIGGERED** 🚨\n\n"
                            f"⚡ **Market Move:** Watchlist Average `+{avg_return:.2f}%` | BTC `+{btc_return:.2f}%` (4H)\n"
                            f"🛡️ **Action Taken:** `{closed_count}` active SHORT position(s) closed immediately as `SQUEEZE_EXIT` to protect capital.\n"
                            "🚫 **Short Signals:** BLOCKED across all timeframes.\n"
                            "🚀 **Breakout Mode:** Active for Momentum LONGs.\n\n"
                            "⚠️ *If you have manual short positions open, consider exiting or adjusting stops immediately!*"
                        )
                        notifier.send_message(msg)
                    except Exception as ne:
                        logger.error(f"Failed to send Discord Squeeze Exit alert: {ne}")
                    
                return {'state': 'BULLISH_BREAKOUT_SQUEEZE', 'short_blocked': True, 'long_blocked': False}
                
            elif avg_return <= -2.5 or btc_return <= -3.0:
                self.datastore.set_setting("SHORT_SIGNALS_BLOCKED", "False")
                self.datastore.set_setting("LONG_SIGNALS_BLOCKED", "True")
                self.datastore.set_setting("MARKET_STATE", "BEARISH_FLUSH")
                logger.info(f"📉 Real-Time Bearish Flush Detected! Avg Watchlist Move: {avg_return:.2f}%, BTC: {btc_return:.2f}%. Long signals BLOCKED.")
                
                closed_count = 0
                with self.datastore.get_connection() as conn:
                    active_longs = self.datastore._fetch_query(conn, "SELECT id, name FROM signals WHERE signal_type LIKE '%LONG%' AND status = 'ACTIVE'")
                    closed_count = len(active_longs) if active_longs else 0
                    if closed_count > 0:
                        self.datastore._execute_query(conn, """
                            UPDATE signals SET status = 'FLUSH_EXIT', updated_at = ?
                            WHERE signal_type LIKE '%LONG%' AND status = 'ACTIVE'
                        """, (datetime.now(timezone.utc).isoformat(),))

                if prev_state != "BEARISH_FLUSH" or closed_count > 0:
                    try:
                        from integrations.discord_notifier import DiscordNotifier
                        notifier = DiscordNotifier()
                        msg = (
                            "🚨 **URGENT ALERT: BEARISH FLUSH EXIT TRIGGERED** 🚨\n\n"
                            f"⚡ **Market Move:** Watchlist Average `{avg_return:.2f}%` | BTC `{btc_return:.2f}%` (4H)\n"
                            f"🛡️ **Action Taken:** `{closed_count}` active LONG position(s) closed immediately as `FLUSH_EXIT` to protect capital.\n"
                            "🚫 **Long Signals:** BLOCKED across all timeframes.\n\n"
                            "⚠️ *If you have manual long positions open, consider exiting or adjusting stops immediately!*"
                        )
                        notifier.send_message(msg)
                    except Exception as ne:
                        logger.error(f"Failed to send Discord Flush Exit alert: {ne}")
                    
                return {'state': 'BEARISH_FLUSH', 'short_blocked': False, 'long_blocked': True}
                
            else:
                self.datastore.set_setting("SHORT_SIGNALS_BLOCKED", "False")
                self.datastore.set_setting("LONG_SIGNALS_BLOCKED", "False")
                self.datastore.set_setting("MARKET_STATE", "NORMAL")
                return {'state': 'NORMAL', 'short_blocked': False, 'long_blocked': False}
                
        except Exception as e:
            logger.error(f"Error checking real-time market velocity: {e}")
            return {'state': 'NORMAL', 'short_blocked': False, 'long_blocked': False}

    def _compute_features(self, lookback_hours: int) -> Optional[Dict]:
        """
        Compute regime features from recent scrape data.
        Uses the LATEST scrape per asset per timeframe within the lookback window.
        """
        from detection.datastore import USE_POSTGRES
        with self.datastore.get_connection() as conn:
            # Get latest scrapes for each asset (LTF: 15m, 1h)
            if USE_POSTGRES:
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
            else:
                cutoff_utc = datetime.utcnow() - timedelta(hours=lookback_hours)
                cutoff_iso = cutoff_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                rows = self.datastore._fetch_query(conn, """
                    SELECT name, timeframe, close, open, high, low,
                           mango_d1, mango_d2, entry_up, entry_down,
                           eq_band1, eq_band2, upper_vol_b, lower_vol_b
                    FROM scrapes s1
                    WHERE timestamp >= ?
                      AND timeframe IN ('15m', '1h', '4h')
                      AND timestamp = (
                          SELECT MAX(timestamp) FROM scrapes s2
                          WHERE s2.name = s1.name
                            AND s2.timeframe = s1.timeframe
                            AND s2.timestamp >= ?
                      )
                """, (cutoff_iso, cutoff_iso))

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

        # Fetch latest mango scrape
        with self.datastore.get_connection() as conn:
            try:
                mango_rows = self.datastore._fetch_query(conn, """
                    SELECT timestamp, market_trend, market_volatility, assets_json
                    FROM mango_scrapes
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
            except Exception as e:
                logger.warning(f"Failed to query latest mango_scrapes: {e}")
                mango_rows = []

        mango_feats = DEFAULT_MANGO_FEATURES.copy()
        if mango_rows:
            latest_row = mango_rows[0]
            try:
                ts_str = latest_row['timestamp']
                ts = pd.to_datetime(ts_str, utc=True).tz_localize(None)
                now_naive = datetime.utcnow()
                if (now_naive - ts) <= timedelta(hours=24):
                    mango_feats = extract_mango_features(latest_row)
            except Exception as e:
                logger.warning(f"Error parsing latest mango scrape timestamp: {e}")

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
            'mango_market_trend': mango_feats['mango_market_trend'],
            'mango_market_volatility': mango_feats['mango_market_volatility'],
            'mango_badge_trend_ratio': mango_feats['mango_badge_trend_ratio'],
            'mango_avg_asset_volatility': mango_feats['mango_avg_asset_volatility']
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
            if hasattr(self.model, 'n_features_in_') and self.model.n_features_in_ == 4:
                X = pd.DataFrame([{
                    'zone_escape_ratio': features['zone_escape_ratio'],
                    'direction_alignment': features['direction_alignment'],
                    'range_expansion': features['range_expansion'],
                    'eq_expansion_ratio': features['eq_expansion_ratio']
                }])
            else:
                X = pd.DataFrame([{
                    'zone_escape_ratio': features['zone_escape_ratio'],
                    'direction_alignment': features['direction_alignment'],
                    'range_expansion': features['range_expansion'],
                    'eq_expansion_ratio': features['eq_expansion_ratio'],
                    'mango_market_trend': features['mango_market_trend'],
                    'mango_market_volatility': features['mango_market_volatility'],
                    'mango_badge_trend_ratio': features['mango_badge_trend_ratio'],
                    'mango_avg_asset_volatility': features['mango_avg_asset_volatility']
                }])
            
            try:
                pred = self.model.predict(X)[0]
                prob = max(self.model.predict_proba(X)[0]) * 100
                
                # If ML model confidence is low (< 60%), fall back to robust heuristics
                if prob < 60.0:
                    logger.info(f"ML regime prediction has low confidence ({prob:.1f}%). Falling back to heuristics (score={score}).")
                    if score >= 55:
                        regime = 'TRENDING'
                    else:
                        regime = 'RANGING'
                else:
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
