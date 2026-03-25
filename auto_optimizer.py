"""
Automated Signal Optimizer (Iterative Loop)

Runs analysis on recent signals and automatically adjusts confidence thresholds
based on performance metrics (Win Rate, Frequency) — SEPARATELY for scalps and swings.
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

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
MIN_SWING = 60   # Never go below these — too noisy below here
MIN_SCALP = 65
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
        if 'error' in analysis:
            logger.warning(f"Analysis failed: {analysis['error']}")
            # Still attempt the frequency safety valve even without rich data
            self._apply_frequency_safety_valve(hours)
            return

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

        # 3. Per-type win rate analysis (most important improvement)
        #    Adjust swing and scalp INDEPENDENTLY based on their own performance.
        by_type = breakdowns.get('by_signal_type', {})
        swing_stats = self._merge_type_stats(by_type, 'SWING')
        scalp_stats = self._merge_type_stats(by_type, 'SCALP')

        swing_update = self._decide_threshold(
            label='SWING', current=current_swing,
            stats=swing_stats,
            min_th=MIN_SWING, max_th=MAX_SWING
        )
        scalp_update = self._decide_threshold(
            label='SCALP', current=current_scalp,
            stats=scalp_stats,
            min_th=MIN_SCALP, max_th=MAX_SCALP
        )

        if swing_update is not None:
            updates['MIN_CONFIDENCE_SWING'] = swing_update
        if scalp_update is not None:
            updates['MIN_CONFIDENCE_SCALP'] = scalp_update
            
        # 3b. Advanced Optimization: Asset Blacklisting
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
        if metrics['losers'] >= 5 and metrics['win_rate_pct'] < 30:
            logger.info(f"Systemic bleed detected (WR: {metrics['win_rate_pct']}%). Widening SL buffers for chop protection.")
            updates['SL_BUFFER_PCT_SWING'] = 0.025
            updates['SL_BUFFER_PCT_SCALP'] = 0.012
        elif metrics['win_rate_pct'] > 45:
            updates['SL_BUFFER_PCT_SWING'] = 0.015
            updates['SL_BUFFER_PCT_SCALP'] = 0.008

        # 3e. Market Regime Detection (TRENDING vs RANGING)
        regime_result = self.regime_detector.detect_regime(lookback_hours=4)
        regime = regime_result['regime']
        regime_conf = regime_result['confidence']
        regime_dir = regime_result.get('trending_direction', 'MIXED')
        logger.info(f"Market Regime: {regime} (confidence={regime_conf:.0f}, direction={regime_dir})")
        logger.info(f"  Details: {regime_result['details']}")

        updates['MARKET_REGIME'] = regime

        if regime == 'TRENDING':
            # On trending days: widen breakout capture and lower thresholds slightly
            updates['BREAKOUT_CAPTURE_PCT'] = 0.01  # 1% beyond zone (was 0.3%)
            # Lower thresholds by 3 to capture more setups (trending = higher conviction)
            if 'MIN_CONFIDENCE_SWING' not in updates:
                updates['MIN_CONFIDENCE_SWING'] = max(MIN_SWING, current_swing - 3)
            if 'MIN_CONFIDENCE_SCALP' not in updates:
                updates['MIN_CONFIDENCE_SCALP'] = max(MIN_SCALP, current_scalp - 3)
            logger.info(f"TRENDING regime: widened breakout capture to 1%, lowered thresholds")
        else:
            # Ranging: standard settings
            updates['BREAKOUT_CAPTURE_PCT'] = 0.003  # Default 0.3%

        # 4. Global frequency safety valve — fires if PER-TYPE analysis didn't act
        #    (prevents system from starving itself when no closed data exists yet)
        if not updates:
            freq = metrics['signals_per_hour']
            if freq > 4.0:
                logger.info(f"Frequency too high ({freq}/hr). Raising all thresholds.")
                updates['MIN_CONFIDENCE_SWING'] = min(MAX_SWING, current_swing + 2)
                updates['MIN_CONFIDENCE_SCALP'] = min(MAX_SCALP, current_scalp + 2)
            elif freq < 0.3:
                logger.info(f"Frequency critically low ({freq}/hr). Lowering all thresholds (safety valve).")
                updates['MIN_CONFIDENCE_SWING'] = max(MIN_SWING, current_swing - 3)
                updates['MIN_CONFIDENCE_SCALP'] = max(MIN_SCALP, current_scalp - 3)

        # 5. Apply
        if updates:
            for key, val in updates.items():
                logger.info(f"APPLYING UPDATE: {key} = {val}")
                self.datastore.set_setting(key, val)
            self._send_discord_alert(updates, metrics, swing_stats, scalp_stats, hours)
        else:
            logger.info("No adjustments needed at this time.")

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

        Rules:
        - Need ≥5 closed trades to make quality-based changes.
        - WR < 25%  → raise by 2  (clear underperformance)
        - WR < 40%  → raise by 1
        - WR 40-60% → hold (acceptable range)
        - WR > 60% AND frequency looks ok → lower by 1 to catch more
        - If < 5 closed, skip quality check (frequency valve handles it globally)
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
        # With no data at all, just gently nudge down to ensure signals can flow
        if current_swing > MAX_SWING or current_scalp > MAX_SCALP:
            logger.warning("Thresholds above hard caps with no data — resetting to caps.")
            self.datastore.set_setting("MIN_CONFIDENCE_SWING", min(current_swing, MAX_SWING))
            self.datastore.set_setting("MIN_CONFIDENCE_SCALP", min(current_scalp, MAX_SCALP))

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
        # We approximate PnL using R-multiples based on the signal's RR ratio:
        #   TP_HIT  → +RR (e.g. 2.75R swing win = +2.75% for 1% risk)
        #   SL_HIT  → -1.0 (always lose 1R on a stop-loss)
        # This gives a normalised "R" total — not dollar PnL (which depends on position size).
        all_24h = self.datastore.get_signal_history(hours=hours)
        total_r = 0.0
        tp_count = 0
        sl_count = 0
        for sig in all_24h:
            rr = sig.get('rr_ratio') or 0
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
        # Fetch current prices for PnL calculation
        current_prices = {}
        try:
            latest_scrapes = self.datastore.get_latest_for_all_assets()
            for scrape in latest_scrapes:
                # Key: BTC, SPX, etc. (normalized)
                current_prices[scrape['name'].strip().upper()] = float(scrape['close'])
        except Exception:
            pass

        msg += f"\n📂 **OPEN POSITIONS: {active_count}**\n"
        total_open_pnl = 0.0
        open_pnl_count = 0

        if active_signals:
            # First, calculate PnL for ALL positions to get the grand total
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

            # Now build the display lines for top 8
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

            # Summed open PnL
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
        # ─────────────────────────────────────────────────────────────────────

        # Regime info
        regime = updates.get('MARKET_REGIME', 'RANGING')
        if regime == 'TRENDING':
            msg += "\n📈 **Market Regime: TRENDING** (Breakout capture widened)\n\n"
        else:
            msg += "\n📊 **Market Regime: RANGING** (Standard filters)\n\n"
        msg += "**⚡ MIN CONFIDENCE THRESHOLDS:**\n"

        for k, v in updates.items():
            if "MIN_CONFIDENCE" in k:
                name = k.replace("MIN_CONFIDENCE_", "").title()
                msg += f"• **{name} Confidence**: Set to **{v}**\n"
                
        # Group advanced optimizations
        advanced_updates = {k: v for k, v in updates.items() if "MIN_CONFIDENCE" not in k}
        if advanced_updates:
            msg += "\n**🛡️ ADVANCED SAFETY ENGAGED:**\n"
            if 'ASSET_BLACKLIST' in advanced_updates and advanced_updates['ASSET_BLACKLIST']:
                msg += f"• **Toxic Assets Benched**: `{advanced_updates['ASSET_BLACKLIST']}`\n"
            if 'MAX_CONFIDENCE_SCALP' in advanced_updates and advanced_updates['MAX_CONFIDENCE_SCALP'] < 100:
                msg += f"• **Max Confidence Cap**: `88%` (Filtering late 'perfect' setups)\n"
            if 'SL_BUFFER_PCT_SCALP' in advanced_updates and advanced_updates['SL_BUFFER_PCT_SCALP'] > 0.008:
                msg += f"• **Dynamic SL**: Buffers widened for chop protection\n"

        notifier.send_message(msg)



if __name__ == "__main__":
    optimizer = AutoOptimizer()
    optimizer.run_optimization(hours=24)
