"""Discord webhook integration for trading signal alerts"""
import os
import requests
import logging
from datetime import datetime
from typing import Dict, Optional
from config import settings

logger = logging.getLogger(__name__)

# Mango-native signal TP/SL display labels (kept in sync with mango_native_signals.py defaults)
DEFAULT_TP_PCT_DISPLAY = os.getenv("MANGO_NATIVE_TP_PCT", "3.0")
DEFAULT_SL_PCT_DISPLAY = os.getenv("MANGO_NATIVE_SL_PCT", "1.5")


class DiscordNotifier:
    """Send trading signal alerts to Discord via webhook"""
    
    def __init__(self, webhook_url: str = None):
        """
        Initialize Discord notifier
        
        Args:
            webhook_url: Discord webhook URL (defaults to settings)
        """
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL
        
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
    
    def send_signal_alert(self, signal: Dict) -> bool:
        """
        Send a trading signal alert to Discord
        
        Args:
            signal: Signal dictionary with all required fields
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.error("Cannot send alert: Discord webhook URL not configured")
            return False
        
        try:
            # Branch: Mango-native signals have their own formatter
            if signal.get('is_mango_native'):
                message = self._format_mango_native_alert(signal)
            else:
                message = self._format_signal_alert(signal)
            
            # Create Discord embed for the signal text + LTF chart
            embed = self._create_embed(signal, message)
            
            # Prepare request payload
            import os, json
            files = {}
            file_handles = []
            embeds = []
            
            # Check for HTF screenshot (shown first for context)
            htf_image_path = signal.get('htf_image_path')
            if htf_image_path and os.path.exists(htf_image_path):
                htf_filename = os.path.basename(htf_image_path)
                try:
                    fh = open(htf_image_path, "rb")
                    file_handles.append(fh)
                    files["file1"] = (htf_filename, fh)
                    htf_tf = signal.get('htf', 'HTF')
                    htf_embed = {
                        "title": f"HTF Chart ({htf_tf})",
                        "image": {"url": f"attachment://{htf_filename}"},
                        "color": 0x2ECC71 if 'LONG' in signal.get('signal_type', '') else 0xE74C3C
                    }
                    embeds.append(htf_embed)
                except Exception as e:
                    logger.error(f"Failed to attach HTF image: {e}")
            
            # Check for LTF screenshot (entry chart)
            image_path = signal.get('image_path')
            if image_path and os.path.exists(image_path):
                ltf_filename = os.path.basename(image_path)
                try:
                    fh = open(image_path, "rb")
                    file_handles.append(fh)
                    # Use file2 if HTF exists, else file
                    file_key = "file2" if "file1" in files else "file"
                    files[file_key] = (ltf_filename, fh)
                    embed["image"] = {"url": f"attachment://{ltf_filename}"}
                except Exception as e:
                    logger.error(f"Failed to attach LTF image: {e}")

            # Signal text embed goes after HTF chart
            embeds.append(embed)
            payload = {"embeds": embeds}
            
            # Send to Discord (using multipart if files exist)
            if files:
                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(payload)},
                    files=files,
                    timeout=30  # Longer timeout for dual image upload
                )
            else:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
            
            # Close all file handles
            for fh in file_handles:
                try: fh.close()
                except: pass
            
            if response.status_code in [200, 204]:
                logger.info(f"Discord alert sent: {signal['asset_name']} {signal['signal_type']}")
                return True
            else:
                logger.error(f"Discord alert failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Discord alert timeout")
            return False
        except Exception as e:
            logger.error(f"Discord alert error: {e}")
            return False
    
    def _format_signal_alert(self, signal: Dict) -> str:
        """
        Format signal as Discord message
        
        Format:
        🚨 SWING LONG - BTC
        ━━━━━━━━━━━━━━━━━━
        📊 Timeframes: 4h → 1h
        💰 Entry Price: $42,250
        🎯 Take Profit: $44,500
        🛡️ Stop Loss: $41,100
        📈 RR: 2.5:1
        🎲 Confidence: 85%
        ⏰ Entry Time: 2026-02-10 09:35 AM EST
        """
        # Determine emoji based on signal type
        if 'LONG' in signal['signal_type']:
            emoji = "🚨"  # Alert for longs
        else:
            emoji = "⚠️"  # Warning for shorts
        
        # Format signal type (remove underscores)
        signal_type = signal['signal_type'].replace('_', ' ')
        
        # Format entry time
        entry_time = self._format_datetime(signal['entry_time'])
        
        # Determine decimal precision based on price
        entry_price = signal['entry_price']
        if entry_price < 1:
            decimals = 4  # Low price assets (ADA, etc.)
        elif entry_price < 100:
            decimals = 3  # Medium price assets (LINK, etc.)
        else:
            decimals = 2  # High price assets (BTC, ETH, etc.)
        
        # Build message
        entry_price = signal['entry_price']
        partial_tp  = signal.get('partial_tp')
        take_profit = signal['take_profit']
        stop_loss   = signal['stop_loss']

        # Format partial_tp line (show distance from entry as a %)
        if partial_tp:
            dist_pct = abs(partial_tp - entry_price) / entry_price * 100
            partial_tp_line = f"⚡ Partial TP (+1R): ${partial_tp:.{decimals}f}  (+{dist_pct:.2f}% → SL moves to breakeven)"
        else:
            partial_tp_line = None

        lines = [
            f"{emoji} {signal_type} - {signal['asset_name']}",
            "━━━━━━━━━━━━━━━━━━",
            f"📊 Timeframes: {signal['htf']} → {signal['ltf']}",
            f"💰 Entry Price: ${entry_price:.{decimals}f}",
            f"🎯 Take Profit: ${take_profit:.{decimals}f}",
        ]
        if partial_tp_line:
            lines.append(partial_tp_line)
        lines += [
            f"🛡️ Stop Loss: ${stop_loss:.{decimals}f}",
            f"📈 RR: {signal['rr_ratio']:.1f}:1",
            f"🎲 Confidence: {signal['confidence']:.0f}%",
            f"⏰ Entry Time: {entry_time}"
        ]
        
        # Add Mango Research Premium Confluence if available
        confluence = signal.get('mango_confluence')
        if confluence:
            vol_gauge = confluence.get('volatility')
            vol_str = f"⚡ {vol_gauge}/100" if isinstance(vol_gauge, int) else f"⚡ {vol_gauge}"
            
            lines += [
                "━━━━━━━━━━━━━━━━━━",
                "🥭 **Mango Research Premium Confluence:**",
                f"   • Asset Trend Badge: {confluence.get('trend_badge')}",
                f"   • Asset Volatility: {vol_str}",
                f"   • Overall Market Trend: {confluence.get('market_trend', '🟣 NEUTRAL')}",
                f"   • Overall Market Vol: ⚡ {confluence.get('market_volatility', 50)}/100"
            ]
            flags = confluence.get('flags')
            if flags:
                formatted_flags = []
                bullish_flags = ["Golden Cross", "Bullish Ichimoku", "RSI Bullish Divergence", "Cheap / Discount", "Mango Hotlist"]
                bearish_flags = ["Death Cross", "Bearish Ichimoku", "RSI Bearish Divergence", "Expensive / Premium"]
                for f in flags:
                    if f in bullish_flags:
                        formatted_flags.append(f"🟢 {f}")
                    elif f in bearish_flags:
                        formatted_flags.append(f"🔴 {f}")
                    elif f.startswith("⚠️"):
                        formatted_flags.append(f)
                    else:
                        formatted_flags.append(f"⚪ {f}")
                lines.append(f"   • Technical Flags: {', '.join(formatted_flags)}")
            # MTF preset filter status
            mtf_b = confluence.get('mtf_bullish', False)
            mtf_be = confluence.get('mtf_bearish', False)
            sig_dir = 'LONG' if 'LONG' in signal.get('signal_type', '') else 'SHORT'
            if mtf_b and sig_dir == 'LONG':
                lines.append("   • MTF Preset: ✅ Mango Bullish Confirmed")
            elif mtf_be and sig_dir == 'SHORT':
                lines.append("   • MTF Preset: ✅ Mango Bearish Confirmed")
            elif mtf_b or mtf_be:
                lines.append(f"   • MTF Preset: ⚠️ {'Mango Bullish' if mtf_b else 'Mango Bearish'} (opposite direction)")
                
        return "\n".join(lines)

    def _format_mango_native_alert(self, signal: Dict) -> str:
        """
        Format a Mango Dashboard-native signal alert.
        Distinct layout with badge flip indicator and timeframe alignment grid.
        """
        direction    = "LONG" if "LONG" in signal["signal_type"] else "SHORT"
        emoji_dir    = "🚀" if direction == "LONG" else "📉"
        entry_price  = signal["entry_price"]
        take_profit  = signal["take_profit"]
        stop_loss    = signal["stop_loss"]
        rr_ratio     = signal["rr_ratio"]
        confidence   = signal["confidence"]
        prev_trend   = signal.get("badge_flip_from", "UNKNOWN")
        volatility   = signal.get("volatility", "N/A")
        flags        = signal.get("flags", [])
        timeframes   = signal.get("timeframes", {})
        mkt_trend    = signal.get("market_trend", "🟣 NEUTRAL")
        mkt_vol      = signal.get("market_volatility", 50)
        entry_time   = self._format_datetime(signal["entry_time"])
        mtf_bullish  = signal.get("mtf_bullish", False)
        mtf_bearish  = signal.get("mtf_bearish", False)

        # Decimal precision
        if entry_price < 1:
            dec = 6
        elif entry_price < 100:
            dec = 3
        else:
            dec = 2

        # Badge flip display
        trend_icons = {"LONG": "🟢 LONG", "SHORT": "🔴 SHORT", "NEUTRAL": "🟣 NEUTRAL", "UNKNOWN": "❔"}
        prev_icon    = trend_icons.get(prev_trend, "❔")
        current_icon = trend_icons.get(direction, direction)

        # Timeframe grid
        tf_order = ["15M", "1H", "2H", "4H", "8H", "12H", "1D", "2D", "3D", "4D", "1W"]
        tf_lines = []
        if timeframes:
            agree = sum(1 for v in timeframes.values() if v == direction)
            total = len(timeframes)
            tf_lines.append(f"📊 Timeframe Alignment ({agree}/{total} agree):")
            # Sort by canonical order
            sorted_tfs = sorted(timeframes.items(),
                                key=lambda x: tf_order.index(x[0]) if x[0] in tf_order else 99)
            for tf_label, tf_trend in sorted_tfs:
                icon = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "🟣"}.get(tf_trend, "❔")
                agree_mark = "✓" if tf_trend == direction else " "
                tf_lines.append(f"   {agree_mark} {tf_label:<4} → {icon} {tf_trend}")
        else:
            tf_lines.append("📊 Timeframe Alignment: (badge flip only — detail page pending)")

        # MTF preset status line
        if mtf_bullish and direction == "LONG":
            mtf_line = "🥭 MTF Preset: ✅ **Mango Bullish Confirmed** (Golden Cross + Long HTF)"
        elif mtf_bearish and direction == "SHORT":
            mtf_line = "🥭 MTF Preset: ✅ **Mango Bearish Confirmed** (Death Cross + Short HTF)"
        elif mtf_bullish or mtf_bearish:
            preset_name = "Mango Bullish" if mtf_bullish else "Mango Bearish"
            mtf_line = f"🥭 MTF Preset: ⚠️ {preset_name} active (opposite direction)"
        else:
            mtf_line = "🥭 MTF Preset: ➖ No preset match yet"

        lines = [
            f"{emoji_dir} **MANGO SIGNAL — {direction} — {signal['asset_name']}**",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📡 Badge Flip: {prev_icon} → {current_icon}",
            f"📊 Timeframe: {signal.get('timeframe', '4H')}",
            mtf_line,
        ] + tf_lines + [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"💰 Entry: ${entry_price:.{dec}f}",
            f"🎯 Take Profit: ${take_profit:.{dec}f}  (+{signal.get('tp_pct', DEFAULT_TP_PCT_DISPLAY)}%)",
            f"🛡️ Stop Loss: ${stop_loss:.{dec}f}  (-{signal.get('sl_pct', DEFAULT_SL_PCT_DISPLAY)}%)",
            f"📈 RR: {rr_ratio:.1f}:1",
            f"🎲 Alignment Confidence: {confidence:.0f}%",
            f"⚡ Asset Volatility: {volatility}/100",
            f"🌍 Market Regime: {mkt_trend} (Vol: {mkt_vol}/100)",
            f"⏰ Signal Time: {entry_time}",
        ]

        if flags:
            formatted_flags = []
            bullish_flags = ["Golden Cross", "Bullish Ichimoku", "RSI Bullish Divergence", "Cheap / Discount", "Mango Hotlist"]
            bearish_flags = ["Death Cross", "Bearish Ichimoku", "RSI Bearish Divergence", "Expensive / Premium"]
            for f in flags:
                if f in bullish_flags:
                    formatted_flags.append(f"🟢 {f}")
                elif f in bearish_flags:
                    formatted_flags.append(f"🔴 {f}")
                elif f.startswith("⚠️"):
                    formatted_flags.append(f)
                else:
                    formatted_flags.append(f"⚪ {f}")
            lines.append(f"📌 Technical Flags: {', '.join(formatted_flags)}")

        return "\n".join(lines)
    
    def _create_embed(self, signal: Dict, message: str) -> Dict:
        """
        Create Discord embed with color coding and tier indicators
        
        Args:
            signal: Signal data
            message: Formatted message
            
        Returns:
            Discord embed dictionary
        """
        tier = signal.get('tier', 'B')
        is_long = 'LONG' in signal.get('signal_type', '')
        
        # Color coding based on tier and direction
        if tier == 'A+':
            color = 0xF1C40F  # Gold/Amber for Tier A+ (Ultra)
        elif tier == 'A':
            color = 0x2ECC71 if is_long else 0xE74C3C  # Emerald Green / Alizarin Red (Premium)
        else:
            color = 0x3498DB if is_long else 0x95A5A6  # Muted Blue / Slate Grey (Standard)
            
        # Determine title
        if tier == 'A+':
            title = "🏆 TIER A+ ULTRA SETUP 🏆"
        elif tier == 'A':
            title = "🟢 TIER A HIGH CONVICTION" if is_long else "🔴 TIER A HIGH CONVICTION"
        else:
            title = "⚡ Standard Scalp Signal" if 'SCALP' in signal.get('signal_type', '') else "🎯 Standard Swing Signal"
            
        if signal.get('is_mango_native'):
            title = f"🥭 {title} (Native Flip)"
            
        # Prepend Tier Header to description text for prominent visual distinction
        tier_badges = {
            'A+': "🏆 **TIER A+ ULTRA SETUP** 🏆\n*Perfect conditions: Low Volatility + Multi-Timeframe Alignment + Multiple Confirming Flags + Trending ML Regime*",
            'A': "🟢 **TIER A HIGH CONVICTION SETUP**\n*Strong conditions: Healthy Volatility + Confirming Indicators*",
            'B': "⚡ **TIER B STANDARD SETUP**\n*Standard confluence rules satisfied*"
        }
        
        desc = f"{tier_badges.get(tier, '')}\n\n{message}"
        
        embed = {
            "title": title,
            "description": desc,
            "color": color,
            "footer": {
                "text": f"Arcane Portal V2 • Tier {tier} Setup"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed
    
    def _format_datetime(self, iso_string: str) -> str:
        """
        Format ISO datetime string for display in EST
        
        Args:
            iso_string: ISO format datetime string
            
        Returns:
            Formatted string like "2026-02-10 09:35 AM EST"
        """
        try:
            import pytz
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            est = pytz.timezone('America/New_York')
            dt_est = dt.astimezone(est)
            return dt_est.strftime("%Y-%m-%d %I:%M %p EST")
        except Exception:
            return iso_string
    
    def send_message(self, message: str) -> bool:
        """
        Send a general message to Discord
        
        Args:
            message: Formatted text message
            
        Returns:
            True if sent successfully
        """
        if not self.webhook_url:
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json={"content": message},
                timeout=10
            )
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def send_message_with_file(self, message: str, filepath: str) -> bool:
        """
        Send a general message with a file attachment to Discord
        
        Args:
            message: Formatted text message
            filepath: Absolute path to the file to attach
            
        Returns:
            True if sent successfully
        """
        if not self.webhook_url:
            return False
            
        if not filepath or not os.path.exists(filepath):
            logger.warning(f"File path {filepath} does not exist. Falling back to text-only send_message.")
            return self.send_message(message)
            
        try:
            import json
            filename = os.path.basename(filepath)
            with open(filepath, "rb") as fh:
                payload = {"content": message}
                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(payload)},
                    files={"file": (filename, fh)},
                    timeout=30
                )
                
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Failed to send message with file: {e}")
            return False

    def send_test_alert(self) -> bool:
        """Send a test alert to verify webhook is working"""
        test_signal = {
            'asset_name': 'BTC',
            'asset_type': 'crypto',
            'signal_type': 'SWING_LONG',
            'confidence': 85.0,
            'entry_price': 42250.0,
            'take_profit': 44500.0,
            'stop_loss': 41100.0,
            'rr_ratio': 2.5,
            'htf': '4h',
            'ltf': '1h',
            'entry_time': datetime.utcnow().isoformat()
        }
        
        return self.send_signal_alert(test_signal)
    
    def send_error_alert(self, error_message: str) -> bool:
        """
        Send critical error alert to Discord
        
        Args:
            error_message: Error description
            
        Returns:
            True if sent successfully
        """
        if not self.webhook_url:
            return False
        
        try:
            embed = {
                "title": "⚠️ Arcane Portal Error",
                "description": f"```\n{error_message}\n```",
                "color": 0xFF0000,  # Red
                "timestamp": datetime.utcnow().isoformat()
            }
            
            payload = {"embeds": [embed]}
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")
            return False

    def send_ml_retrain_alert(self, metrics: dict) -> bool:
        """Send a weekly ML retrain summary"""
        if not self.webhook_url:
            return False
            
        try:
            total = metrics.get('total_samples', 0)
            acc = metrics.get('accuracy', 0.0)
            
            # Formatting feature importances
            imp = metrics.get('importances', {})
            imp_lines = [f"• **{k}**: {v:.1%}" for k, v in list(imp.items())[:3]]
            imp_str = "\n".join(imp_lines) if imp_lines else "N/A"
            
            desc = (
                f"The weekly automated ML retraining process has completed successfully.\n\n"
                f"**Training Data:** {total} 4H samples\n"
                f"**Walk-Forward Accuracy:** {acc:.1%}\n"
            )
            
            # Label sources breakdown
            label_sources = metrics.get('label_sources')
            if label_sources:
                sources_str = ", ".join([f"{str(k).capitalize()}: {v}" for k, v in label_sources.items()])
                desc += f"**Label Sources:** {sources_str}\n"
                
            # Best hyperparams
            best_params = metrics.get('best_params')
            if best_params:
                params_str = ", ".join([f"{k}={v}" for k, v in best_params.items()])
                desc += f"**Optimized Hyperparameters:** `{params_str}`\n"
                
            desc += f"\n**Top Predictive Features:**\n{imp_str}"
            
            embed = {
                "title": "🧠 ML Regime Model Retrained",
                "description": desc,
                "color": 0x9B59B6,  # Purple
                "footer": {
                    "text": "Arcane Auto-Optimizer • Machine Learning"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Failed to send ML retrain alert: {e}")
            return False

    def send_daily_regime_alert(self, results: dict) -> bool:
        """Send a daily crypto regime prediction or verification summary"""
        if not self.webhook_url:
            return False
            
        try:
            decision = results.get('decision', 'TRENDING')
            time_of_day = results.get('time_of_day', 'Morning Check')
            regime = results.get('regime', 'TRENDING')
            confidence = results.get('confidence', 50.0)
            reason = results.get('reason', '')
            date_str = results.get('date', '')
            
            # Select color based on decision
            if decision == 'TRENDING':
                color = 0x2ECC71  # Green
                status_text = "🟢 TRENDING (Swings & Scalps Enabled)"
            elif decision == 'RANGING_SCALPS_ONLY':
                color = 0xF1C40F  # Yellow
                status_text = "🟡 RANGING (Quick Scalps Only)"
            else:
                color = 0xE74C3C  # Red
                status_text = "🔴 RANGING (All Trading Halted)"
                
            desc = (
                f"**Daily Check Stage:** `{time_of_day}`\n"
                f"**Detected Market State:** `{regime}` (Confidence: {confidence:.0f}%)\n"
                f"**System Target Action:** **{status_text}**\n\n"
                f"**Rationale:**\n{reason}\n"
            )
            
            # Formulate metrics table
            metrics = results.get('metrics', {})
            if metrics:
                desc += "\n**📊 Underlying Micro Metrics:**\n"
                desc += f"• Zone Escape Ratio: `{metrics.get('zone_escape_ratio', 0.0):.0%}`\n"
                desc += f"• Directional Alignment: `{metrics.get('direction_alignment', 0.0):.0%}`\n"
                desc += f"• Range Expansion: `{metrics.get('range_expansion', 1.0):.2f}x`\n"
                desc += f"• Equilibrium Expansion: `{metrics.get('eq_expansion_ratio', 0.5):.0%}`\n"
            
            # Mango Dashboard metrics
            desc += "\n**🥭 Mango Dashboard Indicators:**\n"
            trend_val = metrics.get('mango_market_trend', 0)
            trend_str = "LONG" if trend_val == 1 else ("SHORT" if trend_val == -1 else "NEUTRAL")
            desc += f"• Global Market Trend: `{trend_str}`\n"
            desc += f"• Global Market Volatility: `{results.get('btc_vol', 50.0):.0f}`\n"
            desc += f"• Active Badge Ratio: `{metrics.get('mango_badge_trend_ratio', 0.5):.0%}`\n"
            desc += f"• Watchlist Avg Volatility: `{metrics.get('mango_avg_asset_volatility', 50.0):.0f}`\n"
            
            if results.get('avg_daily_range') is not None:
                desc += f"\n**📈 Actual Intraday Return Range (Watchlist Average):** `{results['avg_daily_range']:.2%}`\n"
                
            if results.get('bbwp_squeeze'):
                desc += "\n**⚠️ VOLATILITY SQUEEZE WARNING:**\n" \
                        "• Bitcoin BBWP indicates extreme compression (< 25). A massive volatility breakout is imminent. Watch for trending breakout opportunities.\n"
                        
            if results.get('cb_active'):
                desc += "\n**🛡️ DRAWDOWN SAFEGUARD:**\n" \
                        "• Drawdown circuit breaker is active. System is operating in low-risk mode.\n"
            
            embed = {
                "title": f"🧠 Daily Crypto Regime Check — {date_str}",
                "description": desc,
                "color": color,
                "footer": {
                    "text": "Arcane Portal V2 • Daily Prediction Engine"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Failed to send daily regime alert: {e}")
            return False

def send_signal_to_discord(signal: Dict) -> bool:
    """
    Convenience function to send a signal alert
    
    Args:
        signal: Signal dictionary
        
    Returns:
        True if sent successfully
    """
    notifier = DiscordNotifier()
    return notifier.send_signal_alert(signal)
