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
        
        # A. Win Rate Logic (Quality Control)
        # -----------------------------------
        total_closed = metrics['winners'] + metrics['losers']
        win_rate = metrics['win_rate_pct']
        
        if total_closed >= 5: # Need minimal sample size
            if win_rate < 30:
                logger.info("CRITICAL: Win rate < 30%. Increasing thresholds aggressively.")
                updates['MIN_CONFIDENCE_SWING'] = min(95, current_swing + 4)
                updates['MIN_CONFIDENCE_SCALP'] = min(95, current_scalp + 4)
                
            elif win_rate < 45:
                logger.info("WARNING: Win rate < 45%. Increasing thresholds moderately.")
                updates['MIN_CONFIDENCE_SWING'] = min(90, current_swing + 2)
                updates['MIN_CONFIDENCE_SCALP'] = min(90, current_scalp + 2)
                
            elif win_rate > 75 and metrics['signals_per_hour'] < 0.2:
                logger.info("EXCELLENT: Win rate > 75% but low volume. Lowering thresholds slightly to capture more.")
                updates['MIN_CONFIDENCE_SWING'] = max(50, current_swing - 2)
                updates['MIN_CONFIDENCE_SCALP'] = max(60, current_scalp - 2)
        else:
            logger.info(f"Not enough closed trades ({total_closed}) to adjust based on Win Rate.")

        # B. Frequency Logic (Volume Control) -- Only if Win Rate didn't trigger
        # -----------------------------------
        if not updates:
            if metrics['signals_per_hour'] > 3.0:
                logger.info("Frequency too high (>3/hr). Increasing thresholds.")
                updates['MIN_CONFIDENCE_SWING'] = min(95, current_swing + 2)
                updates['MIN_CONFIDENCE_SCALP'] = min(95, current_scalp + 2)
                
            elif metrics['signals_per_hour'] < 0.2:
                 # Only reduce if we haven't lost money recently (Safety Check)
                 if metrics['win_rate_pct'] >= 50 or total_closed == 0:
                     logger.info("Frequency too low (<0.2/hr). Decreasing thresholds.")
                     updates['MIN_CONFIDENCE_SWING'] = max(50, current_swing - 2)
                     updates['MIN_CONFIDENCE_SCALP'] = max(60, current_scalp - 2)
        
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
