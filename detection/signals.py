"""Enhanced Mango Dynamic signal detection with TP/SL calculation"""
import logging
import pytz
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Signal type enumeration"""
    SWING_LONG = "SWING_LONG"
    SWING_SHORT = "SWING_SHORT"
    SCALP_LONG = "SCALP_LONG"
    SCALP_SHORT = "SCALP_SHORT"


class MangoSignalDetector:
    """Detects trading signals from Mango Dynamic data with TP/SL calculation"""
    
    def __init__(self, datastore):
        self.datastore = datastore
        self.min_confidence_swing = settings.MIN_CONFIDENCE_SWING
        self.min_confidence_scalp = settings.MIN_CONFIDENCE_SCALP
    
    def get_all_signals(self) -> List[Dict]:
        """Analyze all assets and return signals above confidence threshold"""
        signals = []
        latest_data = self.datastore.get_latest_for_all_assets()
        
        # Group by asset name
        assets_data = {}
        for row in latest_data:
            name = row['name']
            if name not in assets_data:
                assets_data[name] = {}
            assets_data[name][row['timeframe']] = row
        
        # Analyze each asset - both swing and scalp signals
        for name, timeframes in assets_data.items():
            # Swing signals (HTF → LTF)
            swing_signal = self._detect_swing_signal(name, timeframes)
            if swing_signal and swing_signal['confidence'] >= self.min_confidence_swing:
                signals.append(swing_signal)
            
            # Scalp signals (scalp_htf → scalp_ltf)
            scalp_signal = self._detect_scalp_signal(name, timeframes)
            if scalp_signal and scalp_signal['confidence'] >= self.min_confidence_scalp:
                signals.append(scalp_signal)
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        return signals
    
    
    def _detect_swing_signal(self, name: str, timeframes: Dict) -> Optional[Dict]:
        """
        Detect swing signal (HTF-based position trade)
        
        Strategy:
        - HTF determines direction (bullish/bearish)
        - LTF determines entry (inside Mango Dynamic OR within bid zone)
        - Uses 4h → 1h or 1d → 4h combinations
        """
        # Try different HTF/LTF combinations for swing trading
        # Try different HTF/LTF combinations for swing trading
        combinations = [
            ('1d', '4h'),   # Daily/4H is the primary swing combination
        ]
        
        for htf_tf, ltf_tf in combinations:
            htf_data = timeframes.get(htf_tf)
            ltf_data = timeframes.get(ltf_tf)
            
            if not (htf_data and ltf_data):
                continue
            
            # Check HTF direction
            htf_direction = self._get_htf_direction(htf_data)
            if not htf_direction or htf_direction == 'NEUTRAL':
                continue  # Skip neutral trends (price inside Mango Dynamic)
            
            # Check LTF entry conditions
            ltf_entry = self._check_ltf_entry(ltf_data, htf_direction)
            if not ltf_entry['valid']:
                continue
            
            # Calculate confidence
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=True)
            
            # Determine signal type
            signal_type = SignalType.SWING_LONG if htf_direction == 'LONG' else SignalType.SWING_SHORT
            
            # Calculate TP/SL
            tp_sl = self._calculate_tp_sl(
                entry_price=ltf_data['close'],
                direction=htf_direction,
                entry_zone_low=ltf_data['entry_down'],
                entry_zone_high=ltf_data['entry_up'],
                timeframe=htf_data['timeframe']
            )
            
            if not tp_sl:
                continue
            
            return {
                'asset_name': name,
                'asset_type': self._get_asset_type(name),
                'signal_type': signal_type.value,
                'confidence': confidence,
                'entry_price': ltf_data['close'],
                'take_profit': tp_sl['take_profit'],
                'stop_loss': tp_sl['stop_loss'],
                'rr_ratio': tp_sl['rr_ratio'],
                'entry_zone_low': ltf_data['entry_down'],
                'entry_zone_high': ltf_data['entry_up'],
                'htf': htf_data['timeframe'],
                'ltf': ltf_data['timeframe'],
                'entry_time': datetime.now(pytz.timezone('America/New_York')).isoformat(),
                'status': 'ACTIVE'
            }
        
        return None
    
    def _detect_scalp_signal(self, name: str, timeframes: Dict) -> Optional[Dict]:
        """
        Detect scalp signal (LTF-based quick trade)
        
        Strategy:
        - Faster timeframe alignment
        - Higher confidence threshold required
        - Uses 1h → 15m or 4h → 1h combinations
        """
        # Try different HTF/LTF combinations for scalp trading
        combinations = [
            ('1h', '15m'),  # Primary scalp combination
            ('4h', '1h'),   # Alternative scalp combination
        ]
        
        for htf_tf, ltf_tf in combinations:
            htf_data = timeframes.get(htf_tf)
            ltf_data = timeframes.get(ltf_tf)
            
            if not (htf_data and ltf_data):
                continue
            
            # Same logic as swing but with tighter parameters
            htf_direction = self._get_htf_direction(htf_data)
            if not htf_direction or htf_direction == 'NEUTRAL':
                continue  # Skip neutral trends (price inside Mango Dynamic)
            
            ltf_entry = self._check_ltf_entry(ltf_data, htf_direction)
            if not ltf_entry['valid']:
                continue
            
            # Calculate confidence (stricter for scalps)
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=False)
            
            # Determine signal type
            signal_type = SignalType.SCALP_LONG if htf_direction == 'LONG' else SignalType.SCALP_SHORT
            
            # Calculate TP/SL (tighter for scalps)
            tp_sl = self._calculate_tp_sl(
                entry_price=ltf_data['close'],
                direction=htf_direction,
                entry_zone_low=ltf_data['entry_down'],
                entry_zone_high=ltf_data['entry_up'],
                timeframe=ltf_data['timeframe'],
                is_scalp=True
            )
            
            if not tp_sl:
                continue
            
            return {
                'asset_name': name,
                'asset_type': self._get_asset_type(name),
                'signal_type': signal_type.value,
                'confidence': confidence,
                'entry_price': ltf_data['close'],
                'take_profit': tp_sl['take_profit'],
                'stop_loss': tp_sl['stop_loss'],
                'rr_ratio': tp_sl['rr_ratio'],
                'entry_zone_low': ltf_data['entry_down'],
                'entry_zone_high': ltf_data['entry_up'],
                'htf': htf_data['timeframe'],
                'ltf': ltf_data['timeframe'],
                'entry_time': datetime.now(pytz.timezone('America/New_York')).isoformat(),
                'status': 'ACTIVE'
            }
        
        return None
    
    def _get_htf_direction(self, htf_data: Dict) -> Optional[str]:
        """
        Determine HTF trend direction
        
        Returns: 'LONG', 'SHORT', 'NEUTRAL', or None
        """
        price = htf_data.get('close')
        mango_d1 = htf_data.get('mango_d1')
        mango_d2 = htf_data.get('mango_d2')
        
        if not (price and mango_d1 and mango_d2):
            return None
        
        # Bullish: Price above Mango D2
        if price > mango_d2:
            return 'LONG'
        
        # Bearish: Price below Mango D1
        if price < mango_d1:
            return 'SHORT'
        
        # Neutral: Price between D1 and D2 (inside Mango Dynamic)
        if mango_d1 <= price <= mango_d2:
            return 'NEUTRAL'
        
        return None
    
    def _check_ltf_entry(self, ltf_data: Dict, direction: str) -> Dict:
        """
        Check if LTF shows valid entry
        
        Entry conditions:
        - Inside Mango Dynamic (between entry_down and entry_up)
        - OR within bid zone
        """
        price = ltf_data.get('close')
        entry_up = ltf_data.get('entry_up')
        entry_down = ltf_data.get('entry_down')
        
        if not (price and entry_up and entry_down):
            return {'valid': False, 'reason': 'Missing data'}
        
        # Check if price is in entry zone
        in_zone = entry_down <= price <= entry_up
        
        # Additional check: price should be near the zone boundary appropriate for direction
        if direction == 'LONG':
            # For longs, prefer entry near bottom of zone
            near_entry = abs(price - entry_down) / entry_down < 0.01  # Within 1%
        else:
            # For shorts, prefer entry near top of zone
            near_entry = abs(price - entry_up) / entry_up < 0.01
        
        valid = in_zone or near_entry
        
        return {
            'valid': valid,
            'in_zone': in_zone,
            'near_entry': near_entry,
            'reason': 'Valid entry' if valid else 'Not in entry zone'
        }
    
    def _calculate_confidence(self, htf_data: Dict, ltf_data: Dict, is_swing: bool) -> float:
        """
        Calculate signal confidence (0-100%)
        
        Factors:
        - HTF trend strength
        - LTF entry quality
        - Volume confirmation
        - Mango D1/D2 alignment
        """
        confidence = 50.0  # Base confidence
        
        # HTF trend strength (up to +20%)
        price = htf_data.get('close')
        mango_d2 = htf_data.get('mango_d2')
        if price and mango_d2:
            trend_strength = abs(price - mango_d2) / mango_d2
            confidence += min(trend_strength * 100, 20)
        
        # LTF entry quality (up to +15%)
        ltf_price = ltf_data.get('close')
        entry_down = ltf_data.get('entry_down')
        entry_up = ltf_data.get('entry_up')
        if ltf_price and entry_down and entry_up:
            zone_size = entry_up - entry_down
            if zone_size > 0:
                # Closer to ideal entry = higher confidence
                distance_from_ideal = min(
                    abs(ltf_price - entry_down),
                    abs(ltf_price - entry_up)
                )
                entry_quality = 1 - (distance_from_ideal / zone_size)
                confidence += entry_quality * 15
        
        # Mango D1/D2 alignment (up to +10%)
        mango_d1 = htf_data.get('mango_d1')
        if mango_d1 and mango_d2:
            if (price > mango_d1 and price > mango_d2) or (price < mango_d1 and price < mango_d2):
                confidence += 10
        
        # Swing trades get slight boost for longer timeframe
        if is_swing:
            confidence += 5
        
        # Cap at 100%
        return min(confidence, 100.0)
    
    def _calculate_tp_sl(
        self,
        entry_price: float,
        direction: str,
        entry_zone_low: float,
        entry_zone_high: float,
        timeframe: str,
        is_scalp: bool = False
    ) -> Optional[Dict]:
        """
        Calculate Take Profit and Stop Loss levels
        Returns None if trade is invalid (e.g. Price violates SL logic)
        """
        if direction == 'LONG':
            # Long trade: SL is bottom of zone
            stop_loss = entry_zone_low
            risk = entry_price - stop_loss
            
            # Invalid if Price <= SL (already stopped out)
            if risk <= 0:
                return None
            
            # TP based on RR ratio
            rr_ratio = 2.0 if is_scalp else 2.5
            take_profit = entry_price + (risk * rr_ratio)
            
        else:
            # Short trade: SL is top of zone
            stop_loss = entry_zone_high
            risk = stop_loss - entry_price
            
            # Invalid if Price >= SL (already stopped out)
            if risk <= 0:
                return None
            
            # TP based on RR ratio
            rr_ratio = 2.0 if is_scalp else 2.5
            take_profit = entry_price - (risk * rr_ratio)
        
        # Calculate actual RR ratio
        actual_rr = abs(take_profit - entry_price) / risk
        
        return {
            'take_profit': round(take_profit, 2),
            'stop_loss': round(stop_loss, 2),
            'rr_ratio': round(actual_rr, 1)
        }
    
    def _get_asset_type(self, asset_name: str) -> str:
        """Get asset type from config"""
        from config.assets import get_active_assets
        
        assets = get_active_assets()
        for asset in assets:
            if asset['name'] == asset_name:
                return asset.get('type', 'crypto')
        
        return 'crypto'  # Default