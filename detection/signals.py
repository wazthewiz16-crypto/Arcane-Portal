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
        self.datastore = datastore
        # Dynamic settings are now fetched at runtime
        # self.min_confidence_swing = settings.MIN_CONFIDENCE_SWING
        # self.min_confidence_scalp = settings.MIN_CONFIDENCE_SCALP
    
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
        
        # Load dynamic advanced optimization settings 
        min_swing = float(self.datastore.get_setting("MIN_CONFIDENCE_SWING", 70))
        min_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", 75))
        max_swing = float(self.datastore.get_setting("MAX_CONFIDENCE_SWING", 100))
        max_scalp = float(self.datastore.get_setting("MAX_CONFIDENCE_SCALP", 100))
        
        sl_buffer_swing = float(self.datastore.get_setting("SL_BUFFER_PCT_SWING", 0.015))
        sl_buffer_scalp = float(self.datastore.get_setting("SL_BUFFER_PCT_SCALP", 0.008))
        
        blacklist_str = self.datastore.get_setting("ASSET_BLACKLIST", "")
        blacklist = [a.strip().upper() for a in blacklist_str.split(',') if a.strip()]

        # Analyze each asset - both swing and scalp signals
        # Dedup set: (asset_name, direction) — prevents the same underlying
        # trade from firing twice in one run via different HTF combinations
        # e.g. BTC LONG via 1H->15m AND BTC LONG via 4H->15m = same trade, one signal
        seen_this_run = set()

        for name, timeframes in assets_data.items():
            if name.upper() in blacklist:
                logger.info(f"Skipping {name} — temporarily blacklisted by auto-optimizer.")
                continue

            # Swing signals (HTF -> LTF)
            swing_signal = self._detect_swing_signal(name, timeframes, sl_buffer_swing)
            if swing_signal and min_swing <= swing_signal['confidence'] <= max_swing:
                direction = 'LONG' if 'LONG' in swing_signal['signal_type'] else 'SHORT'
                key = (name, 'SWING', direction)
                if key not in seen_this_run:
                    seen_this_run.add(key)
                    signals.append(swing_signal)
                else:
                    logger.debug(f"Dedup: suppressed duplicate {swing_signal['signal_type']} for {name} (already queued this run)")
            
            # Scalp signals (scalp_htf -> scalp_ltf)
            scalp_signal = self._detect_scalp_signal(name, timeframes, sl_buffer_scalp)
            if scalp_signal and min_scalp <= scalp_signal['confidence'] <= max_scalp:
                direction = 'LONG' if 'LONG' in scalp_signal['signal_type'] else 'SHORT'
                key = (name, 'SCALP', direction)
                if key not in seen_this_run:
                    seen_this_run.add(key)
                    signals.append(scalp_signal)
                else:
                    logger.debug(f"Dedup: suppressed duplicate {scalp_signal['signal_type']} for {name} (already queued this run)")
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        return signals
    
    def detect_signals_for_asset(self, asset_name: str) -> List[Dict]:
        """Analyze a single asset and return signals above confidence threshold"""
        signals = []
        # Get latest data for this asset specifically
        latest_data = self.datastore.get_latest_for_asset(asset_name)
        
        # Group by timeframe
        timeframes = {}
        for row in latest_data:
            timeframes[row['timeframe']] = row
        
        # Analyze - Swing signals
        swing_signal = self._detect_swing_signal(asset_name, timeframes)
        min_swing = float(self.datastore.get_setting("MIN_CONFIDENCE_SWING", settings.MIN_CONFIDENCE_SWING))
        if swing_signal and swing_signal['confidence'] >= min_swing:
            signals.append(swing_signal)
        
        # Scalp signals
        scalp_signal = self._detect_scalp_signal(asset_name, timeframes)
        min_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP))
        if scalp_signal and scalp_signal['confidence'] >= min_scalp:
            signals.append(scalp_signal)
            
        return signals
    
    
    def _detect_swing_signal(self, name: str, timeframes: Dict, sl_buffer: float = 0.015) -> Optional[Dict]:
        """
        Detect swing signal (HTF-based position trade)
        
        Strategy:
        - HTF determines direction (bullish/bearish)
        - LTF determines entry (inside Mango Dynamic OR within bid zone)
        - Uses 4h → 1h or 1d → 4h combinations
        """
        # Try different HTF/LTF combinations for swing trading
        combinations = [
            ('4d', '1d'),   # Weekly/Daily swing
            ('1d', '4h'),   # Daily/4H swing
            ('4h', '1h'),   # 4H/1H swing (tighter, more reactive)
            ('12h', '1h'),  # 12H/1H swing (slower, use as last resort)
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
            
            # --- Grandmaster Filter (Daily Trend Check) ---
            # Swing must not fight the Daily trend. NEUTRAL daily is OK.
            daily_data = timeframes.get('1d')
            if daily_data:
                daily_dir = self._get_htf_direction(daily_data)
                # Only reject if Daily is explicitly OPPOSITE (not just neutral)
                if daily_dir and daily_dir != 'NEUTRAL' and daily_dir != htf_direction:
                    continue
            # ---------------------------------------------

            # --- Swing LTF Ribbon Confirmation ---
            # The LTF ribbon must EXPLICITLY agree with the signal direction.
            # NEUTRAL is NOT enough — it means the ribbon hasn't confirmed the move yet.
            ltf_direction = self._get_htf_direction(ltf_data)
            if htf_direction == 'LONG' and ltf_direction != 'LONG':
                continue  # LTF must be explicitly bullish for a LONG (not just non-SHORT)
            if htf_direction == 'SHORT' and ltf_direction != 'SHORT':
                continue  # LTF must be explicitly bearish for a SHORT (not just non-LONG)
            # -------------------------------------

            # --- 15m Real-Time Ribbon Cross-check (Mid-Candle Flip Detection) ---
            # Problem: the 1H is only scraped on candle close (up to 59 min stale).
            # The ribbon can FLIP within the live candle but the DB still shows old direction.
            # Root cause of DOGE SHORT: 1H D2 dropped from 0.09396→0.09308 mid-candle,
            # flipping ribbon bullish AFTER the scrape, but DB still said bearish at signal time.
            # Fix: use the 15m ribbon (scraped every 15 min, always fresh) as a real-time proxy.
            # If 15m D1/D2 definitively disagrees with the signal direction, kill the signal.
            fresh_15m = timeframes.get('15m')
            if fresh_15m:
                m15_d1 = fresh_15m.get('mango_d1')
                m15_d2 = fresh_15m.get('mango_d2')
                if m15_d1 and m15_d2:
                    m15_bullish = m15_d1 > m15_d2
                    if htf_direction == 'SHORT' and m15_bullish:
                        logger.debug(f"Skipping {name} SWING SHORT: 15m ribbon is BULLISH (D1={m15_d1:.5f} > D2={m15_d2:.5f}) — mid-candle flip detected")
                        continue  # 15m is bullish → LTF may be turning, don't short
                    if htf_direction == 'LONG' and not m15_bullish:
                        logger.debug(f"Skipping {name} SWING LONG: 15m ribbon is BEARISH (D2={m15_d2:.5f} > D1={m15_d1:.5f}) — mid-candle flip detected")
                        continue  # 15m is bearish → LTF may be turning, don't long
            # ------------------------------------------------------------------
            
            # Check LTF entry conditions
            ltf_entry = self._check_ltf_entry(ltf_data, htf_direction)
            if not ltf_entry['valid']:
                continue

            # --- Late Entry / Chase Filter ---
            # Reject if price has already moved far past the entry zone in signal direction.
            # This happens when the HTF ribbon lags and the move is already exhausted.
            ltf_price = ltf_data.get('close', 0)
            ltf_entry_up = ltf_data.get('entry_up', 0)
            ltf_entry_down = ltf_data.get('entry_down', 0)
            zone_width = ltf_entry_up - ltf_entry_down
            chase_buffer = max(zone_width * 1.5, ltf_price * 0.015)  # 1.5x zone or 1.5% price

            if htf_direction == 'LONG' and ltf_price > ltf_entry_up + chase_buffer:
                continue  # Price has already run far above resistance — too late
            if htf_direction == 'SHORT' and ltf_price < ltf_entry_down - chase_buffer:
                continue  # Price has already dumped far below support — too late
            # ---------------------------------
            
            # Calculate confidence
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=True, is_bounce=ltf_entry.get('is_bounce', False))
            
            # Determine signal type
            signal_type = SignalType.SWING_LONG if htf_direction == 'LONG' else SignalType.SWING_SHORT
            
            tp_sl = self._calculate_tp_sl(
                entry_price=ltf_data['close'],
                direction=htf_direction,
                entry_zone_low=ltf_data['entry_down'],
                entry_zone_high=ltf_data['entry_up'],
                candle_low=ltf_data['low'],
                candle_high=ltf_data['high'],
                timeframe=ltf_tf,
                is_scalp=False,
                asset_type=self._get_asset_type(name),
                buffer_pct=sl_buffer
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
    
    def _detect_scalp_signal(self, name: str, timeframes: Dict, sl_buffer: float = 0.008) -> Optional[Dict]:
        """
        Detect scalp signal (LTF-based quick trade)
        
        Strategy:
        - Faster timeframe alignment
        - Higher confidence threshold required
        - Uses 1h → 15m or 4h → 1h combinations
        """
        # Try different HTF/LTF combinations for scalp trading
        # Only timeframes actively scraped by the scheduler: 15m, 1h, 4h, 12h, 4d
        combinations = [
            ('4h', '15m'),  # 4H/15m scalp — primary scalp combo
            ('1h', '15m'),  # 1H/15m scalp — tighter confirmation
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
            
            # --- Grandmaster Filter (Daily Trend Check) ---
            # Ensure scalp direction aligns with Daily trend
            daily_data = timeframes.get('1d')
            if daily_data:
                daily_dir = self._get_htf_direction(daily_data)
                
                # Strict: Daily must match HTF direction (LONG/SHORT)
                # If Daily is Neutral or Opposite, we skip.
                if daily_dir != htf_direction:
                    # logger.debug(f"Skipping scalp for {name}: Daily {daily_dir} vs HTF {htf_direction}")
                    continue
            # ---------------------------------------------

            # --- LTF Ribbon Confirmation (Critical) ---
            # The 15m Mango Dynamic ribbon *itself* must agree with the trade direction.
            # Without this, the system would short an asset whose 15m ribbon is still
            # bullish just because the 4H is bearish — a contradictory, high-risk entry.
            # e.g. ADA SHORT 4H→15m fired when the 15m showed Trend: Bullish (D1 > D2)
            ltf_ribbon_dir = self._get_htf_direction(ltf_data)
            if htf_direction == 'LONG' and ltf_ribbon_dir == 'SHORT':
                continue  # Don't long if 15m ribbon is bearish
            if htf_direction == 'SHORT' and ltf_ribbon_dir == 'LONG':
                continue  # Don't short if 15m ribbon is still bullish
            # ------------------------------------------
            
            # --- Candle Color Check (Scalp Only) ---
            # Ensure momentum aligns with trade direction (Green for Long, Red for Short)
            open_price = ltf_data.get('open')
            close_price = ltf_data.get('close')
            
            if open_price and close_price:
                is_bullish = close_price > open_price
                is_bearish = close_price < open_price
                
                if htf_direction == 'LONG' and not is_bullish:
                    continue # Skip Long if candle is Red/Doji
                elif htf_direction == 'SHORT' and not is_bearish:
                    continue # Skip Short if candle is Green/Doji
            # ---------------------------------------
            
            ltf_entry = self._check_ltf_entry(ltf_data, htf_direction)
            if not ltf_entry['valid']:
                continue
            
            # Calculate confidence (stricter for scalps)
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=False, is_bounce=ltf_entry.get('is_bounce', False))
            
            # Determine signal type
            signal_type = SignalType.SCALP_LONG if htf_direction == 'LONG' else SignalType.SCALP_SHORT
            
            tp_sl = self._calculate_tp_sl(
                entry_price=ltf_data['close'],
                direction=htf_direction,
                entry_zone_low=ltf_data['entry_down'],
                entry_zone_high=ltf_data['entry_up'],
                candle_low=ltf_data['low'],
                candle_high=ltf_data['high'],
                timeframe=ltf_tf,
                is_scalp=True,
                asset_type=self._get_asset_type(name),
                buffer_pct=sl_buffer
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
        Prioritizes scraped 'Trend' text from TradingView if available.
        Returns: 'LONG', 'SHORT', 'NEUTRAL', or None
        """
        # 1. Prefer Scraped Trend (Single Source of Truth)
        scraped_trend = htf_data.get('trend')
        if scraped_trend:
            if 'Bullish' in scraped_trend: return 'LONG'
            if 'Bearish' in scraped_trend: return 'SHORT'
            if 'Neutral' in scraped_trend: return 'NEUTRAL'

        # 2. Fallback to Calculation using D1/D2 ribbon structure
        price = htf_data.get('close')
        mango_d1 = htf_data.get('mango_d1')
        mango_d2 = htf_data.get('mango_d2')
        entry_up = htf_data.get('entry_up')
        entry_down = htf_data.get('entry_down')
        
        if not (price and mango_d1 and mango_d2):
            return None
        
        # The Mango Dynamic ribbon direction is determined by which band is on top:
        # Bullish ribbon: D1 > D2 (D1 is the upper band, price is being supported)
        # Bearish ribbon: D2 > D1 (D2 is the upper band, price is being pressured down)
        is_bullish_ribbon = mango_d1 > mango_d2
        
        if is_bullish_ribbon:
            # Bullish trend: price above or within the support zone
            if entry_down and price >= entry_down:
                return 'LONG'
        else:
            # Bearish trend: price below or within the resistance zone
            if entry_up and price <= entry_up:
                return 'SHORT'
        
        return 'NEUTRAL'
    
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
        
        # 1. Chop Filter (Prop Firm Rule #1)
        # Verify the zone has enough width to be a valid trend, not a squeeze/chop
        # Width is difference between Entry Up and Entry Down relative to Price
        zone_width_pct = abs(entry_up - entry_down) / price
        min_width = 0.003  # 0.3% — loosened from 0.4% (was killing tradfi index signals)
        
        if zone_width_pct < min_width:
             return {'valid': False, 'reason': f'Chop/Squeeze detected (Zone width {zone_width_pct*100:.2f}%)'}

        # --- PHASE 1 IMPROVEMENTS ---
        
        # 2. Candle Size Filter (Avoid dojis and indecision)
        open_price = ltf_data.get('open', price)
        high = ltf_data.get('high', price)
        low = ltf_data.get('low', price)
        
        candle_body = abs(price - open_price)
        candle_range = high - low
        
        # Require meaningful candle body (not pure doji) - relaxed to 15%
        # This allows hammer/pin-bar entries which are high-quality reversal signals
        if candle_range > 0:
            body_ratio = candle_body / candle_range
            if body_ratio < 0.15:  # Body must be at least 15% of range
                return {'valid': False, 'reason': 'Doji/indecision candle (weak body)'}
        
        # 3. Momentum Confirmation (Close position) - Softened for volume
        # Only reject truly weak closes (bottom/top 35% of candle)
        if candle_range > 0:
            close_position = (price - low) / candle_range
            
            if direction == 'LONG' and close_position < 0.35:
                return {'valid': False, 'reason': 'Weak close for long (bottom 35%)'}
                
            if direction == 'SHORT' and close_position > 0.65:
                return {'valid': False, 'reason': 'Weak close for short (top 65%)'}

        # 4. Optimal Entry Zone Filter (Bottom 85% for longs, Top 85% for shorts)
        # Re-enabled at 85% (Very Permissive) to avoid entering at the very worst edge of the zone.
        # This prevents buying at the absolute top of support or selling at the absolute bottom of resistance.
        zone_size = entry_up - entry_down
        
        if direction == 'LONG':
            # For longs: Enter in bottom 75% of zone (avoids extreme top edge without being too strict)
            optimal_entry_top = entry_down + (zone_size * 0.75)
            if price > optimal_entry_top:
                return {'valid': False, 'reason': f'Price too high in zone (want bottom 75%)'}
        else:
            # For shorts: Enter in top 75% of zone (avoids extreme bottom edge without being too strict)
            optimal_entry_bottom = entry_up - (zone_size * 0.75)
            if price < optimal_entry_bottom:
                return {'valid': False, 'reason': f'Price too low in zone (want top 75%)'}
        
        # --- END PHASE 1 IMPROVEMENTS ---

        # 5. Check Entry Position
        # Check if price is in entry zone
        in_zone = entry_down <= price <= entry_up
        
        near_entry = False
        is_bounce = False
        valid = False
        
        if direction == 'LONG':
            # Check for bounce (Low wicked into zone)
            # Must be above entry_down to be a valid bounce off support (not below it)
            if price > entry_down: 
                # Touched zone (Low <= Top of zone)
                if low <= entry_up:
                    is_bounce = True
            
            # Valid if IN ZONE
            if in_zone:
                valid = True
                
            # OR if Bounce + Very close to top (Breakout < 0.3%)
            # This allows capturing the "Break back above" signal without chasing
            elif is_bounce and price > entry_up and (price - entry_up) / entry_up < 0.003:
                near_entry = True
                valid = True
                    
        else:
            # Short logic
            # Check for bounce (High wicked into zone)
            if price < entry_up:
                # Touched zone (High >= Bottom of zone)
                if high >= entry_down:
                    is_bounce = True
            
            # Valid if IN ZONE
            if in_zone:
                valid = True
                
            # OR if Bounce + Very close to bottom (Breakout < 0.3%)
            elif is_bounce and price < entry_down and (entry_down - price) / entry_down < 0.003:
                near_entry = True
                valid = True
        
        return {
            'valid': valid,
            'in_zone': in_zone,
            'near_entry': near_entry,
            'is_bounce': is_bounce,
            'reason': 'Valid entry' if valid else 'Not in entry zone'
        }
    
    def _calculate_confidence(self, htf_data: Dict, ltf_data: Dict, is_swing: bool, is_bounce: bool = False) -> float:
        """
        Calculate signal confidence (0-100%)
        
        Factors:
        - HTF trend strength
        - LTF entry quality (Bounce/Breakout)
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
            
        # Perfect Bounce Pattern Reward
        # Reduced from +15 to +8 — was too easily inflating scores into the 90%+ bucket
        if is_bounce:
            confidence += 8
        
        # Cap at 100%
        return min(confidence, 100.0)
    
    def _calculate_tp_sl(
        self,
        entry_price: float,
        direction: str,
        entry_zone_low: float,
        entry_zone_high: float,
        candle_low: float,
        candle_high: float,
        timeframe: str,
        is_scalp: bool = False,
        asset_type: str = 'crypto',
        buffer_pct: float = None
    ) -> Optional[Dict]:
        """
        Calculate Take Profit and Stop Loss levels
        
        PHASE 1 IMPROVEMENTS (Option B):
        - Uses Mango Dynamic boundaries as natural stops
        - Scalps (15m): 1.5-2R
        - Swings (4H-1D): 2-3R
        
        Rationale: The Mango Dynamic zone itself represents support/resistance.
        Using these boundaries as stops aligns with the indicator's logic and
        provides significantly wider stops than percentage-based buffers.
        """
        
        # Small buffer beyond Mango Dynamic boundaries
        if buffer_pct is None:
            buffer_pct = 0.008 if is_scalp else 0.015
        
        # Define a minimum SL distance to avoid micro-wicks stopping us out instantly
        if is_scalp:
            MIN_RISK_PCT = 0.015
        else:
            if asset_type == 'tradfi':
                MIN_RISK_PCT = 0.020  # 2% SL for tradfi swings
            else:
                MIN_RISK_PCT = 0.033  # 3.3% SL for crypto swings
        
        # Determine RR ratio based on timeframe
        if is_scalp:
            # Scalp timeframes (3m, 5m, 15m)
            if timeframe in ['3m', '5m']:
                rr_ratio = 1.2  # Softened from 1.5
            else:  # 15m
                rr_ratio = 1.6  # Softened from 2.0
        else:
            # Swing timeframes (4h, 1d, 12h, 4d)
            if timeframe in ['4h', '12h']:
                rr_ratio = 2.3  # Bumped from 2.0
            else:  # 1d, 4d
                rr_ratio = 2.7  # Bumped from 2.5
        
        if direction == 'LONG':
            # OPTION B: Use Mango Dynamic Lower Boundary (entry_down) as natural stop
            # This respects the indicator's support level
            # For Longs: SL below the support zone
            stop_loss = entry_zone_low * (1 - buffer_pct)
            
            # Enforce minimum risk width
            min_sl_price = entry_price * (1 - MIN_RISK_PCT)
            if stop_loss > min_sl_price:
                stop_loss = min_sl_price
                
            risk = entry_price - stop_loss
            
            # Invalid if Price <= SL (shouldn't happen with proper entries)
            if risk <= 0:
                return None
            
            # TP based on timeframe-specific RR ratio
            take_profit = entry_price + (risk * rr_ratio)
            
        else:
            # OPTION B: Use Mango Dynamic Upper Boundary (entry_up) as natural stop
            # This respects the indicator's resistance level
            # For Shorts: SL above the resistance zone
            stop_loss = entry_zone_high * (1 + buffer_pct)
            
            # Enforce minimum risk width
            min_sl_price = entry_price * (1 + MIN_RISK_PCT)
            if stop_loss < min_sl_price:
                stop_loss = min_sl_price
                
            risk = stop_loss - entry_price

            # Invalid if Price >= SL
            if risk <= 0:
                return None
            
            # TP based on timeframe-specific RR ratio
            take_profit = entry_price - (risk * rr_ratio)
        
        # Calculate actual RR ratio
        actual_rr = abs(take_profit - entry_price) / risk
        
        return {
            'take_profit': round(take_profit, 2 if entry_price > 1 else 6),
            'stop_loss': round(stop_loss, 2 if entry_price > 1 else 6),
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