"""Trade Radar - Pushes prime active trades to Discord."""
import sys
import os
import io

# Force UTF-8 encoding for standard output and error to avoid UnicodeEncodeErrors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

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
        
        if not cur_price or not sig.get('entry_price') or not sig.get('stop_loss') or not sig.get('take_profit'):
            continue
            
        try:
            entry_p = float(sig['entry_price'])
            stop_l = float(sig['stop_loss'])
            take_p = float(sig['take_profit'])
            
            if entry_p <= 0 or cur_price <= 0:
                continue
                
            # Evaluate distance to stop loss (as a %)
            if 'LONG' in sig['signal_type']:
                pnl_pct = (cur_price - entry_p) / entry_p * 100
                distance_to_sl = (cur_price - stop_l) / cur_price * 100
                
                # Enhanced R:R calculation
                risk_denom = cur_price - stop_l
                reward_num = take_p - cur_price
            else:
                pnl_pct = (entry_p - cur_price) / entry_p * 100
                distance_to_sl = (stop_l - cur_price) / cur_price * 100
                
                # Enhanced R:R calculation
                risk_denom = stop_l - cur_price
                reward_num = cur_price - take_p
                
            # Original R:R
            original_risk = abs(entry_p - stop_l)
            original_reward = abs(take_p - entry_p)
            original_rr = original_reward / original_risk if original_risk > 0 else float(sig.get('rr_ratio', 0.0))
            
            # Enhanced R:R
            enhanced_rr = reward_num / risk_denom if risk_denom > 0 else 0.0
            
            # R-Multiple Drift (Swap raw percentage distance for R-multiple distance)
            risk_pct = original_risk / entry_p
            r_drift = pnl_pct / (risk_pct * 100) if risk_pct > 0 else 0.0
            
            conf = float(sig.get('confidence', 0))
            evaluated.append({
                'signal': sig,
                'pnl_pct': pnl_pct,
                'r_drift': r_drift,
                'original_rr': original_rr,
                'enhanced_rr': enhanced_rr,
                'conf': conf,
                'distance_to_sl': distance_to_sl
            })
        except Exception as e:
            print(f"Error evaluating {asset_key}: {e}")
            continue

    if not evaluated:
        print("Could not evaluate PnL for active signals.")
        return False

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
    
    is_fallback = False
    if prime_trades:
        top_trades = prime_trades[:5]
        # Build the Discord message for prime entries
        msg = "**📡 ARCANE TRADE RADAR (Prime Entries)**\n"
        msg += "*Top high-probability setups currently near entry zones:*\n\n"
    else:
        is_fallback = True
        # Sort all evaluated active trades by confidence/PnL
        evaluated.sort(key=lambda x: x['conf'], reverse=True)
        top_trades = evaluated[:5]
        # Build the Discord message for active trade status
        msg = "**📡 ARCANE TRADE RADAR (Active Trade Status)**\n"
        msg += "*No new setups are currently in prime entry zones. Current active setups are running in profit/loss:*\n\n"

    if not top_trades:
        print("No active trades to process.")
        return False

    for t in top_trades:
        sig = t['signal']
        direction = "🟢 LONG" if "LONG" in sig['signal_type'] else "🔴 SHORT"
        trade_type = "Swing" if "SWING" in sig['signal_type'] else "Scalp"
        r_drift = t['r_drift']
        
        # Format PnL status using R-multiple
        if r_drift < -0.15:
            status = f"Ideal Pullback (`{r_drift:.2f}R`)"
        elif -0.15 <= r_drift <= +0.15:
            sign = "+" if r_drift > 0 else ""
            status = f"At exact entry (`{sign}{r_drift:.2f}R`)"
        else:
            status = f"Running Profit (`+{r_drift:.2f}R`)"
            
        tier = sig.get('tier', 'N/A')
        if not tier:
            tier = 'N/A'
            
        tier_badges = {
            'A+': '🏆 **A+**',
            'A': '🟢 **A**',
            'B': '⚡ **B**',
            'N/A': '❔ **N/A**'
        }
        tier_display = tier_badges.get(tier, f'**{tier}**')
            
        msg += f"**{sig['asset_name']}** {trade_type} ({sig['htf']}→{sig['ltf']})\n"
        msg += f"↳ Action: {direction} @ {sig['entry_price']}\n"
        msg += f"↳ Status: **{status}** | Conf: `{t['conf']:.1f}%` | Tier: {tier_display}\n"
        msg += f"↳ R:R Ratio: `{t['original_rr']:.1f}:1` ➔ **Enhanced R:R: `{t['enhanced_rr']:.1f}:1`**\n\n"
        
    msg += "*Not financial advice. Manage your risk.*\n"
    
    # 1. Visual Chart Attachments: Automatically fetch the latest saved chart screenshot
    # from the database for the #1 ranked prime trade setup and attach it to the Discord alert
    screenshot_file = None
    if top_trades:
        top_sig = top_trades[0]['signal']
        asset_name = top_sig['asset_name']
        ltf = top_sig.get('ltf')
        htf = top_sig.get('htf')
        
        screenshot_data = None
        # Try LTF first
        if ltf:
            screenshot_data = datastore.get_screenshot(asset_name, ltf)
            if not screenshot_data and asset_name != asset_name.strip().upper():
                screenshot_data = datastore.get_screenshot(asset_name.strip().upper(), ltf)
                
        # Fallback to HTF
        if not screenshot_data and htf:
            screenshot_data = datastore.get_screenshot(asset_name, htf)
            if not screenshot_data and asset_name != asset_name.strip().upper():
                screenshot_data = datastore.get_screenshot(asset_name.strip().upper(), htf)
                
        if screenshot_data and screenshot_data.get('image_data'):
            try:
                temp_filename = f"temp_radar_{asset_name}_{ltf or htf}.png".replace("/", "_")
                temp_path = os.path.join(str(Path(__file__).parent), temp_filename)
                with open(temp_path, "wb") as f:
                    f.write(screenshot_data['image_data'])
                screenshot_file = temp_path
                print(f"Retrieved and saved screenshot for {asset_name} ({ltf or htf}) to {temp_path}")
            except Exception as e:
                print(f"Error saving temporary screenshot file: {e}")

    did_send = False
    try:
        # Send
        print(f"Sending {len(top_trades)} prime trades to Radar Discord channel...")
        if screenshot_file:
            did_send = notifier.send_message_with_file(msg, screenshot_file)
        else:
            did_send = notifier.send_message(msg)
        return did_send
    finally:
        # Clean up temporary screenshot file
        if screenshot_file and os.path.exists(screenshot_file):
            try:
                os.remove(screenshot_file)
                print(f"Cleaned up temporary screenshot file: {screenshot_file}")
            except Exception as e:
                print(f"Error removing temporary file {screenshot_file}: {e}")
    
if __name__ == "__main__":
    try:
        run_trade_radar()
    except Exception as e:
        import traceback
        err_msg = f"❌ CRITICAL ERROR: TradeRadar failed with exception:\n{str(e)}\n\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        try:
            from integrations.discord_notifier import DiscordNotifier
            DiscordNotifier().send_error_alert(err_msg[:1900])
        except Exception as de:
            print(f"Failed to send Discord error alert: {de}", file=sys.stderr)
        sys.exit(1)
