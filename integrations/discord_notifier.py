"""Discord webhook integration for trading signal alerts"""
import requests
import logging
from datetime import datetime
from typing import Dict, Optional
from config import settings

logger = logging.getLogger(__name__)


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
            # Format the alert message
            message = self._format_signal_alert(signal)
            
            # Create Discord embed
            embed = self._create_embed(signal, message)
            
            # Send to Discord
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
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
        lines = [
            f"{emoji} {signal_type} - {signal['asset_name']}",
            "━━━━━━━━━━━━━━━━━━",
            f"📊 Timeframes: {signal['htf']} → {signal['ltf']}",
            f"💰 Entry Price: ${signal['entry_price']:.{decimals}f}",
            f"🎯 Take Profit: ${signal['take_profit']:.{decimals}f}",
            f"🛡️ Stop Loss: ${signal['stop_loss']:.{decimals}f}",
            f"📈 RR: {signal['rr_ratio']:.1f}:1",
            f"🎲 Confidence: {signal['confidence']:.0f}%",
            f"⏰ Entry Time: {entry_time}"
        ]
        
        return "\n".join(lines)
    
    def _create_embed(self, signal: Dict, message: str) -> Dict:
        """
        Create Discord embed with color coding
        
        Args:
            signal: Signal data
            message: Formatted message
            
        Returns:
            Discord embed dictionary
        """
        # Color coding
        if 'LONG' in signal['signal_type']:
            color = 0x00FF00  # Green for longs
        else:
            color = 0xFF0000  # Red for shorts
        
        # Determine title
        if 'SWING' in signal['signal_type']:
            title = "🎯 Swing Trade Signal"
        else:
            title = "⚡ Scalp Trade Signal"
        
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "footer": {
                "text": "Arcane Portal V2 • Mango Dynamic Strategy"
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
