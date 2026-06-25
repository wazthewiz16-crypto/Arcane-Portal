"""
Signal Performance Analyzer
Analyzes signals from last 24-48 hours and suggests filter adjustments
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Fix UnicodeEncodeError on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env file BEFORE importing datastore
from dotenv import load_dotenv
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os
import pytz

class SignalAnalyzer:
    def __init__(self):
        self.datastore = MangoDataStore()
    
    def analyze_recent_signals(self, hours=24):
        """Analyze signals from the last N hours"""
        
        # Get all signals using SQL
        with self.datastore.get_connection() as conn:
            all_signals = self.datastore._fetch_query(conn, """
                SELECT * FROM signals
                ORDER BY created_at DESC
            """)
        
        if not all_signals:
            return {
                'error': 'No signals in database',
                'total_signals': 0
            }
        
        # Filter to recent signals
        # created_at is UTC, so we must use utcnow() for comparison
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_signals = []
        for s in all_signals:
            # Handle potential timezone strings in DB
            try:
                sig_time = datetime.fromisoformat(s['created_at'].replace('Z', '+00:00'))
                # Convert to naive UTC for comparison if needed
                if sig_time.tzinfo is not None:
                    sig_time = sig_time.astimezone(pytz.utc).replace(tzinfo=None)
                
                if sig_time > cutoff_time:
                    recent_signals.append(s)
            except Exception:
                continue
        
        if not recent_signals:
            return {
                'error': f'No signals in last {hours} hours',
                'total_signals': len(all_signals),
                'oldest_signal': all_signals[0]['created_at'] if all_signals else None
            }
        
        # Analyze metrics
        analysis = {
            'period_hours': hours,
            'total_signals': len(recent_signals),
            'timeframe': cutoff_time.strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': self._calculate_metrics(recent_signals, period_hours=hours),
            'breakdowns': self._calculate_breakdowns(recent_signals),
            'recommendations': []
        }
        
        # Generate recommendations
        analysis['recommendations'] = self._generate_recommendations(analysis['metrics'], analysis['breakdowns'])
        
        return analysis
    
    def _calculate_metrics(self, signals, period_hours=None):
        """Calculate overall metrics"""
        
        total = len(signals)
        
        # Status breakdown
        status_counts = defaultdict(int)
        for s in signals:
            status_counts[s['status']] += 1
        
        # Win/Loss calculation (only for closed signals)
        # DB uses: TP_HIT, SL_HIT, CLOSED (Upper case)
        closed = [s for s in signals if s['status'] in ['TP_HIT', 'SL_HIT', 'CLOSED', 'hit_tp', 'hit_sl']]
        winners = [s for s in closed if s['status'] in ['TP_HIT', 'hit_tp']]
        losers = [s for s in closed if s['status'] in ['SL_HIT', 'hit_sl']]
        
        win_rate = (len(winners) / len(closed) * 100) if closed else 0
        
        # Confidence distribution
        confidences = [s['confidence'] for s in signals]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        min_confidence = min(confidences) if confidences else 0
        max_confidence = max(confidences) if confidences else 0
        
        # RR ratios
        rr_ratios = [s.get('rr_ratio', 0) for s in signals if s.get('rr_ratio')]
        avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
        
        # Calculate hourly rate
        if period_hours:
            hours_span = period_hours
        else:
            earliest = min(datetime.fromisoformat(s['created_at']) for s in signals)
            latest = max(datetime.fromisoformat(s['created_at']) for s in signals)
            hours_span = (latest - earliest).total_seconds() / 3600
        
        signals_per_hour = total / hours_span if hours_span > 0 else 0
        
        return {
            'total_signals': total,
            'signals_per_hour': round(signals_per_hour, 2),
            'active': status_counts.get('ACTIVE', 0) + status_counts.get('active', 0),
            'hit_tp': status_counts.get('TP_HIT', 0) + status_counts.get('hit_tp', 0),
            'hit_sl': status_counts.get('SL_HIT', 0) + status_counts.get('hit_sl', 0),
            'closed': status_counts.get('CLOSED', 0) + status_counts.get('closed', 0),
            'win_rate_pct': round(win_rate, 1),
            'winners': len(winners),
            'losers': len(losers),
            'avg_confidence': round(avg_confidence, 1),
            'min_confidence': round(min_confidence, 1),
            'max_confidence': round(max_confidence, 1),
            'avg_rr_ratio': round(avg_rr, 2)
        }
    
    def _calculate_breakdowns(self, signals):
        """Calculate breakdowns by type, timeframe, asset"""
        
        # By signal type
        by_type = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0})
        for s in signals:
            signal_type = s['signal_type']
            by_type[signal_type]['count'] += 1
            if s['status'] in ['TP_HIT', 'hit_tp']:
                by_type[signal_type]['wins'] += 1
            elif s['status'] in ['SL_HIT', 'hit_sl']:
                by_type[signal_type]['losses'] += 1
        
        # Calculate win rates
        for t in by_type:
            total_closed = by_type[t]['wins'] + by_type[t]['losses']
            by_type[t]['win_rate'] = round((by_type[t]['wins'] / total_closed * 100) if total_closed > 0 else 0, 1)
        
        # By timeframe (LTF)
        by_ltf = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0})
        for s in signals:
            ltf = s['ltf']
            by_ltf[ltf]['count'] += 1
            if s['status'] in ['TP_HIT', 'hit_tp']:
                by_ltf[ltf]['wins'] += 1
            elif s['status'] in ['SL_HIT', 'hit_sl']:
                by_ltf[ltf]['losses'] += 1
        
        for tf in by_ltf:
            total_closed = by_ltf[tf]['wins'] + by_ltf[tf]['losses']
            by_ltf[tf]['win_rate'] = round((by_ltf[tf]['wins'] / total_closed * 100) if total_closed > 0 else 0, 1)
        
        # By asset (full win/loss tracking)
        by_asset = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0})
        for s in signals:
            asset = s['asset_name']
            by_asset[asset]['count'] += 1
            if s['status'] in ['TP_HIT', 'hit_tp']:
                by_asset[asset]['wins'] += 1
            elif s['status'] in ['SL_HIT', 'hit_sl']:
                by_asset[asset]['losses'] += 1
                
        for a in by_asset:
            total_closed = by_asset[a]['wins'] + by_asset[a]['losses']
            by_asset[a]['win_rate'] = round((by_asset[a]['wins'] / total_closed * 100) if total_closed > 0 else 0, 1)

        # By confidence bucket (grouped by 5)
        by_conf = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0})
        for s in signals:
            try:
                conf = float(s['confidence'])
                bucket = int((conf // 5) * 5)  # groups into 75, 80, 85, 90, 95 etc
                by_conf[bucket]['count'] += 1
                if s['status'] in ['TP_HIT', 'hit_tp']:
                    by_conf[bucket]['wins'] += 1
                elif s['status'] in ['SL_HIT', 'hit_sl']:
                    by_conf[bucket]['losses'] += 1
            except:
                pass
                
        for b in by_conf:
            total_closed = by_conf[b]['wins'] + by_conf[b]['losses']
            by_conf[b]['win_rate'] = round((by_conf[b]['wins'] / total_closed * 100) if total_closed > 0 else 0, 1)

        # Get top 5 assets by signal count
        top_5 = sorted(by_asset.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        top_5_assets = [(k, v['count']) for k, v in top_5]

        return {
            'by_signal_type': dict(by_type),
            'by_timeframe': dict(by_ltf),
            'by_asset': dict(by_asset),
            'by_confidence': dict(by_conf),
            'top_5_assets': top_5_assets
        }
    
    def _generate_recommendations(self, metrics, breakdowns):
        """Generate actionable recommendations based on analysis"""
        
        recommendations = []
        
        # 1. Frequency check
        # 1. Frequency check
        current_swing = float(os.getenv("MIN_CONFIDENCE_SWING", "68"))
        current_scalp = float(os.getenv("MIN_CONFIDENCE_SCALP", "78"))
        
        if metrics['signals_per_hour'] < 0.5:
            new_swing = max(50, current_swing - 3)
            new_scalp = max(60, current_scalp - 3)
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Frequency',
                'issue': f"Low signal frequency: {metrics['signals_per_hour']}/hour",
                'action': f"Lower confidence thresholds: Swing {current_swing}->{new_swing}, Scalp {current_scalp}->{new_scalp}",
                'target': 'config/settings.py'
            })
        elif metrics['signals_per_hour'] > 3:
            new_swing = min(95, current_swing + 3)
            new_scalp = min(95, current_scalp + 3)
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Frequency',
                'issue': f"High signal frequency: {metrics['signals_per_hour']}/hour",
                'action': f"Increase confidence thresholds: Swing {current_swing}->{new_swing}, Scalp {current_scalp}->{new_scalp}",
                'target': 'config/settings.py'
            })
        
        # 2. Win rate check (only if we have enough closed trades)
        total_closed = metrics['winners'] + metrics['losers']
        if total_closed >= 10:
            if metrics['win_rate_pct'] < 25:
                recommendations.append({
                    'priority': 'CRITICAL',
                    'category': 'Quality',
                    'issue': f"Very low win rate: {metrics['win_rate_pct']}%",
                    'action': 'Increase confidence thresholds by 5 points AND review stop loss calculation',
                    'target': 'config/settings.py + detection/signals.py (_calculate_tp_sl)'
                })
            elif metrics['win_rate_pct'] < 40: # Bumped for higher standard
                new_val = min(90, current_swing + 4)
                recommendations.append({
                    'priority': 'HIGH',
                    'category': 'Quality',
                    'issue': f"Low win rate: {metrics['win_rate_pct']}%",
                    'action': f"Increase confidence thresholds significantly (e.g. Swing {current_swing}->{new_val})",
                    'target': 'config/settings.py'
                })
            elif metrics['win_rate_pct'] > 60:
                new_val = max(50, current_swing - 2)
                recommendations.append({
                    'priority': 'LOW',
                    'category': 'Quality',
                    'issue': f"High win rate: {metrics['win_rate_pct']}% (may be too selective)",
                    'action': f"Consider lowering confidence slightly (e.g. Swing {current_swing}->{new_val}) for more signals",
                    'target': 'config/settings.py'
                })
        else:
            recommendations.append({
                'priority': 'INFO',
                'category': 'Data',
                'issue': f"Only {total_closed} closed trades (need 10+ for reliable win rate)",
                'action': 'Wait for more data before making adjustments',
                'target': 'Monitor for 24-48 more hours'
            })
        
        # 3. Confidence distribution check
        confidence_spread = metrics['max_confidence'] - metrics['min_confidence']
        if confidence_spread < 10:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Confidence',
                'issue': f"Narrow confidence range: {metrics['min_confidence']}-{metrics['max_confidence']}%",
                'action': 'All signals are similar quality - this is normal but limits selectivity',
                'target': 'No action needed unless win rate is poor'
            })
        
        # 4. Signal type performance
        by_type = breakdowns['by_signal_type']
        for signal_type, stats in by_type.items():
            total_closed_type = stats['wins'] + stats['losses']
            if total_closed_type >= 5:  # Need at least 5 closed trades
                if stats['win_rate'] < 25:
                    recommendations.append({
                        'priority': 'HIGH',
                        'category': 'Signal Type Performance',
                        'issue': f"{signal_type} has poor win rate: {stats['win_rate']}%",
                        'action': f"Consider disabling {signal_type} or increasing its confidence requirement",
                        'target': 'detection/signals.py'
                    })
        
        # 5. Timeframe performance
        by_ltf = breakdowns['by_timeframe']
        for timeframe, stats in by_ltf.items():
            total_closed_tf = stats['wins'] + stats['losses']
            if total_closed_tf >= 5:
                if stats['win_rate'] < 25:
                    recommendations.append({
                        'priority': 'MEDIUM',
                        'category': 'Timeframe Performance',
                        'issue': f"{timeframe} timeframe has poor win rate: {stats['win_rate']}%",
                        'action': f"Consider increasing confidence for {timeframe} signals or review {timeframe} entry logic",
                        'target': 'detection/signals.py'
                    })
        
        # 6. Candle body size check (infer from low frequency + low win rate)
        if metrics['signals_per_hour'] < 0.8 and metrics['win_rate_pct'] < 30 and total_closed >= 5:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Entry Filters',
                'issue': 'Low frequency + low win rate suggests filters are not effective',
                'action': 'Review candle body size (0.25%) and body ratio (40%) - may need adjustment',
                'target': 'detection/signals.py: _check_ltf_entry()'
            })
        
        # Sort by priority
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 5))
        
        return recommendations
    
    def print_analysis(self, hours=24):
        """Print formatted analysis report"""
        
        analysis = self.analyze_recent_signals(hours)
        
        print("\n" + "=" * 80)
        print(f"SIGNAL PERFORMANCE ANALYSIS - Last {hours} Hours")
        print("=" * 80)
        
        if 'error' in analysis:
            print(f"\n❌ {analysis['error']}")
            if 'total_signals' in analysis:
                print(f"   Total signals in database: {analysis['total_signals']}")
            if 'oldest_signal' in analysis:
                print(f"   Oldest signal: {analysis['oldest_signal']}")
            return
        
        # Metrics
        m = analysis['metrics']
        print(f"\n📊 OVERALL METRICS")
        print(f"   Period: {analysis['timeframe']} to now")
        print(f"   Total Signals: {m['total_signals']}")
        print(f"   Frequency: {m['signals_per_hour']}/hour")
        print(f"\n   Status Breakdown:")
        print(f"      Active: {m['active']}")
        print(f"      Hit TP: {m['hit_tp']} ✅")
        print(f"      Hit SL: {m['hit_sl']} ❌")
        print(f"      Closed: {m['closed']}")
        
        print(f"\n   Performance:")
        print(f"      Win Rate: {m['win_rate_pct']}% ({m['winners']}W / {m['losers']}L)")
        print(f"      Avg Confidence: {m['avg_confidence']}%")
        print(f"      Confidence Range: {m['min_confidence']}% - {m['max_confidence']}%")
        print(f"      Avg RR Ratio: {m['avg_rr_ratio']}:1")
        
        # Breakdowns
        b = analysis['breakdowns']
        
        print(f"\n📈 BY SIGNAL TYPE:")
        for signal_type, stats in b['by_signal_type'].items():
            print(f"   {signal_type}:")
            print(f"      Count: {stats['count']}")
            print(f"      Win Rate: {stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)")
        
        print(f"\n⏱️  BY TIMEFRAME:")
        for tf, stats in b['by_timeframe'].items():
            print(f"   {tf}:")
            print(f"      Count: {stats['count']}")
            print(f"      Win Rate: {stats['win_rate']}% ({stats['wins']}W/{stats['losses']}L)")
        
        print(f"\n🏆 TOP 5 ASSETS:")
        for asset, count in b['top_5_assets']:
            print(f"   {asset}: {count} signals")
        
        # Recommendations
        recommendations = analysis['recommendations']
        
        if recommendations:
            print(f"\n💡 RECOMMENDATIONS ({len(recommendations)}):")
            for i, rec in enumerate(recommendations, 1):
                priority_emoji = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🟢',
                    'INFO': 'ℹ️'
                }.get(rec['priority'], '•')
                
                print(f"\n   {i}. {priority_emoji} [{rec['priority']}] {rec['category']}")
                print(f"      Issue: {rec['issue']}")
                print(f"      Action: {rec['action']}")
                print(f"      Target: {rec['target']}")
        else:
            print(f"\n✅ No recommendations - performance looks good!")
        
        print("\n" + "=" * 80)
        print(f"Analysis generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80 + "\n")
    
    def export_analysis_json(self, hours=24, output_file='signal_analysis.json'):
        """Export analysis to JSON file"""
        analysis = self.analyze_recent_signals(hours)
        
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"✅ Analysis exported to: {output_file}")
        return output_file


def main():
    """Run signal analysis"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze trading signal performance')
    parser.add_argument('--hours', type=int, default=24, help='Hours to analyze (default: 24)')
    parser.add_argument('--export', action='store_true', help='Export to JSON file')
    parser.add_argument('--output', type=str, default='signal_analysis.json', help='Output file for JSON export')
    
    args = parser.parse_args()
    
    analyzer = SignalAnalyzer()
    
    # Print analysis
    analyzer.print_analysis(hours=args.hours)
    
    # Export if requested
    if args.export:
        analyzer.export_analysis_json(hours=args.hours, output_file=args.output)


if __name__ == "__main__":
    main()
