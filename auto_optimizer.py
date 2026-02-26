"""
Automated Signal Optimizer (Iterative Loop)

Runs analysis on recent signals and automatically adjusts confidence thresholds
based on performance metrics (Win Rate, Frequency).
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

class AutoOptimizer:
    def __init__(self):
        self.datastore = MangoDataStore()
        self.analyzer = SignalAnalyzer()
        
    def run_optimization(self, hours=24):
        """Run analysis and apply updates"""
        logger.info(f"Running optimization for last {hours} hours...")
        
        # 1. Get Analysis
        # Try primary timeframe, then fallback if not enough data
        analysis = self.analyzer.analyze_recent_signals(hours)
        if 'error' in analysis:
            logger.warning(f"Analysis failed: {analysis['error']}")
            return
            
        metrics = analysis['metrics']
        total_closed = metrics['winners'] + metrics['losers']
        
        # Fallback to 48 hours if not enough data in 24 hours
        if total_closed < 5 and hours < 48:
            logger.info(f"Not enough closed trades ({total_closed}) in {hours}h. Expanding to 48h...")
            analysis_48 = self.analyzer.analyze_recent_signals(48)
            
            if 'error' not in analysis_48:
                metrics_48 = analysis_48['metrics']
                total_closed_48 = metrics_48['winners'] + metrics_48['losers']
                
                # Only switch if 48h actually gives us more data to work with
                if total_closed_48 >= 5:
                    logger.info(f"Using 48h data: {total_closed_48} closed trades found.")
                    analysis = analysis_48
                    metrics = metrics_48
                    hours = 48 # Update hour tracking for logs
                else:
                    logger.info(f"Still not enough data in 48h ({total_closed_48} closed). Reverting to {hours}h.")

        # Log current metrics
        logger.info(f"Metrics ({hours}h): WR={metrics['win_rate_pct']}%, Signals={metrics['total_signals']}, Freq={metrics['signals_per_hour']}/hr")
        
        # 2. Get Current Settings (from DB or default)
        current_swing = float(self.datastore.get_setting("MIN_CONFIDENCE_SWING", settings.MIN_CONFIDENCE_SWING))
        current_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP))
        
        logger.info(f"Current Thresholds -> Swing: {current_swing}, Scalp: {current_scalp}")
        
        updates = {}
        
        # 3. Apply Decision Logic (Iterative Improvement)
        # HARD CAPS - confidence formula rarely exceeds 92, so caps must be reasonable
        MAX_SWING = 85  # Hard ceiling for swing threshold
        MAX_SCALP = 88  # Hard ceiling for scalp threshold
        MIN_SWING = 60  # Hard floor for swing threshold
        MIN_SCALP = 65  # Hard floor for scalp threshold
        
        # A. Win Rate Logic (Quality Control)
        # -----------------------------------
        total_closed = metrics['winners'] + metrics['losers']
        win_rate = metrics['win_rate_pct']
        
        if total_closed >= 5: # Need minimal sample size
            if win_rate < 25:
                logger.info("CRITICAL: Win rate < 25%. Increasing thresholds moderately.")
                updates['MIN_CONFIDENCE_SWING'] = min(MAX_SWING, current_swing + 2)
                updates['MIN_CONFIDENCE_SCALP'] = min(MAX_SCALP, current_scalp + 2)
                
            elif win_rate < 40:
                logger.info("WARNING: Win rate < 40%. Increasing thresholds slightly.")
                updates['MIN_CONFIDENCE_SWING'] = min(MAX_SWING, current_swing + 1)
                updates['MIN_CONFIDENCE_SCALP'] = min(MAX_SCALP, current_scalp + 1)
                
            elif win_rate > 60 and metrics['signals_per_hour'] < 0.5:
                logger.info("GOOD: Win rate > 60% but low volume. Lowering thresholds to capture more.")
                updates['MIN_CONFIDENCE_SWING'] = max(MIN_SWING, current_swing - 2)
                updates['MIN_CONFIDENCE_SCALP'] = max(MIN_SCALP, current_scalp - 2)
        else:
            logger.info(f"Not enough closed trades ({total_closed}) to adjust based on Win Rate.")

        # B. Frequency Safety Valve -- Prevent system from choking itself
        # Even if win rate is poor, if we're generating almost NO signals,
        # thresholds are clearly too high and must come down.
        # -----------------------------------
        if not updates:
            if metrics['signals_per_hour'] > 3.0:
                logger.info("Frequency too high (>3/hr). Increasing thresholds.")
                updates['MIN_CONFIDENCE_SWING'] = min(MAX_SWING, current_swing + 2)
                updates['MIN_CONFIDENCE_SCALP'] = min(MAX_SCALP, current_scalp + 2)
                
            elif metrics['signals_per_hour'] < 0.3:
                logger.info("Frequency critically low (<0.3/hr). Decreasing thresholds (safety valve).")
                updates['MIN_CONFIDENCE_SWING'] = max(MIN_SWING, current_swing - 3)
                updates['MIN_CONFIDENCE_SCALP'] = max(MIN_SCALP, current_scalp - 3)
        
        # 4. Apply Updates
        if updates:
            for key, val in updates.items():
                logger.info(f"APPLYING UPDATE: {key} = {val}")
                self.datastore.set_setting(key, val)
            
            # Send Discord Notification
            self._send_discord_alert(updates, metrics)
        else:
            logger.info("No adjustments needed at this time.")

    def _send_discord_alert(self, updates, metrics):
        """Send update notification to Discord"""
        from integrations.discord_notifier import DiscordNotifier
        notifier = DiscordNotifier()
        
        msg = "**🤖 ARCANE AUTO-OPTIMIZER**\n"
        msg += f"Analysis Period: Last 24h\n"
        msg += f"Performance: WR {metrics['win_rate_pct']}% ({metrics['winners']}W/{metrics['losers']}L) | {metrics['signals_per_hour']} sigs/hr\n\n"
        msg += "**⚡ ADJUSTMENTS APPLIED:**\n"
        
        for k, v in updates.items():
            name = k.replace("MIN_CONFIDENCE_", "").title()
            msg += f"• **{name} Confidence**: Set to **{v}**\n"
            
        notifier.send_message(msg)

if __name__ == "__main__":
    optimizer = AutoOptimizer()
    optimizer.run_optimization(hours=24)
