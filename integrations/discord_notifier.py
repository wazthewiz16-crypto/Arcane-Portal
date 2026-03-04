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
