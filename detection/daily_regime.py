import logging
import json
import numpy as np
from datetime import datetime, timedelta, time
import pytz
from detection.market_regime import MarketRegimeDetector
from integrations.discord_notifier import DiscordNotifier

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

def execute_daily_regime_check(datastore, is_afternoon: bool = False):
    """
    Executes the daily market regime check:
    - Morning (6 AM EST): predicts if today is TRENDING or RANGING.
    - Afternoon (1 PM EST): verifies/corrects the morning prediction based on actual intraday price moves.
    """
    est = pytz.timezone('America/New_York')
    now_est = datetime.now(est)
    
    # Initialize regime detector
    regime_detector = MarketRegimeDetector(datastore)
    regime_result = regime_detector.detect_regime(lookback_hours=4)
    
    regime = regime_result.get('regime', 'RANGING')
    confidence = regime_result.get('confidence', 50.0)
    features = regime_result.get('features', {})
    
    notifier = DiscordNotifier()
    
    # ── Suggestion A: Volatility Squeeze (BBWP) check ──
    # Check if BTC volatility in cached Mango data is extremely compressed
    bbwp_squeeze = False
    btc_vol = 50.0
    try:
        cached_data_str = datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
        if cached_data_str:
            cached_data = json.loads(cached_data_str)
            btc_data = cached_data.get('assets', {}).get('BTC', {})
            btc_vol = float(btc_data.get('volatility', 50.0))
            if btc_vol < 25.0:
                bbwp_squeeze = True
    except Exception as e:
        logger.warning(f"Error parsing BBWP squeeze info: {e}")
        
    # ── Suggestion B: Drawdown Circuit Breaker Safeguard ──
    cb_active = False
    try:
        cb_val = datastore.get_setting("CIRCUIT_BREAKER_ACTIVE")
        if str(cb_val).lower() == 'true':
            cb_active = True
    except Exception as e:
        logger.warning(f"Error checking circuit breaker: {e}")
        
    if not is_afternoon:
        # MORNING CHECK (6:00 AM EST)
        # Determine Daily Regime Decision
        if cb_active:
            decision = 'RANGING_SCALPS_ONLY'  # Force safety during drawdown
            reason = "Drawdown Circuit Breaker is active! Forcing RANGING_SCALPS_ONLY to restrict swing trading risk."
        elif regime == 'TRENDING':
            decision = 'TRENDING'
            reason = f"Trending day predicted with {confidence:.0f}% confidence. All swing & scalp trade signals enabled."
        else: # RANGING
            if confidence >= 85.0:
                decision = 'RANGING_NO_TRADE'
                reason = f"Highly choppy ranging day predicted ({confidence:.0f}% confidence). Halting all trade signals today to protect capital."
            else:
                decision = 'RANGING_SCALPS_ONLY'
                reason = f"Moderate ranging day predicted ({confidence:.0f}% confidence). Swing trades disabled; sticking to quick scalps only."
                
        # Save settings
        datastore.set_setting("DAILY_REGIME_DECISION", decision)
        datastore.set_setting("DAILY_REGIME_MORNING_PRED", decision)
        
        # ── Suggestion C: Dynamic Altcoin Correlation Cap Adjustment ──
        if decision == 'RANGING_SCALPS_ONLY':
            datastore.set_setting("MAX_CRYPTO_SAME_DIRECTION", "1")
            logger.info("Ranging Scalps Only: Tightening crypto correlation cap to 1 position max.")
        elif decision == 'RANGING_NO_TRADE':
            # All signals blocked, cap is irrelevant
            pass
        else:
            # Trending: Restore standard correlation cap (2 max)
            datastore.set_setting("MAX_CRYPTO_SAME_DIRECTION", "2")

        # ── Calculate Overnight Price Moves (11 PM yesterday to 6 AM today) ──
        top_gainers = []
        top_losers = []
        try:
            # Target times in UTC
            target_prev_est = est.localize(datetime.combine(now_est.date() - timedelta(days=1), time(23, 0)))
            target_prev_utc = target_prev_est.astimezone(pytz.utc)

            target_curr_est = est.localize(datetime.combine(now_est.date(), time(6, 0)))
            target_curr_utc = target_curr_est.astimezone(pytz.utc)

            # Search windows (to handle timezone/scheduling variance)
            prev_start = target_prev_est - timedelta(hours=1.5)
            prev_end = target_prev_est + timedelta(hours=1.5)
            curr_start = target_curr_est - timedelta(hours=1.5)
            curr_end = target_curr_est + timedelta(hours=1.5)

            prev_start_iso = prev_start.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            prev_end_iso = prev_end.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            curr_start_iso = curr_start.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            curr_end_iso = curr_end.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            with datastore.get_connection() as conn:
                scrapes_rows = datastore._fetch_query(conn, """
                    SELECT name, close, timestamp
                    FROM scrapes
                    WHERE timeframe = '1h'
                      AND (
                        (timestamp >= ? AND timestamp <= ?)
                        OR
                        (timestamp >= ? AND timestamp <= ?)
                      )
                """, (prev_start_iso, prev_end_iso, curr_start_iso, curr_end_iso))

            prev_scrapes = {}
            curr_scrapes = {}
            for r in scrapes_rows:
                name = r['name']
                if name.upper() in ('BTCD', 'CRYPTOCAP:BTC.D'):
                    continue
                close = r['close']
                if close is None:
                    continue
                close = float(close)
                
                try:
                    ts_str = r['timestamp']
                    if ts_str.endswith('Z'):
                        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(ts_str)
                        if dt.tzinfo is None:
                            dt = pytz.utc.localize(dt)
                        else:
                            dt = dt.astimezone(pytz.utc)
                except Exception:
                    continue

                diff_prev = abs((dt - target_prev_utc).total_seconds())
                diff_curr = abs((dt - target_curr_utc).total_seconds())
                
                in_prev = prev_start.astimezone(pytz.utc) <= dt <= prev_end.astimezone(pytz.utc)
                in_curr = curr_start.astimezone(pytz.utc) <= dt <= curr_end.astimezone(pytz.utc)

                if in_prev:
                    if name not in prev_scrapes or diff_prev < prev_scrapes[name]['diff']:
                        prev_scrapes[name] = {'close': close, 'timestamp': ts_str, 'diff': diff_prev}
                if in_curr:
                    if name not in curr_scrapes or diff_curr < curr_scrapes[name]['diff']:
                        curr_scrapes[name] = {'close': close, 'timestamp': ts_str, 'diff': diff_curr}

            overnight_changes = []
            for name in prev_scrapes:
                if name in curr_scrapes:
                    p_close = prev_scrapes[name]['close']
                    c_close = curr_scrapes[name]['close']
                    if p_close > 0:
                        change = (c_close - p_close) / p_close
                        overnight_changes.append({
                            'name': name,
                            'prev_price': p_close,
                            'curr_price': c_close,
                            'change': change
                        })

            overnight_changes.sort(key=lambda x: x['change'], reverse=True)
            gainers = [x for x in overnight_changes if x['change'] > 0]
            losers = [x for x in overnight_changes if x['change'] < 0]
            losers.sort(key=lambda x: x['change'])  # Most negative first

            top_gainers = gainers[:3]
            top_losers = losers[:3]
        except Exception as e:
            logger.warning(f"Error calculating overnight moves: {e}")

        # ── Calculate Watchlist Bias Sentiment ──
        watchlist_bias = "N/A"
        try:
            cached_data_str = datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
            if cached_data_str:
                cached_data = json.loads(cached_data_str)
                assets = cached_data.get('assets', {})
                
                crypto_watchlist = {"BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR", "PAXG"}
                long_count = 0
                short_count = 0
                neutral_count = 0
                
                for sym, asset_data in assets.items():
                    if sym.upper() in crypto_watchlist:
                        trend = str(asset_data.get('trend', 'NEUTRAL')).upper()
                        if 'LONG' in trend or 'BULL' in trend:
                            long_count += 1
                        elif 'SHORT' in trend or 'BEAR' in trend:
                            short_count += 1
                        else:
                            neutral_count += 1
                
                if long_count > short_count:
                    bias_label = "Bullish Bias"
                elif short_count > long_count:
                    bias_label = "Bearish Bias"
                else:
                    bias_label = "Neutral Bias"
                    
                watchlist_bias = f"{long_count} LONG, {short_count} SHORT, {neutral_count} NEUTRAL ({bias_label})"
        except Exception as e:
            logger.warning(f"Error calculating watchlist sentiment bias: {e}")

        # ── Calculate BTC Dominance Cycle status ──
        btc_dom_status = "NEUTRAL (Data unavailable)"
        try:
            with datastore.get_connection() as conn:
                macro_rows = datastore._fetch_query(conn, """
                    SELECT name, timeframe, close, open, high, low,
                           mango_d1, mango_d2, entry_up, entry_down, trend
                    FROM scrapes
                    WHERE name IN ('BTC', 'BTCD', 'CRYPTOCAP:BTC.D')
                      AND timeframe IN ('4h', '1h')
                    ORDER BY timestamp DESC
                """)
            
            btc_scrapes = {}
            for r in macro_rows:
                name = 'BTCD' if r['name'] == 'CRYPTOCAP:BTC.D' else r['name']
                tf = r['timeframe']
                if name not in btc_scrapes:
                    btc_scrapes[name] = {}
                if tf not in btc_scrapes[name]:
                    btc_scrapes[name][tf] = r
                    
            def get_direction(htf_data):
                if not htf_data:
                    return 'NEUTRAL'
                scraped_trend = htf_data.get('trend')
                if scraped_trend:
                    if 'Bullish' in scraped_trend or 'LONG' in scraped_trend: return 'LONG'
                    if 'Bearish' in scraped_trend or 'SHORT' in scraped_trend: return 'SHORT'
                    if 'Neutral' in scraped_trend or 'NEUTRAL' in scraped_trend: return 'NEUTRAL'
                
                price = htf_data.get('close')
                d1 = htf_data.get('mango_d1')
                d2 = htf_data.get('mango_d2')
                if price is not None and d1 is not None and d2 is not None:
                    price = float(price)
                    d1 = float(d1)
                    d2 = float(d2)
                    ribbon_top = max(d1, d2)
                    ribbon_bottom = min(d1, d2)
                    if price > ribbon_top:
                        return 'LONG'
                    elif price < ribbon_bottom:
                        return 'SHORT'
                return 'NEUTRAL'

            btc_data = btc_scrapes.get('BTC', {}).get('4h') or btc_scrapes.get('BTC', {}).get('1h')
            btcd_data = btc_scrapes.get('BTCD', {}).get('4h') or btc_scrapes.get('BTCD', {}).get('1h')
            
            btc_dir = get_direction(btc_data)
            btcd_dir_raw = get_direction(btcd_data)
            btcd_dir = 'UP' if btcd_dir_raw == 'LONG' else ('DOWN' if btcd_dir_raw == 'SHORT' else 'NEUTRAL')
            
            if btcd_dir == 'UP' and btc_dir == 'LONG':
                btc_dom_status = "ALT_BEARISH (Money flowing into BTC, alts underperform BTC)"
            elif btcd_dir == 'UP' and btc_dir == 'SHORT':
                btc_dom_status = "ALT_DUMP (Widespread risk-off, dump likely)"
            elif btcd_dir == 'DOWN' and btc_dir == 'LONG':
                btc_dom_status = "ALT_SEASON (Capital rotating into alts, bullish alts)"
            elif btcd_dir == 'DOWN' and btc_dir == 'SHORT':
                btc_dom_status = "ALT_NEUTRAL (BTC falling with dominance, alts stable)"
            elif btcd_dir == 'DOWN' and btc_dir == 'NEUTRAL':
                btc_dom_status = "ALT_SLIGHTLY_BULLISH (Slight alt bias)"
            else:
                btc_dom_status = f"NEUTRAL (BTC={btc_dir}, BTC.D={btcd_dir})"
        except Exception as e:
            logger.warning(f"Error calculating BTC Dominance Cycle status: {e}")

        # Send Discord Alert
        results = {
            'date': now_est.strftime('%Y-%m-%d'),
            'time_of_day': 'Morning Check (6:00 AM EST)',
            'regime': regime,
            'confidence': confidence,
            'decision': decision,
            'reason': reason,
            'bbwp_squeeze': bbwp_squeeze,
            'btc_vol': btc_vol,
            'cb_active': cb_active,
            'metrics': features,
            'overnight_gainers': top_gainers,
            'overnight_losers': top_losers,
            'watchlist_bias': watchlist_bias,
            'btc_dom_status': btc_dom_status
        }
        notifier.send_daily_regime_alert(results)
        
    else:
        # AFTERNOON VERIFICATION (1:00 PM EST)
        morning_pred = datastore.get_setting("DAILY_REGIME_MORNING_PRED", "TRENDING")
        
        # Query scrapes since 5:00 AM EST today
        today_5am_est = est.localize(datetime.combine(now_est.date(), time(5, 0)))
        today_5am_utc = today_5am_est.astimezone(pytz.utc)
        cutoff_iso = today_5am_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        avg_daily_range = 0.0
        try:
            with datastore.get_connection() as conn:
                scrapes = datastore._fetch_query(conn, """
                    SELECT name, close, high, low, timestamp
                    FROM scrapes
                    WHERE timestamp >= ?
                      AND timeframe IN ('15m', '1h')
                """, (cutoff_iso,))
                
            if scrapes:
                # Group by asset name
                asset_groups = {}
                for s in scrapes:
                    name = s['name']
                    if name.upper() in ('BTCD', 'CRYPTOCAP:BTC.D'):
                        continue
                    if name not in asset_groups:
                        asset_groups[name] = {'highs': [], 'lows': [], 'closes': []}
                    if s.get('high') is not None: asset_groups[name]['highs'].append(float(s['high']))
                    if s.get('low') is not None: asset_groups[name]['lows'].append(float(s['low']))
                    if s.get('close') is not None: asset_groups[name]['closes'].append(float(s['close']))
                
                ranges = []
                for name, data in asset_groups.items():
                    if data['highs'] and data['lows'] and data['closes']:
                        max_h = max(data['highs'])
                        min_l = min(data['lows'])
                        if min_l > 0:
                            pct_range = (max_h - min_l) / min_l
                            ranges.append(pct_range)
                if ranges:
                    avg_daily_range = float(np.mean(ranges))
        except Exception as e:
            logger.warning(f"Error calculating intraday actual ranges: {e}")
            
        # Verification Logic
        if cb_active:
            decision = 'RANGING_SCALPS_ONLY'
            reason = "Afternoon check: Circuit Breaker is active. Maintaining standard safety limits (RANGING_SCALPS_ONLY)."
        elif avg_daily_range > 0.025 or regime == 'TRENDING':
            decision = 'TRENDING'
            if morning_pred == 'TRENDING':
                reason = f"Trending day confirmed (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Continuing swing/scalp trading."
            else:
                reason = f"Regime deviation! Market broke out to TRENDING (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Upgrading decision from {morning_pred} to TRENDING. Swing trading enabled."
        elif avg_daily_range < 0.012 or regime == 'RANGING':
            if morning_pred == 'TRENDING':
                if confidence >= 85.0:
                    decision = 'RANGING_NO_TRADE'
                    reason = f"Regime deviation! Market is flat/ranging (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Downgrading from TRENDING to RANGING_NO_TRADE. Halting new positions."
                else:
                    decision = 'RANGING_SCALPS_ONLY'
                    reason = f"Regime deviation! Market is flat/ranging (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Downgrading from TRENDING to RANGING_SCALPS_ONLY. Swing signals disabled."
            else:
                decision = morning_pred
                reason = f"Ranging day confirmed (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Continuing with {morning_pred} settings."
        else:
            # In between, keep morning prediction
            decision = morning_pred
            reason = f"Market range within expected limits (1 PM actual move: {avg_daily_range:.1%}, latest conf: {confidence:.0f}%). Maintaining {morning_pred} settings."
            
        # Save decision
        datastore.set_setting("DAILY_REGIME_DECISION", decision)
        
        # Adjust Correlation Cap if needed
        if decision == 'RANGING_SCALPS_ONLY':
            datastore.set_setting("MAX_CRYPTO_SAME_DIRECTION", "1")
        elif decision == 'TRENDING':
            datastore.set_setting("MAX_CRYPTO_SAME_DIRECTION", "2")
            
        # Send Discord Alert
        results = {
            'date': now_est.strftime('%Y-%m-%d'),
            'time_of_day': 'Afternoon Verification (1:00 PM EST)',
            'regime': regime,
            'confidence': confidence,
            'decision': decision,
            'reason': reason,
            'bbwp_squeeze': bbwp_squeeze,
            'btc_vol': btc_vol,
            'cb_active': cb_active,
            'avg_daily_range': avg_daily_range,
            'metrics': features
        }
        notifier.send_daily_regime_alert(results)
        
    return results
