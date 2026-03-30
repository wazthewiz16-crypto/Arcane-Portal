"""Trade Radar - Pushes prime active trades to Discord."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from integrations.discord_notifier import DiscordNotifier

def run_trade_radar():
    print("\n" + "=" * 50)
    print("ARCANE TRADE RADAR")
    print("=" * 50)
    
    datastore = MangoDataStore()
    notifier = DiscordNotifier()
    
    active_signals = datastore.get_active_signals()
    if not active_signals:
        print("No active signals to process. Skipping.")
        return
        
    latest_scrapes = datastore.get_latest_for_all_assets()
    current_prices = {}
    for scrape in latest_scrapes:
        current_prices[scrape['name'].strip().upper()] = float(scrape['close'])
        
    # Evaluate signals
    evaluated = []
    for sig in active_signals:
        asset_key = sig['asset_name'].strip().upper()
        cur_price = current_prices.get(asset_key)
        
        if not cur_price or not sig.get('entry_price'):
            continue
            
        try:
            entry_p = float(sig['entry_price'])
            if 'LONG' in sig['signal_type']:
                pnl_pct = (cur_price - entry_p) / entry_p * 100
                distance_to_sl = (cur_price - float(sig['stop_loss'])) / cur_price * 100
            else:
                pnl_pct = (entry_p - cur_price) / entry_p * 100
                distance_to_sl = (float(sig['stop_loss']) - cur_price) / cur_price * 100
                
            conf = float(sig.get('confidence', 0))
            evaluated.append({
                'signal': sig,
                'pnl_pct': pnl_pct,
                'conf': conf,
                'distance_to_sl': distance_to_sl
            })
        except Exception as e:
            print(f"Error evaluating {asset_key}: {e}")
            continue

    if not evaluated:
        print("Could not evaluate PnL for active signals.")
        return

    # Filter out trades that are too close to SL (< 0.5% away) or already massively in profit (> 2.5%)
    # We want "Prime" trades: slightly negative (up to -2%) to slightly positive (up to +1.5%)
    prime_trades = []
    for t in evaluated:
        p = t['pnl_pct']
        if -2.0 <= p <= +1.5 and t['distance_to_sl'] > 0.3:
            prime_trades.append(t)
            
    # Sort by a combination of factors: 
    # slightly negative PnL (better reward-to-risk) and high confidence
    # We'll rank them mostly by confidence, prioritizing those that haven't pumped yet (-1% to 0.5% PnL)
    def rank_score(trade):
        pnl = trade['pnl_pct']
        conf = trade['conf']
        # Bonus points if it's currently at a favorable entry (pullback)
        pnl_bonus = 5 if -1.5 <= pnl <= 0.2 else 0
        return conf + pnl_bonus

    prime_trades.sort(key=rank_score, reverse=True)
    top_trades = prime_trades[:5]

    if not top_trades:
        print("No prime trades meet the radar criteria right now.")
        return

    # Build the Discord message
    msg = "**📡 ARCANE TRADE RADAR (Prime Entries)**\n"
    msg += "*Top high-probability setups currently near entry zones:*\n\n"
    
    for t in top_trades:
        sig = t['signal']
        direction = "🟢 LONG" if "LONG" in sig['signal_type'] else "🔴 SHORT"
        trade_type = "Swing" if "SWING" in sig['signal_type'] else "Scalp"
        pnl = t['pnl_pct']
        
        # Format PnL status
        if pnl < -0.5:
            status = f"Ideal Pullback (`{pnl:.2f}%`)"
        elif -0.5 <= pnl <= +0.5:
            sign = "+" if pnl > 0 else ""
            status = f"At exact entry (`{sign}{pnl:.2f}%`)"
        else:
            status = f"Early Profit (`+{pnl:.2f}%`)"
            
        msg += f"**{sig['asset_name']}** {trade_type} ({sig['htf']}→{sig['ltf']})\n"
        msg += f"↳ Action: {direction} @ {sig['entry_price']}\n"
        msg += f"↳ Status: **{status}** | Conf: `{t['conf']:.1f}%`\n\n"
        
    msg += "*Not financial advice. Manage your risk.*\n"
    
    # Send
    print(f"Sending {len(top_trades)} prime trades to Radar Discord channel...")
    notifier.send_message(msg)
    
if __name__ == "__main__":
    run_trade_radar()
