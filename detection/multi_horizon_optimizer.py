"""
Multi-Horizon Self-Improvement Engine
Analyzes closed signal performance across 7, 14, 30, and 60-day lookback windows.
Applies adaptive signal-type gating penalties and multi-window threshold optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("MultiHorizonOptimizer")

class MultiHorizonOptimizer:
    def __init__(self, datastore):
        self.datastore = datastore

    def analyze_horizons(self, horizons: List[int] = [7, 14, 30, 60]) -> Dict[int, Dict]:
        """
        Analyze closed signals across multiple lookback windows.
        Returns a dictionary mapping lookback_days -> horizon_metrics.
        """
        results = {}
        now = datetime.utcnow()
        
        with self.datastore.get_connection() as conn:
            for days in horizons:
                cutoff = (now - timedelta(days=days)).isoformat()
                
                try:
                    closed = self.datastore._fetch_query(conn, """
                        SELECT id, asset_name, asset_type, signal_type, confidence,
                               status, entry_price, take_profit, stop_loss, rr_ratio, entry_time
                        FROM signals
                        WHERE status IN ('TP_HIT', 'SL_HIT', 'BREAKEVEN')
                        AND entry_time >= ?
                    """, (cutoff,))
                except Exception as e:
                    logger.warning(f"Error fetching closed signals for horizon {days}d: {e}")
                    closed = []
                    
                winners = [s for s in closed if s['status'] == 'TP_HIT']
                losers = [s for s in closed if s['status'] == 'SL_HIT']
                breakevens = [s for s in closed if s['status'] == 'BREAKEVEN']
                
                total_closed = len(closed)
                win_rate = (len(winners) / total_closed * 100.0) if total_closed > 0 else 0.0
                net_r = sum(float(w.get('rr_ratio') or 1.8) for w in winners) - len(losers)
                
                # Breakdown by Signal Type
                type_stats = {}
                signal_types = ['SWING_LONG', 'SWING_SHORT', 'SCALP_LONG', 'SCALP_SHORT']
                for st in signal_types:
                    st_closed = [s for s in closed if s['signal_type'] == st]
                    st_wins = [s for s in st_closed if s['status'] == 'TP_HIT']
                    st_losses = [s for s in st_closed if s['status'] == 'SL_HIT']
                    st_total = len(st_closed)
                    st_wr = (len(st_wins) / st_total * 100.0) if st_total > 0 else 0.0
                    st_r = sum(float(w.get('rr_ratio') or 1.8) for w in st_wins) - len(st_losses)
                    
                    type_stats[st] = {
                        'total': st_total,
                        'wins': len(st_wins),
                        'losses': len(st_losses),
                        'win_rate': round(st_wr, 1),
                        'net_r': round(st_r, 2)
                    }
                    
                results[days] = {
                    'total_closed': total_closed,
                    'winners': len(winners),
                    'losers': len(losers),
                    'breakevens': len(breakevens),
                    'win_rate': round(win_rate, 1),
                    'net_r': round(net_r, 2),
                    'by_type': type_stats
                }
                
        return results

    def determine_adaptive_gating(self, horizon_data: Dict[int, Dict]) -> Dict[str, Dict]:
        """
        Evaluate performance across 7d, 14d, and 30d windows to set signal-type gating.
        Returns dict mapping signal_type -> {'penalty': float, 'halt': bool, 'reason': str}.
        """
        adjustments = {}
        signal_types = ['SWING_LONG', 'SWING_SHORT', 'SCALP_LONG', 'SCALP_SHORT']
        
        d7 = horizon_data.get(7, {})
        d14 = horizon_data.get(14, {})
        d30 = horizon_data.get(30, {})
        
        for st in signal_types:
            st7 = d7.get('by_type', {}).get(st, {'total': 0, 'win_rate': 0.0, 'net_r': 0.0})
            st14 = d14.get('by_type', {}).get(st, {'total': 0, 'win_rate': 0.0, 'net_r': 0.0})
            st30 = d30.get('by_type', {}).get(st, {'total': 0, 'win_rate': 0.0, 'net_r': 0.0})
            
            penalty = 0.0
            halt = False
            reason = "Performing normally."
            
            # Rule 1: Auto-Halt on 0% Win Rate over 7d with at least 3 trades
            if st7['total'] >= 3 and st7['win_rate'] == 0.0:
                halt = True
                penalty = 15.0
                reason = f"AUTO-HALT: 0% WR ({st7['total']}L in 7d). Un-halts as active trades hit TP or as losses age out of 7d window."
            # Rule 2: Severe Underperformance (Win Rate < 30% or Net R < -2.0) across 7d/14d
            elif (st7['total'] >= 2 and st7['win_rate'] < 30.0) or (st14['total'] >= 4 and st14['win_rate'] < 30.0):
                penalty = 10.0
                reason = f"HIGH GATING (+10% conf required): 7d WR={st7['win_rate']}%, 14d WR={st14['win_rate']}%."
            # Rule 3: Moderate Underperformance (Win Rate 30-45%)
            elif (st14['total'] >= 3 and st14['win_rate'] < 45.0) or (st30['total'] >= 5 and st30['win_rate'] < 45.0):
                penalty = 5.0
                reason = f"MODERATE GATING (+5% conf required): 14d WR={st14['win_rate']}%, 30d WR={st30['win_rate']}%."
            # Rule 4: Recovery (7d WR >= 50% with at least 2 trades)
            elif st7['total'] >= 2 and st7['win_rate'] >= 50.0:
                penalty = 0.0
                reason = f"RECOVERED: 7d WR={st7['win_rate']}% — full signal access restored."
                
            adjustments[st] = {
                'penalty': penalty,
                'halt': halt,
                'reason': reason
            }
            
        return adjustments

    def optimize_thresholds(self, horizon_data: Dict[int, Dict]) -> Tuple[float, float]:
        """
        Derive optimal confidence thresholds for Swings and Scalps based on multi-window backtests.
        """
        # Fetch closed signals from the past 30 days
        now = datetime.utcnow()
        cutoff = (now - timedelta(days=30)).isoformat()
        
        with self.datastore.get_connection() as conn:
            try:
                closed = self.datastore._fetch_query(conn, """
                    SELECT * FROM signals
                    WHERE status IN ('TP_HIT', 'SL_HIT')
                    AND entry_time >= ?
                """, (cutoff,))
            except Exception as e:
                logger.warning(f"Error fetching signals for threshold optimization: {e}")
                closed = []
                
        swings = [s for s in closed if 'SWING' in str(s['signal_type']).upper()]
        scalps = [s for s in closed if 'SCALP' in str(s['signal_type']).upper()]
        
        def grid_search(subset, min_th, max_th, default_th):
            best_th = default_th
            best_net_r = -999.0
            
            for th in range(min_th, max_th + 1, 2):
                passed = [s for s in subset if s['confidence'] >= th]
                if len(passed) < 3:
                    continue
                winners = [s for s in passed if s['status'] == 'TP_HIT']
                losers = [s for s in passed if s['status'] == 'SL_HIT']
                net_r = sum(float(w.get('rr_ratio') or 1.8) for w in winners) - len(losers)
                
                if net_r > best_net_r:
                    best_net_r = net_r
                    best_th = th
                    
            return float(best_th)

        opt_swing = grid_search(swings, 68, 85, 68.0)
        opt_scalp = grid_search(scalps, 72, 88, 72.0)
        
        return opt_swing, opt_scalp

    def format_discord_report(self, horizon_data: Dict[int, Dict], adjustments: Dict[str, Dict], swing_th: float, scalp_th: float) -> str:
        """Format the Multi-Horizon Self-Improvement report for Discord alerts."""
        lines = [
            "🧠 **MULTI-HORIZON SELF-IMPROVEMENT ENGINE REPORT**",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "📊 **Performance Across Horizons:**"
        ]
        
        for days in [7, 14, 30, 60]:
            h = horizon_data.get(days, {})
            lines.append(f"  • **{days} Days**: Win Rate: **{h.get('win_rate', 0)}%** ({h.get('winners', 0)}W/{h.get('losers', 0)}L) | Net R: **{h.get('net_r', 0):+.2f}R**")
            
        lines += [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "⚡ **Adaptive Signal Gating & Suppression:**"
        ]
        
        for st, adj in adjustments.items():
            status_icon = "🛑 HALTED" if adj['halt'] else (f"⚠️ +{adj['penalty']:.0f}% Gated" if adj['penalty'] > 0 else "✅ Normal")
            lines.append(f"  • **{st}**: {status_icon} — _{adj['reason']}_")
            
        lines += [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🎯 **Auto-Optimized Thresholds**: Swing: **{swing_th:.0f}%** | Scalp: **{scalp_th:.0f}%**"
        ]
        
        return "\n".join(lines)
