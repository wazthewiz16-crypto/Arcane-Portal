"""
Automated Signal Optimizer (Upgraded Phase 2)

Runs analysis on recent signals and automatically adjusts confidence thresholds
based on performance metrics (Win Rate, Frequency) — SEPARATELY for scalps and swings.
Now features the Drawdown Circuit Breaker, Dynamic Altcoin Correlation Cap (BTC BBWP matching),
and a Self-Healing Parameter Backtesting engine.
"""
import sys
import os
import io

# Force UTF-8 encoding for standard output and error to avoid UnicodeEncodeErrors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))

# Load Env
from dotenv import load_dotenv
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.market_regime import MarketRegimeDetector
from analyze_signals import SignalAnalyzer
from config import settings

# Setup Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoOptimizer")

# ─── Hard caps ───────────────────────────────────────────────────────────────
MAX_SWING = 85   # Confidence formula rarely exceeds 92, this is a safe ceiling
MAX_SCALP = 88
MIN_SWING = 55   # Never go below these — too noisy below here
MIN_SCALP = 60
# ─────────────────────────────────────────────────────────────────────────────


class AutoOptimizer:
    def __init__(self):
        self.datastore = MangoDataStore()
        self.analyzer = SignalAnalyzer()
        self.regime_detector = MarketRegimeDetector(self.datastore)

    # ─── Public entry point ───────────────────────────────────────────────────
    def run_optimization(self, hours=24):
        """Run analysis and apply updates"""
        logger.info(f"Running optimization for last {hours} hours...")

        # 1. Fetch signals
        analysis = self.analyzer.analyze_recent_signals(hours)
        has_analysis_error = 'error' in analysis
        
        if has_analysis_error:
            logger.warning(f"Analysis failed/No recent signals in last {hours} hours: {analysis['error']}")
            self._apply_frequency_safety_valve(hours)
            
            # Setup defaults for no recent signals
            metrics = {
                'win_rate_pct': 0.0,
                'winners': 0,
                'losers': 0,
                'total_signals': 0,
                'signals_per_hour': 0.0
            }
            breakdowns = {}
            total_closed = 0
        else:
            metrics    = analysis['metrics']
            breakdowns = analysis['breakdowns']
            total_closed = metrics['winners'] + metrics['losers']

            # Expand to 48 h if sample is thin
            if total_closed < 5 and hours < 48:
                logger.info(f"Only {total_closed} closed trades in {hours}h — expanding to 48h...")
                analysis_48 = self.analyzer.analyze_recent_signals(48)
                if 'error' not in analysis_48:
                    m48 = analysis_48['metrics']
                    tc48 = m48['winners'] + m48['losers']
                    if tc48 >= 5:
                        logger.info(f"Using 48h data: {tc48} closed trades.")
                        analysis      = analysis_48
                        metrics       = m48
                        breakdowns    = analysis['breakdowns']
                        total_closed  = tc48
                        hours         = 48

        logger.info(
            f"Metrics ({hours}h): WR={metrics['win_rate_pct']}%, "
            f"Signals={metrics['total_signals']}, Freq={metrics['signals_per_hour']}/hr"
        )

        # 2. Current thresholds (live DB values, fall back to settings defaults)
        current_swing = float(self.datastore.get_setting("MIN_CONFIDENCE_SWING", settings.MIN_CONFIDENCE_SWING))
        current_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP))
        logger.info(f"Current Thresholds → Swing: {current_swing}, Scalp: {current_scalp}")

        updates = {}

        # 2b. Run Self-Healing Backtest to optimize thresholds (Upgrade 4)
        opt_swing, opt_scalp = self._run_self_healing_backtest(lookback_days=14)

        # 3. Per-type win rate analysis (Dynamic Self-Healing vs Heuristics)
        by_type = breakdowns.get('by_signal_type', {})
        swing_stats = self._merge_type_stats(by_type, 'SWING')
        scalp_stats = self._merge_type_stats(by_type, 'SCALP')

        proposed_swing = current_swing
        proposed_scalp = current_scalp

        if opt_swing is not None:
            logger.info(f"Self-Healing: using optimized Swing threshold {opt_swing} (R-maximized)")
            proposed_swing = float(opt_swing)
        else:
            swing_update = self._decide_threshold(
                label='SWING', current=current_swing,
                stats=swing_stats,
                min_th=MIN_SWING, max_th=MAX_SWING
            )
            if swing_update is not None:
                proposed_swing = swing_update

        if opt_scalp is not None:
            logger.info(f"Self-Healing: using optimized Scalp threshold {opt_scalp} (R-maximized)")
            proposed_scalp = float(opt_scalp)
        else:
            scalp_update = self._decide_threshold(
                label='SCALP', current=current_scalp,
                stats=scalp_stats,
                min_th=MIN_SCALP, max_th=MAX_SCALP
            )
            if scalp_update is not None:
                proposed_scalp = scalp_update
            
        # 3b. Advanced Optimization: Asset Blacklisting
        if not has_analysis_error:
            toxic_assets = []
            for asset, a_stats in breakdowns.get('by_asset', {}).items():
                if a_stats['wins'] == 0 and a_stats['losses'] >= 3:
                    toxic_assets.append(asset.upper())
            if toxic_assets:
                logger.info(f"Blacklisting toxic assets: {toxic_assets}")
                updates['ASSET_BLACKLIST'] = ",".join(toxic_assets)
            else:
                updates['ASSET_BLACKLIST'] = "" # Clear blacklist if no longer toxic

        # 3c. Advanced Optimization: Max Confidence Cap ("Too Perfect" filter)
        if not has_analysis_error:
            hi_conf_wins = 0
            hi_conf_losses = 0
            for bucket, c_stats in breakdowns.get('by_confidence', {}).items():
                if bucket >= 85: # Look at extreme setups
                    hi_conf_wins += c_stats['wins']
                    hi_conf_losses += c_stats['losses']
            
            hi_conf_total = hi_conf_wins + hi_conf_losses
            hi_conf_wr = (hi_conf_wins / hi_conf_total * 100) if hi_conf_total > 0 else 0
            
            if hi_conf_total >= 5 and hi_conf_wr <= 25:
                logger.info(f"High-confidence setups are bleeding (WR: {hi_conf_wr:.0f}%). Capping Max Confidence to 88.")
                updates['MAX_CONFIDENCE_SWING'] = 88
                updates['MAX_CONFIDENCE_SCALP'] = 88
            else:
                updates['MAX_CONFIDENCE_SWING'] = 100
                updates['MAX_CONFIDENCE_SCALP'] = 100

        # 3d. Advanced Optimization: Dynamic Stop Loss Buffers (Chop Protection)
        if not has_analysis_error:
            if metrics['losers'] >= 5 and metrics['win_rate_pct'] < 30:
                logger.info(f"Systemic bleed detected (WR: {metrics['win_rate_pct']}%). Widening SL buffers for chop protection.")
                updates['SL_BUFFER_PCT_SWING'] = 0.025
                updates['SL_BUFFER_PCT_SCALP'] = 0.016
            elif metrics['win_rate_pct'] > 45:
                updates['SL_BUFFER_PCT_SWING'] = 0.015
                updates['SL_BUFFER_PCT_SCALP'] = 0.012

        # 3e. Market Regime Detection (TRENDING vs RANGING)
        regime_result = self.regime_detector.detect_regime(lookback_hours=4)
        regime = regime_result['regime']
        regime_conf = regime_result['confidence']
        regime_dir = regime_result.get('trending_direction', 'MIXED')
        logger.info(f"Market Regime: {regime} (confidence={regime_conf:.0f}, direction={regime_dir})")
        logger.info(f"  Details: {regime_result['details']}")

        updates['MARKET_REGIME'] = regime

        if regime == 'TRENDING':
            updates['BREAKOUT_CAPTURE_PCT'] = 0.01  # 1% beyond zone (was 0.3%)
            proposed_swing = max(MIN_SWING, proposed_swing - 3)
            proposed_scalp = max(MIN_SCALP, proposed_scalp - 3)
            logger.info(f"TRENDING regime: widened breakout capture to 1%, lowered proposed thresholds: Swing={proposed_swing}, Scalp={proposed_scalp}")
        else:
            updates['BREAKOUT_CAPTURE_PCT'] = 0.003  # Default 0.3%

        # 3f. Drawdown Circuit Breaker (Upgrade 2)
        # Calculate 24h PnL in R-multiples
        cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        with self.datastore.get_connection() as conn:
            closed_24h = self.datastore._fetch_query(conn, """
                SELECT * FROM signals
                WHERE status IN ('TP_HIT', 'SL_HIT')
                AND updated_at >= ?
            """, (cutoff_24h,))

        total_r = 0.0
        for sig in closed_24h:
            rr = sig.get('rr_ratio') or 0.0
            if sig['status'] == 'TP_HIT':
                total_r += float(rr)
            elif sig['status'] == 'SL_HIT':
                total_r -= 1.0

        if total_r <= -3.0:
            logger.warning(f"🚨 Drawdown detected ({total_r:.2f}R <= -3.0R)! Activating Drawdown Circuit Breaker.")
            self.datastore.set_setting("CIRCUIT_BREAKER_ACTIVE", "True")
            self.datastore.set_setting("CIRCUIT_BREAKER_EXPIRE_TIME", (datetime.utcnow() + timedelta(hours=24)).isoformat())
            updates['CIRCUIT_BREAKER_ACTIVE'] = "True"
        else:
            # Auto-reset if expired
            cb_active = self.datastore.get_setting("CIRCUIT_BREAKER_ACTIVE")
            if str(cb_active).lower() == 'true':
                expire_str = self.datastore.get_setting("CIRCUIT_BREAKER_EXPIRE_TIME")
                if expire_str:
                    try:
                        expire = datetime.fromisoformat(expire_str)
                        if datetime.utcnow() >= expire:
                            logger.info("Circuit breaker has expired. Deactivating.")
                            self.datastore.set_setting("CIRCUIT_BREAKER_ACTIVE", "False")
                            updates['CIRCUIT_BREAKER_ACTIVE'] = "False"
                    except:
                        pass

        # 3g. Dynamic Altcoin Correlation Cap (Upgrade 3)
        # Parse BTC volatility from the Mango Dashboard Cached data setting
        btc_vol = 50
        try:
            raw_cache = self.datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
            if raw_cache:
                cache_data = json.loads(raw_cache)
                assets = cache_data.get("assets", {})
                btc_data = assets.get("BTC") or assets.get("BTCUSDT")
                if btc_data:
                    btc_vol = int(btc_data.get("volatility", 50))
                    logger.info(f"BTC Volatility parsed: {btc_vol}")
        except Exception as e:
            logger.warning(f"Could not parse BTC Volatility from cache: {e}")

        if btc_vol < 30:
            dynamic_cap = 3  # Alt season expansion
        elif btc_vol >= 80:
            dynamic_cap = 1  # Correlation tightening
        else:
            dynamic_cap = 2  # Standard cap
            
        # Auto-loosen correlation cap if signal frequency is critically low (< 0.3/hr)
        # to prevent starving the system when signal volume is dried up
        freq = metrics['signals_per_hour']
        if freq < 0.3:
            logger.info(f"Signal frequency is low ({freq:.2f}/hr). Loosening correlation cap (+1).")
            dynamic_cap = min(3, dynamic_cap + 1)
            
        logger.info(f"Setting dynamic correlated cap to {dynamic_cap} (BTC Vol: {btc_vol})")
        updates['MAX_CRYPTO_SAME_DIRECTION'] = dynamic_cap

        # Low signal frequency cap: prevent threshold increases if freq < 0.3
        if freq < 0.3:
            if proposed_swing > current_swing:
                logger.info(f"Signal frequency is low ({freq:.2f}/hr). Blocking threshold increase: Swing {proposed_swing} -> {current_swing}")
                proposed_swing = current_swing
            if proposed_scalp > current_scalp:
                logger.info(f"Signal frequency is low ({freq:.2f}/hr). Blocking threshold increase: Scalp {proposed_scalp} -> {current_scalp}")
                proposed_scalp = current_scalp

        # 4. Global frequency safety valve
        last_valve_str = self.datastore.get_setting("LAST_FREQUENCY_VALVE_TIME")
        should_run_valve = True
        if last_valve_str:
            try:
                last_valve = datetime.fromisoformat(last_valve_str)
                elapsed = (datetime.utcnow() - last_valve).total_seconds() / 3600.0
                if elapsed < 12.0:
                    should_run_valve = False
                    logger.info(f"Frequency safety valve throttled. Only {elapsed:.2f}h since last run.")
            except Exception as e:
                logger.warning(f"Error parsing LAST_FREQUENCY_VALVE_TIME: {e}")
        
        if should_run_valve:
            if freq > 4.0:
                logger.info(f"Frequency too high ({freq}/hr). Raising proposed thresholds via safety valve.")
                proposed_swing = min(MAX_SWING, proposed_swing + 2)
                proposed_scalp = min(MAX_SCALP, proposed_scalp + 2)
                self.datastore.set_setting("LAST_FREQUENCY_VALVE_TIME", datetime.utcnow().isoformat())
            elif freq < 0.3:
                step_down_swing = max(MIN_SWING, current_swing - 3)
                step_down_scalp = max(MIN_SCALP, current_scalp - 3)
                
                # Force proposed thresholds to be at least as low as the safety valve step-down
                proposed_swing = min(proposed_swing, step_down_swing)
                proposed_scalp = min(proposed_scalp, step_down_scalp)
                
                logger.info(f"Frequency critically low ({freq}/hr). Lowering thresholds via safety valve: Swing={proposed_swing}, Scalp={proposed_scalp}")
                self.datastore.set_setting("LAST_FREQUENCY_VALVE_TIME", datetime.utcnow().isoformat())

        updates['MIN_CONFIDENCE_SWING'] = proposed_swing
        updates['MIN_CONFIDENCE_SCALP'] = proposed_scalp

        # 5. Apply and detect changes
        changed_keys = []
        critical_settings = [
            'MIN_CONFIDENCE_SWING', 'MIN_CONFIDENCE_SCALP', 'MARKET_REGIME',
            'CIRCUIT_BREAKER_ACTIVE', 'MAX_CRYPTO_SAME_DIRECTION', 'ASSET_BLACKLIST',
            'MAX_CONFIDENCE_SWING', 'MAX_CONFIDENCE_SCALP', 'SL_BUFFER_PCT_SWING', 'SL_BUFFER_PCT_SCALP'
        ]
        
        for key, val in updates.items():
            current_val = self.datastore.get_setting(key)
            if key in critical_settings:
                # Compare to see if there is an actual change
                if current_val is None or str(current_val).strip() != str(val).strip():
                    changed_keys.append(key)
            
            logger.info(f"APPLYING UPDATE: {key} = {val}")
            self.datastore.set_setting(key, str(val))
            
        # Determine if we should post to Discord
        last_post_str = self.datastore.get_setting("LAST_OPTIMIZER_POST_TIME")
        should_post = False
        
        if changed_keys:
            logger.info(f"Parameter changes detected, triggering Discord alert for keys: {changed_keys}")
            should_post = True
        else:
            logger.info("No parameter changes detected.")
            if last_post_str:
                try:
                    last_post = datetime.fromisoformat(last_post_str)
                    elapsed_hours = (datetime.utcnow() - last_post).total_seconds() / 3600.0
                    if elapsed_hours >= 23.0:
                        logger.info(f"Heartbeat trigger: {elapsed_hours:.2f} hours since last post. Triggering Discord alert.")
                        should_post = True
                    else:
                        logger.info(f"Only {elapsed_hours:.2f} hours since last post. Skipping Discord post.")
                except Exception as e:
                    logger.warning(f"Error parsing LAST_OPTIMIZER_POST_TIME: {e}. Triggering Discord alert.")
                    should_post = True
            else:
                logger.info("No previous post time found. Sending initial heartbeat.")
                should_post = True
                
        if should_post:
            self._send_discord_alert(updates, metrics, swing_stats, scalp_stats, hours)
            self.datastore.set_setting("LAST_OPTIMIZER_POST_TIME", datetime.utcnow().isoformat())

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _merge_type_stats(self, by_type: dict, prefix: str) -> dict:
        """Sum wins/losses across SWING_LONG + SWING_SHORT (or SCALP_*)."""
        wins   = 0
        losses = 0
        count  = 0
        for key, stats in by_type.items():
            if key.startswith(prefix):
                wins   += stats.get('wins',   0)
                losses += stats.get('losses', 0)
                count  += stats.get('count',  0)
        total_closed = wins + losses
        win_rate = round(wins / total_closed * 100, 1) if total_closed > 0 else None
        return {'wins': wins, 'losses': losses, 'count': count,
                'total_closed': total_closed, 'win_rate': win_rate}

    def _decide_threshold(self, label: str, current: float, stats: dict,
                          min_th: float, max_th: float):
        """
        Return the new threshold for a signal type, or None if no change needed.
        """
        tc = stats['total_closed']
        wr = stats['win_rate']  # None if no closed trades

        if tc < 5:
            logger.info(f"{label}: only {tc} closed trades — skipping quality adjustment.")
            return None

        if wr < 25:
            new = min(max_th, current + 2)
            logger.info(f"{label}: WR {wr}% < 25% — raising threshold {current} → {new}")
            return new
        elif wr < 40:
            new = min(max_th, current + 1)
            logger.info(f"{label}: WR {wr}% < 40% — raising threshold {current} → {new}")
            return new
        elif wr > 65 and tc >= 8:
            new = max(min_th, current - 1)
            logger.info(f"{label}: WR {wr}% > 65% — lowering threshold {current} → {new} to increase volume")
            return new
        else:
            logger.info(f"{label}: WR {wr}% in acceptable range — no change (current={current})")
            return None

    def _apply_frequency_safety_valve(self, hours: int):
        """Call independently when analysis data is unavailable."""
        current_swing = float(self.datastore.get_setting("MIN_CONFIDENCE_SWING", settings.MIN_CONFIDENCE_SWING))
        current_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP))
        if current_swing > MAX_SWING or current_scalp > MAX_SCALP:
            logger.warning("Thresholds above hard caps with no data — resetting to caps.")
            self.datastore.set_setting("MIN_CONFIDENCE_SWING", min(current_swing, MAX_SWING))
            self.datastore.set_setting("MIN_CONFIDENCE_SCALP", min(current_scalp, MAX_SCALP))

    def _run_self_healing_backtest(self, lookback_days=14):
        """
        Backtests past signals in the DB across different confidence thresholds
        to dynamically select the optimal thresholds that would have maximized net R-multiple.
        """
        logger.info(f"Running self-healing backtest over the last {lookback_days} days of signals...")
        cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        
        with self.datastore.get_connection() as conn:
            try:
                closed_signals = self.datastore._fetch_query(conn, """
                    SELECT * FROM signals
                    WHERE status IN ('TP_HIT', 'SL_HIT')
                    AND entry_time >= ?
                """, (cutoff,))
            except Exception as e:
                logger.warning(f"Could not fetch signals for backtest: {e}")
                return None, None
            
        if not closed_signals or len(closed_signals) < 5:
            logger.info("Not enough historical signals in the backtest lookback window to optimize parameters.")
            return None, None
            
        swings = [s for s in closed_signals if 'SWING' in str(s['signal_type']).upper()]
        scalps = [s for s in closed_signals if 'SCALP' in str(s['signal_type']).upper()]
        
        def optimize_subset(subset, min_cap, max_cap, label):
            best_threshold = None
            best_net_r = -999.0
            best_wr = 0.0
            
            # Grid search in 2-point increments
            thresholds = list(range(min_cap, max_cap + 1, 2))
            
            for th in thresholds:
                passed = [s for s in subset if s['confidence'] >= th]
                if len(passed) < 3:
                    continue
                    
                winners = [s for s in passed if s['status'] == 'TP_HIT']
                losers = [s for s in passed if s['status'] == 'SL_HIT']
                
                win_rate = len(winners) / len(passed)
                net_r = sum(float(w.get('rr_ratio') or 2.75) for w in winners) - len(losers)
                
                if net_r > best_net_r or (abs(net_r - best_net_r) < 0.01 and win_rate > best_wr):
                    best_net_r = net_r
                    best_threshold = th
                    best_wr = win_rate
                    
            if best_threshold is not None:
                logger.info(f"Optimal {label} threshold found: {best_threshold} (Net R: {best_net_r:+.2f}R, Win Rate: {best_wr:.1%})")
            return best_threshold
            
        opt_swing = optimize_subset(swings, 55, 85, 'SWING')
        opt_scalp = optimize_subset(scalps, 60, 88, 'SCALP')
        
        return opt_swing, opt_scalp

    def _send_discord_alert(self, updates, metrics, swing_stats, scalp_stats, hours):
        """Send update notification to Discord with per-type breakdown, active trades, and 24h PnL."""
        from integrations.discord_notifier import DiscordNotifier
        notifier = DiscordNotifier()

        def wr_str(stats):
            if stats['win_rate'] is None:
                return "N/A"
            return f"{stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)"

        # ── Pull live active trade info from the DB ──────────────────────────
        active_signals = self.datastore.get_active_signals()
        active_count = len(active_signals)

        # ── Calculate 24h PnL from closed signals ────────────────────────────
        from datetime import datetime, timedelta
        cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        with self.datastore.get_connection() as conn:
            closed_24h = self.datastore._fetch_query(conn, """
                SELECT * FROM signals
                WHERE status IN ('TP_HIT', 'SL_HIT')
                AND updated_at >= ?
                ORDER BY updated_at DESC
            """, (cutoff_24h,))

        total_r = 0.0
        tp_count = 0
        sl_count = 0
        for sig in closed_24h:
            rr = sig.get('rr_ratio') or 0.0
            if sig['status'] == 'TP_HIT':
                total_r += float(rr)
                tp_count += 1
            elif sig['status'] == 'SL_HIT':
                total_r -= 1.0
                sl_count += 1
        pnl_sign = "+" if total_r >= 0 else ""
        pnl_str = f"{pnl_sign}{total_r:.2f}R"
        # ─────────────────────────────────────────────────────────────────────

        msg  = "**🤖 ARCANE AUTO-OPTIMIZER**\n"
        msg += f"Analysis Period: Last {hours}h\n"
        msg += f"Overall: WR {metrics['win_rate_pct']}% ({metrics['winners']}W/{metrics['losers']}L) | {metrics['signals_per_hour']} sigs/hr\n"
        msg += f"↳ Swings: {wr_str(swing_stats)} | Scalps: {wr_str(scalp_stats)}\n"

        # ── Active Trades Block (with floating PnL) ─────────────────────────
        current_prices = {}
        try:
            latest_scrapes = self.datastore.get_latest_for_all_assets()
            for scrape in latest_scrapes:
                current_prices[scrape['name'].strip().upper()] = float(scrape['close'])
        except Exception:
            pass

        msg += f"\n📂 **OPEN POSITIONS: {active_count}**\n"
        total_open_pnl = 0.0
        open_pnl_count = 0

        if active_signals:
            for sig in active_signals:
                asset_key = sig['asset_name'].strip().upper()
                cur_price = current_prices.get(asset_key)
                if cur_price and sig.get('entry_price'):
                    try:
                        entry_p = float(sig['entry_price'])
                        if 'LONG' in sig['signal_type']:
                            total_open_pnl += (cur_price - entry_p) / entry_p * 100
                        else:
                            total_open_pnl += (entry_p - cur_price) / entry_p * 100
                        open_pnl_count += 1
                    except: pass

            for sig in active_signals[:8]:
                direction = "🟢 L" if "LONG" in sig['signal_type'] else "🔴 S"
                trade_type = "Swing" if "SWING" in sig['signal_type'] else "Scalp"

                pnl_tag = ""
                asset_key = sig['asset_name'].strip().upper()
                cur_price = current_prices.get(asset_key)
                if cur_price and sig.get('entry_price'):
                    try:
                        entry_p = float(sig['entry_price'])
                        if 'LONG' in sig['signal_type']:
                            pnl_pct = (cur_price - entry_p) / entry_p * 100
                        else:
                            pnl_pct = (entry_p - cur_price) / entry_p * 100
                        sign = "+" if pnl_pct >= 0 else ""
                        pnl_tag = f" `{sign}{pnl_pct:.2f}%`"
                    except: pass

                msg += f"• {direction} **{sig['asset_name']}** {trade_type} ({sig['htf']}→{sig['ltf']}){pnl_tag}\n"

            if active_count > 8:
                msg += f"• *(+{active_count - 8} more...)*\n"

            if open_pnl_count > 0:
                open_sign = "+" if total_open_pnl >= 0 else ""
                open_emoji = "🟩" if total_open_pnl >= 0 else "🟥"
                msg += f"{open_emoji} **Open PnL: {open_sign}{total_open_pnl:.2f}%** ({open_pnl_count} positions)\n"
            elif active_count > 0:
                msg += "⚠️ *Floating PnL data unavailable*\n"
        else:
            msg += "• No open positions\n"
        # ─────────────────────────────────────────────────────────────────────

        # ── 24h PnL Block ────────────────────────────────────────────────────
        pnl_emoji = "📈" if total_r >= 0 else "📉"
        msg += f"\n{pnl_emoji} **24h PnL: {pnl_str}** ({tp_count} TP / {sl_count} SL)\n"
        if closed_24h:
            for sig in closed_24h[:8]:
                direction = "🟢 L" if "LONG" in sig['signal_type'] else "🔴 S"
                trade_type = "Swing" if "SWING" in sig['signal_type'] else "Scalp"
                outcome = "TP" if sig['status'] == 'TP_HIT' else "SL"
                rr_val = f"+{sig['rr_ratio']:.2f}R" if sig['status'] == 'TP_HIT' else "-1.00R"
                msg += f"• {direction} **{sig['asset_name']}** {trade_type} ({sig['htf']}→{sig['ltf']}) -> **{outcome}** ({rr_val})\n"
            if len(closed_24h) > 8:
                msg += f"• *(+{len(closed_24h) - 8} more...)*\n"
        else:
            msg += "• *No trades hit TP/SL in the last 24h*\n"
        # ─────────────────────────────────────────────────────────────────────

        # Regime info
        regime = updates.get('MARKET_REGIME', 'RANGING')
        if regime == 'TRENDING':
            msg += "\n📈 **Market Regime: TRENDING** (Breakout capture widened)\n\n"
        else:
            msg += "\n📊 **Market Regime: RANGING** (Standard filters)\n\n"
            
        msg += "**⚡ MIN CONFIDENCE THRESHOLDS:**\n"
        
        # Get active thresholds from updates or DB/settings fallback
        swing_conf = updates.get('MIN_CONFIDENCE_SWING')
        if swing_conf is None:
            swing_conf = self.datastore.get_setting("MIN_CONFIDENCE_SWING", settings.MIN_CONFIDENCE_SWING)
        scalp_conf = updates.get('MIN_CONFIDENCE_SCALP')
        if scalp_conf is None:
            scalp_conf = self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP)
            
        msg += f"• **Swing Confidence**: Set to **{swing_conf}**\n"
        msg += f"• **Scalp Confidence**: Set to **{scalp_conf}**\n"

        # Show active advanced safety rules
        cb_active = updates.get('CIRCUIT_BREAKER_ACTIVE')
        if cb_active is None:
            cb_active = self.datastore.get_setting("CIRCUIT_BREAKER_ACTIVE")
            
        cap_val = updates.get('MAX_CRYPTO_SAME_DIRECTION')
        if cap_val is None:
            cap_val = self.datastore.get_setting("MAX_CRYPTO_SAME_DIRECTION")
            
        blacklist = updates.get('ASSET_BLACKLIST')
        if blacklist is None:
            blacklist = self.datastore.get_setting("ASSET_BLACKLIST")
            
        max_scalp = updates.get('MAX_CONFIDENCE_SCALP')
        if max_scalp is None:
            max_scalp = self.datastore.get_setting("MAX_CONFIDENCE_SCALP")
            
        sl_scalp = updates.get('SL_BUFFER_PCT_SCALP')
        if sl_scalp is None:
            sl_scalp = self.datastore.get_setting("SL_BUFFER_PCT_SCALP")
            
        has_safeties = (
            str(cb_active).lower() == 'true' or
            cap_val is not None or
            (blacklist and str(blacklist).strip()) or
            (max_scalp is not None and float(max_scalp) < 100) or
            (sl_scalp is not None and float(sl_scalp) > 0.012)
        )
        
        if has_safeties:
            msg += "\n**🛡️ ADVANCED SAFETY ENGAGED:**\n"
            if str(cb_active).lower() == 'true':
                msg += "• **🚨 Drawdown Circuit Breaker**: **ACTIVE** (Only Tier A+ setups permitted)\n"
            if cap_val is not None:
                cap_val = int(cap_val)
                reason = "Alt Decoupling (3 Max)" if cap_val == 3 else ("High Risk Tightening (1 Max)" if cap_val == 1 else "Standard (2 Max)")
                msg += f"• **Crypto Correlation Cap**: `{cap_val} positions max` ({reason})\n"
            if blacklist and str(blacklist).strip():
                msg += f"• **Toxic Assets Benched**: `{blacklist}`\n"
            if max_scalp is not None and float(max_scalp) < 100:
                msg += f"• **Max Confidence Cap**: `88%` (Filtering late 'perfect' setups)\n"
            if sl_scalp is not None and float(sl_scalp) > 0.012:
                msg += f"• **Dynamic SL**: Buffers widened for chop protection\n"

        notifier.send_message(msg)


if __name__ == "__main__":
    try:
        optimizer = AutoOptimizer()
        optimizer.run_optimization(hours=24)
    except Exception as e:
        import traceback
        err_msg = f"❌ CRITICAL ERROR: AutoOptimizer failed with exception:\n{str(e)}\n\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        try:
            from integrations.discord_notifier import DiscordNotifier
            DiscordNotifier().send_error_alert(err_msg[:1900])
        except Exception as de:
            print(f"Failed to send Discord error alert: {de}", file=sys.stderr)
        sys.exit(1)
