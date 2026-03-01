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
        """Send update notification to Discord with per-type breakdown."""
        from integrations.discord_notifier import DiscordNotifier
        notifier = DiscordNotifier()

        def wr_str(stats):
            if stats['win_rate'] is None:
                return "N/A"
            return f"{stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)"

        msg  = "**🤖 ARCANE AUTO-OPTIMIZER**\n"
        msg += f"Analysis Period: Last {hours}h\n"
        msg += f"Overall: WR {metrics['win_rate_pct']}% ({metrics['winners']}W/{metrics['losers']}L) | {metrics['signals_per_hour']} sigs/hr\n"
        msg += f"↳ Swings: {wr_str(swing_stats)} | Scalps: {wr_str(scalp_stats)}\n\n"
        msg += "**⚡ ADJUSTMENTS APPLIED:**\n"

        for k, v in updates.items():
            name = k.replace("MIN_CONFIDENCE_", "").title()
            msg += f"• **{name} Confidence**: Set to **{v}**\n"

        notifier.send_message(msg)


if __name__ == "__main__":
    optimizer = AutoOptimizer()
    optimizer.run_optimization(hours=24)
