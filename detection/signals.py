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

        # ── BTC Macro Context: precompute once per run ──────────────────────
        # Reads latest BTC + BTC.D data from DB to classify the current crypto
        # macro environment. This is then used to filter/adjust altcoin signals.
        btc_context = self._get_btc_macro_context(assets_data)
        if btc_context['verdict'] != 'NEUTRAL':
            logger.info(f"📊 BTC Macro Context: {btc_context['verdict']} "
                        f"(BTC={btc_context['btc_dir']}, BTC.D={btc_context['btcd_dir']})")
        # ────────────────────────────────────────────────────────────────────

        # ── Drawdown Circuit Breaker check ───────────────────────────────────
        cb_active = False
        cb_val = self.datastore.get_setting("CIRCUIT_BREAKER_ACTIVE")
        if str(cb_val).lower() == 'true':
            expire_str = self.datastore.get_setting("CIRCUIT_BREAKER_EXPIRE_TIME")
            if expire_str:
                try:
                    from datetime import datetime
                    expire = datetime.fromisoformat(expire_str)
                    if datetime.utcnow() < expire:
                        cb_active = True
                        logger.info("🚨 Drawdown Circuit Breaker is ACTIVE! (Only Tier A+ setups permitted).")
                except:
                    pass
        self.cb_active = cb_active
        # ────────────────────────────────────────────────────────────────────

        # ── Correlated Positions Cap ────────────────────────────────────────────
        # Prevent stacking too many correlated crypto trades in the same direction.
        # Dynamically scaled by the auto-optimizer based on BTC Dominance/Volatility.
        cap_val = self.datastore.get_setting("MAX_CRYPTO_SAME_DIRECTION")
        MAX_CRYPTO_SAME_DIRECTION = int(cap_val) if cap_val else 2
        active_sigs = self.datastore.get_active_signals()
        active_crypto_longs  = sum(1 for s in active_sigs if s.get('asset_type') == 'crypto' and 'LONG'  in s['signal_type'])
        active_crypto_shorts = sum(1 for s in active_sigs if s.get('asset_type') == 'crypto' and 'SHORT' in s['signal_type'])
        # ────────────────────────────────────────────────────────────────────

        for name, timeframes in assets_data.items():
            if name.upper() in blacklist:
                logger.info(f"Skipping {name} — temporarily blacklisted by auto-optimizer.")
                continue
            
            # Skip context-only assets — they are macro inputs, not trade targets
            if name.upper() in ('BTCD',):
                continue

            # Swing signals (HTF -> LTF)
            swing_signal = self._detect_swing_signal(name, timeframes, sl_buffer_swing)
            if swing_signal and min_swing <= swing_signal['confidence'] <= max_swing:
                # Apply BTC macro context adjustment for crypto altcoins
                swing_signal = self._apply_btc_context_to_altcoin(name, swing_signal, btc_context)
                if swing_signal is None:
                    continue  # Blocked by BTC macro context
                # ── Correlated positions cap check ──
                is_long_signal = 'LONG' in swing_signal['signal_type']
                if swing_signal.get('asset_type') == 'crypto':
                    if is_long_signal and active_crypto_longs >= MAX_CRYPTO_SAME_DIRECTION:
                        logger.info(f"🚫 Correlated cap: skipping {name} LONG (already {active_crypto_longs} active crypto longs)")
                        continue
                    if not is_long_signal and active_crypto_shorts >= MAX_CRYPTO_SAME_DIRECTION:
                        logger.info(f"🚫 Correlated cap: skipping {name} SHORT (already {active_crypto_shorts} active crypto shorts)")
                        continue
                direction = 'LONG' if is_long_signal else 'SHORT'
                key = (name, 'SWING', direction)
                if key not in seen_this_run:
                    swing_signal = self._validate_mango_confluence(name, swing_signal)
                    if swing_signal:
                        seen_this_run.add(key)
                        signals.append(swing_signal)
                        # Update running count so subsequent assets in the same batch respect the cap
                        if swing_signal.get('asset_type') == 'crypto':
                            if is_long_signal: active_crypto_longs += 1
                            else:              active_crypto_shorts += 1
                else:
                    logger.debug(f"Dedup: suppressed duplicate {swing_signal['signal_type']} for {name} (already queued this run)")
            
            # Scalp signals (scalp_htf -> scalp_ltf)
            scalp_signal = self._detect_scalp_signal(name, timeframes, sl_buffer_scalp)
            if scalp_signal and min_scalp <= scalp_signal['confidence'] <= max_scalp:
                # Apply BTC macro context adjustment for crypto altcoins
                scalp_signal = self._apply_btc_context_to_altcoin(name, scalp_signal, btc_context)
                if scalp_signal is None:
                    continue  # Blocked by BTC macro context
                # ── Correlated positions cap check ──
                is_long_signal = 'LONG' in scalp_signal['signal_type']
                if scalp_signal.get('asset_type') == 'crypto':
                    if is_long_signal and active_crypto_longs >= MAX_CRYPTO_SAME_DIRECTION:
                        logger.info(f"🚫 Correlated cap: skipping {name} scalp LONG (already {active_crypto_longs} active crypto longs)")
                        continue
                    if not is_long_signal and active_crypto_shorts >= MAX_CRYPTO_SAME_DIRECTION:
                        logger.info(f"🚫 Correlated cap: skipping {name} scalp SHORT (already {active_crypto_shorts} active crypto shorts)")
                        continue
                direction = 'LONG' if is_long_signal else 'SHORT'
                key = (name, 'SCALP', direction)
                if key not in seen_this_run:
                    scalp_signal = self._validate_mango_confluence(name, scalp_signal)
                    if scalp_signal:
                        seen_this_run.add(key)
                        signals.append(scalp_signal)
                        if scalp_signal.get('asset_type') == 'crypto':
                            if is_long_signal: active_crypto_longs += 1
                            else:              active_crypto_shorts += 1
                else:
                    logger.debug(f"Dedup: suppressed duplicate {scalp_signal['signal_type']} for {name} (already queued this run)")
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        return signals
    
    def _get_btc_macro_context(self, assets_data: Dict) -> Dict:
        """
        Analyse the current BTC price trend and BTC Dominance trend from the
        in-memory scrape data to produce a macro verdict for altcoin filtering.

        Dominance Cycle (from chart reference):
          BTC.D ↑ + BTC ↑  → Alts fall (money flowing INTO BTC)
          BTC.D ↑ + BTC ↓  → Alts DUMP hard (risk-off, everyone out)
          BTC.D ↑ + BTC ~  → Alts stable / accumulation phase
          BTC.D ↓ + BTC ↑  → Alts MOON  (alt season — money rotating out of BTC)
          BTC.D ↓ + BTC ↓  → Alts stable
          BTC.D ↓ + BTC ~  → Alts slightly bullish

        Returns a dict:
          verdict  : 'ALT_BEARISH' | 'ALT_DUMP' | 'ALT_NEUTRAL' | 'ALT_SEASON' | 'NEUTRAL'
          btc_dir  : 'LONG' | 'SHORT' | 'NEUTRAL'
          btcd_dir : 'UP'   | 'DOWN'  | 'NEUTRAL'
          confidence_modifier : int (negative = penalty, positive = bonus)
        """
        # ── Get BTC 4H direction ──
        btc_tf = assets_data.get('BTC', {})
        btc_4h = btc_tf.get('4h') or btc_tf.get('1h')
        btc_dir = self._get_htf_direction(btc_4h) if btc_4h else None
        if btc_dir is None:
            btc_dir = 'NEUTRAL'

        # ── Get BTC.D 4H direction ──
        btcd_tf = assets_data.get('BTCD', {})
        btcd_4h = btcd_tf.get('4h') or btcd_tf.get('1h')
        btcd_dir_raw = self._get_htf_direction(btcd_4h) if btcd_4h else None
        # Translate LONG/SHORT to UP/DOWN for readability
        btcd_dir = 'UP' if btcd_dir_raw == 'LONG' else ('DOWN' if btcd_dir_raw == 'SHORT' else 'NEUTRAL')

        # ── Apply dominance cycle table ──
        if btcd_dir == 'UP' and btc_dir == 'LONG':
            # Money flowing INTO BTC — alts underperform / fall relative to BTC
            verdict = 'ALT_BEARISH'
            modifier = -5  # Penalise LONG alts, favour SHORT alts
        elif btcd_dir == 'UP' and btc_dir == 'SHORT':
            # Widespread risk-off, no safe haven for alts — hard dump likely
            verdict = 'ALT_DUMP'
            modifier = -10  # Strongly penalise LONG alts; SHORT alts get big bonus
        elif btcd_dir == 'DOWN' and btc_dir == 'LONG':
            # Alt season — capital rotating from BTC into alts; best alt LONG environment
            verdict = 'ALT_SEASON'
            modifier = +5  # Bonus for LONG alts, penalise SHORT alts
        elif btcd_dir == 'DOWN' and btc_dir == 'SHORT':
            # BTC dominance falling WITH BTC price — market selling everything but alts still stable
            verdict = 'ALT_NEUTRAL'
            modifier = 0
        elif btcd_dir == 'DOWN' and btc_dir == 'NEUTRAL':
            # Slight alt bias
            verdict = 'ALT_SLIGHTLY_BULLISH'
            modifier = +2
        else:
            # Unknown or stable — no strong bias
            verdict = 'NEUTRAL'
            modifier = 0

        return {
            'verdict': verdict,
            'btc_dir': btc_dir,
            'btcd_dir': btcd_dir,
            'confidence_modifier': modifier
        }

    def _apply_btc_context_to_altcoin(self, name: str, signal: Dict, btc_context: Dict) -> Optional[Dict]:
        """
        Apply the BTC macro context to an altcoin signal.
        - BTC itself is exempt from this filter (it IS the reference).
        - TradFi assets are exempt (unrelated to BTC dominance).
        - Context-only assets (BTCD) should be filtered out before this.

        Rules:
          ALT_DUMP    → Block LONG alts entirely; SHORT alts get +7 bonus
          ALT_BEARISH → Block LONG alts entirely; SHORT alts get +3 bonus
          ALT_SEASON  → Block SHORT alts entirely; LONG alts get +5 bonus
          ALT_SLIGHTLY_BULLISH → LONG alts get +2, no block on SHORT
          ALT_NEUTRAL / NEUTRAL → No change
        """
        from config.assets import ASSETS  # Avoid circular import at module level

        # Only apply to cryptocurrency altcoins (not BTC itself, not TradFi)
        asset_type = signal.get('asset_type', '').lower()
        if name.upper() == 'BTC' or asset_type != 'crypto':
            return signal  # Skip — BTC or TradFi are unaffected by dominance

        verdict = btc_context.get('verdict', 'NEUTRAL')
        modifier = btc_context.get('confidence_modifier', 0)
        is_long = 'LONG' in signal.get('signal_type', '')

        if verdict == 'ALT_DUMP':
            if is_long:
                logger.info(f"🚫 BTC context BLOCKED {name} LONG (ALT_DUMP: BTC falling + BTC.D rising)")
                return None
            else:
                # SHORT alts gain a significant bonus — this is the best SHORT environment
                signal['confidence'] = min(signal['confidence'] + 7, 100)
                signal['btc_context'] = verdict
                return signal

        elif verdict == 'ALT_BEARISH':
            if is_long:
                logger.info(f"🚫 BTC context BLOCKED {name} LONG (ALT_BEARISH: BTC.D rising, BTC rising)")
                return None
            else:
                signal['confidence'] = min(signal['confidence'] + 3, 100)
                signal['btc_context'] = verdict
                return signal

        elif verdict == 'ALT_SEASON':
            if not is_long:
                logger.info(f"🚫 BTC context BLOCKED {name} SHORT (ALT_SEASON: BTC.D falling, BTC rising)")
                return None
            else:
                # LONG alts in alt season get a solid boost
                signal['confidence'] = min(signal['confidence'] + 5, 100)
                signal['btc_context'] = verdict
                return signal

        elif verdict == 'ALT_SLIGHTLY_BULLISH' or verdict == 'ALT_NEUTRAL' or verdict == 'NEUTRAL':
            # Even in neutral dominance environments, we NEVER short altcoins if Bitcoin itself is in an explicit uptrend.
            # Shorting alts while BTC pumps is a surefire way to get liquidated.
            btc_dir = btc_context.get('btc_dir', 'NEUTRAL')
            if not is_long and btc_dir == 'LONG':
                logger.info(f"🚫 BTC context BLOCKED {name} SHORT (BTC itself is explicitly LONG - No counter-trend shorts allowed)")
                return None
                
            if is_long and verdict == 'ALT_SLIGHTLY_BULLISH':
                signal['confidence'] = min(signal['confidence'] + modifier, 100)
                
            signal['btc_context'] = verdict
            return signal

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
            swing_signal = self._validate_mango_confluence(asset_name, swing_signal)
            if swing_signal:
                signals.append(swing_signal)
        
        # Scalp signals
        scalp_signal = self._detect_scalp_signal(asset_name, timeframes)
        min_scalp = float(self.datastore.get_setting("MIN_CONFIDENCE_SCALP", settings.MIN_CONFIDENCE_SCALP))
        if scalp_signal and scalp_signal['confidence'] >= min_scalp:
            scalp_signal = self._validate_mango_confluence(asset_name, scalp_signal)
            if scalp_signal:
                signals.append(scalp_signal)
            
        return signals

    def _validate_mango_confluence(self, asset_name: str, signal: Dict) -> Optional[Dict]:
        """
        Validate signal against the premium Mango Research Dashboard data.
        
        Rules:
        - If confluence is disabled: passes through immediately.
        - Global Trend Filter:
          - A LONG signal is BLOCKED if the global market_trend is SHORT.
          - A SHORT signal is BLOCKED if the global market_trend is LONG.
        - If strict mode is enabled: if asset is not in dashboard data, blocks.
        - If asset is in dashboard data:
          - A LONG signal is BLOCKED if the individual asset trend is SHORT (Opposite-trend blocking).
          - A SHORT signal is BLOCKED if the individual asset trend is LONG (Opposite-trend blocking).
          - Volatility Exhaustion Filter (Scalps): If individual volatility > 85 and signal is a Scalp, blocks.
          - Volatility Compression Filter (Scalps): If individual volatility < 25 and signal is a Scalp, blocks.
        """
        try:
            from scraper.mango_dashboard import MangoDashboardScraper
            mango = MangoDashboardScraper()
            
            if not mango.is_enabled():
                return signal
                
            # Get cached global market metrics
            global_metrics = mango.get_global_metrics()
            market_trend = global_metrics.get("market_trend", "NEUTRAL").upper()
            market_volatility = global_metrics.get("market_volatility", 50)
            
            sig_direction = 'LONG' if 'LONG' in signal['signal_type'].upper() else 'SHORT'
            is_scalp = 'SCALP' in signal['signal_type'].upper()
            
            # 1. Global Trend Opposite-Trend Blocking
            if sig_direction == 'LONG' and market_trend == 'SHORT':
                logger.info(f"🚫 Mango Global Confluence BLOCKED: {asset_name} LONG signal fights SHORT overall market trend ({market_trend})!")
                return None
            elif sig_direction == 'SHORT' and market_trend == 'LONG':
                logger.info(f"🚫 Mango Global Confluence BLOCKED: {asset_name} SHORT signal fights LONG overall market trend ({market_trend})!")
                return None
                
            # Get cached individual confluence details
            confluence = mango.get_cached_confluence(asset_name)
            
            # Check strict mode settings
            strict_str = self.datastore.get_setting("MANGO_CONFLUENCE_STRICT")
            import os
            is_strict = str(strict_str).lower() == 'true' if strict_str is not None else os.getenv("MANGO_CONFLUENCE_STRICT", "false").lower() == "true"
            
            if not confluence:
                if is_strict:
                    logger.info(f"🚫 Mango Confluence: blocked {asset_name} {signal['signal_type']} - asset not found in dashboard cache (strict mode).")
                    return None
                else:
                    # Normal mode - unlisted asset passes individual check, but attach global metrics
                    logger.info(f"ℹ️  Mango Confluence: {asset_name} not found in dashboard cache. Passing through (normal mode) after global checks.")
                    signal['mango_confluence'] = {
                        'trend_badge': '❔ UNLISTED',
                        'volatility': 'N/A',
                        'flags': [],
                        'market_trend': '🟢 LONG' if market_trend == 'LONG' else ('🔴 SHORT' if market_trend == 'SHORT' else '🟣 NEUTRAL'),
                        'market_volatility': market_volatility,
                        'mtf_bullish': False,
                        'mtf_bearish': False
                    }
                    return signal
            
            trend_badge = confluence.get('trend', 'NEUTRAL').upper()
            volatility = confluence.get('volatility', 50)
            
            # 2. Individual Opposite-Trend Blocking
            if sig_direction == 'LONG' and trend_badge == 'SHORT':
                logger.info(f"🚫 Mango Confluence BLOCKED: {asset_name} LONG signal fights SHORT dashboard trend badge!")
                return None
            elif sig_direction == 'SHORT' and trend_badge == 'LONG':
                logger.info(f"🚫 Mango Confluence BLOCKED: {asset_name} SHORT signal fights LONG dashboard trend badge!")
                return None
                
            # 3. Volatility gate
            # Low volatility (blue) < 30 is safe and encouraged, do NOT block it (bypass any compression filters).
            # High volatility (red) >= 80 indicates exhaustion, block completely.
            if volatility >= 80:
                logger.info(f"🚫 Mango Volatility BLOCKED: {asset_name} {signal['signal_type']} blocked - extreme volatility exhaustion ({volatility} >= 80).")
                return None
                
            # Check major timeframes (4H, 12H, 1D). If any has high (red) volatility >= 80, block
            tf_vols = confluence.get('timeframe_volatilities', {})
            high_tf_vols = []
            for tf in ['4H', '12H', '1D']:
                if tf in tf_vols:
                    try:
                        tf_vol = int(tf_vols[tf])
                        if tf_vol >= 80:
                            high_tf_vols.append(f"{tf}: {tf_vol}")
                    except (ValueError, TypeError):
                        pass
            if high_tf_vols:
                logger.info(f"🚫 Mango Volatility BLOCKED: {asset_name} {signal['signal_type']} blocked - high timeframe volatility detected in {', '.join(high_tf_vols)} (exhaustion zone).")
                return None

            # Pull flags from confluence. Try specific LTF and HTF timeframe flags, and merge with base (1D) flags
            flags_set = set(confluence.get('flags', []))
            tf_flags = confluence.get('timeframe_flags', {})
            ltf_upper = str(signal.get('ltf', '')).upper()
            htf_upper = str(signal.get('htf', '')).upper()
            
            if ltf_upper in tf_flags:
                flags_set.update(tf_flags[ltf_upper])
            if htf_upper in tf_flags:
                flags_set.update(tf_flags[htf_upper])
                
            flags = list(flags_set)
            
            # Technical Flags Quality Rules
            BULLISH_FLAGS = ["Golden Cross", "Bullish Ichimoku", "RSI Bullish Divergence", "Cheap / Discount"]
            BEARISH_FLAGS = ["Death Cross", "Bearish Ichimoku", "RSI Bearish Divergence", "Expensive / Premium"]
            
            calculated_confidence = float(signal.get('confidence', 95.0))
            
            if sig_direction == "LONG":
                blocking_flags = [f for f in flags if f in ["Death Cross", "Bearish Ichimoku"]]
                if blocking_flags:
                    logger.info(f"🚫 Mango Flags BLOCKED: {asset_name} LONG signal blocked due to major contrarian flags: {', '.join(blocking_flags)}")
                    return None
                    
                mild_contrarian = [f for f in flags if f in ["Expensive / Premium", "RSI Bearish Divergence"]]
                if mild_contrarian:
                    calculated_confidence -= 20.0
                    logger.info(f"⚠️ Mango Flags PENALTY: {asset_name} LONG confidence penalized by -20% due to mild contrarian flags: {', '.join(mild_contrarian)}")
                    
                confirming = [f for f in flags if f in BULLISH_FLAGS]
                if confirming:
                    calculated_confidence += 10.0
                    logger.info(f"✨ Mango Flags BOOST: {asset_name} LONG confidence boosted by +10% due to confirming flags: {', '.join(confirming)}")
                    
            else:  # SHORT
                blocking_flags = [f for f in flags if f in ["Golden Cross", "Bullish Ichimoku"]]
                if blocking_flags:
                    logger.info(f"🚫 Mango Flags BLOCKED: {asset_name} SHORT signal blocked due to major contrarian flags: {', '.join(blocking_flags)}")
                    return None
                    
                mild_contrarian = [f for f in flags if f in ["Cheap / Discount", "RSI Bullish Divergence"]]
                if mild_contrarian:
                    calculated_confidence -= 20.0
                    logger.info(f"⚠️ Mango Flags PENALTY: {asset_name} SHORT confidence penalized by -20% due to mild contrarian flags: {', '.join(mild_contrarian)}")
                    
                confirming = [f for f in flags if f in BEARISH_FLAGS]
                if confirming:
                    calculated_confidence += 10.0
                    logger.info(f"✨ Mango Flags BOOST: {asset_name} SHORT confidence boosted by +10% due to confirming flags: {', '.join(confirming)}")
            
            # Volatility Quality Boost: low (blue) volatility (< 30) is safer to enter
            if volatility < 30:
                calculated_confidence += 10.0
                logger.info(f"✨ Mango Volatility BOOST: {asset_name} confidence boosted by +10% due to low (blue) volatility: {volatility}")
            
            calculated_confidence = max(0.0, min(100.0, calculated_confidence))
            
            alignment_threshold_pct = 60.0
            if calculated_confidence < alignment_threshold_pct:
                logger.info(f"🚫 Mango Flags BLOCKED: {asset_name} {sig_direction} signal blocked - penalized confidence {calculated_confidence:.1f}% is below threshold {alignment_threshold_pct}%")
                return None
                
            signal['confidence'] = calculated_confidence
            
            # Setup Tiering (A+, A, B) classification logic
            confirming_count = len(confirming) if 'confirming' in locals() else 0
            mtf_aligned = confluence.get('mtf_bullish', False) if sig_direction == 'LONG' else confluence.get('mtf_bearish', False)
            
            # Check ML Market Regime
            market_regime = self.datastore.get_setting("MARKET_REGIME")
            is_trending_regime = str(market_regime).upper() == 'TRENDING'
            
            if (calculated_confidence >= 85.0 and 
                volatility < 30 and 
                mtf_aligned and 
                confirming_count >= 2 and 
                is_trending_regime):
                tier = 'A+'
            elif (calculated_confidence >= 70.0 and 
                  volatility < 60 and 
                  confirming_count >= 1):
                tier = 'A'
            else:
                tier = 'B'
                
            signal['tier'] = tier
            
            # Drawdown Circuit Breaker Gating Check (Upgrade 2)
            if getattr(self, 'cb_active', False) and tier in ('A', 'B'):
                logger.info(f"🚫 Circuit Breaker GATING: {asset_name} {signal['signal_type']} (Tier {tier}) blocked — Drawdown Circuit Breaker is active.")
                return None
            
            # Attach confluence metrics to the signal dictionary for Discord embeds
            signal['mango_confluence'] = {
                'trend_badge': '🟢 LONG' if trend_badge == 'LONG' else ('🔴 SHORT' if trend_badge == 'SHORT' else '🟣 NEUTRAL'),
                'volatility': volatility,
                'timeframe_volatilities': confluence.get('timeframe_volatilities', {}),
                'flags': flags,
                'market_trend': '🟢 LONG' if market_trend == 'LONG' else ('🔴 SHORT' if market_trend == 'SHORT' else '🟣 NEUTRAL'),
                'market_volatility': market_volatility,
                'mtf_bullish': confluence.get('mtf_bullish', False),
                'mtf_bearish': confluence.get('mtf_bearish', False)
            }
            logger.info(f"✅ Mango Confluence CONFIRMED (Tier {tier}): {asset_name} {signal['signal_type']} matches/aligns with {trend_badge} dashboard badge (Vol: {volatility}).")
            return signal
            
        except Exception as e:
            logger.error(f"Error running Mango confluence check: {e}")
            return signal
    
    
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
            ('1d', '4h'),   # Daily/4H swing — primary swing combo
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
            
            # --- Grandmaster Filter (Daily & 4D Macro Trend Check) ---
            # Swing trades must never fight the Daily or 4D (Weekly) trend. 
            # NEUTRAL is OK, but explicitly OPPOSITE is forbidden.
            daily_data = timeframes.get('1d')
            weekly_data = timeframes.get('4d')
            
            if daily_data:
                daily_dir = self._get_htf_direction(daily_data)
                if daily_dir and daily_dir != 'NEUTRAL' and daily_dir != htf_direction:
                    continue  # Fighting the Daily trend
                    
            if weekly_data:
                weekly_dir = self._get_htf_direction(weekly_data)
                if weekly_dir and weekly_dir != 'NEUTRAL' and weekly_dir != htf_direction:
                    continue  # Fighting the Weekly/4D trend
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

            # --- Secondary Confirmation: Mango Equilibrium Tracker (LTF required) ---
            htf_eq = self._check_equilibrium(htf_data, htf_direction)
            ltf_eq = self._check_equilibrium(ltf_data, htf_direction)
            if not ltf_eq['expanding']:
                continue  # LTF color diverges or is compressing → skip
            # HTF is checked for bonus only (not required)
            # -----------------------------------------------------------------------
            
            # Calculate confidence
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=True, is_bounce=ltf_entry.get('is_bounce', False))
            # +3 bonus when BOTH TFs are expanding
            if htf_eq['expanding'] and ltf_eq['expanding']:
                confidence += ltf_eq['confidence_bonus']
            
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
                asset_name=name,
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
                'partial_tp': tp_sl['partial_tp'],
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

            # --- 4D Trend Agreement (Macro Alignment) ---
            # Scalps must never fight the weekly (4D) trend direction.
            # Prevents longing into a macro downtrend, or shorting into a macro bull market.
            weekly_data = timeframes.get('4d')
            if weekly_data:
                weekly_dir = self._get_htf_direction(weekly_data)
                if htf_direction == 'LONG' and weekly_dir == 'SHORT':
                    continue  # Don't scalp long against a bearish 4D trend
                if htf_direction == 'SHORT' and weekly_dir == 'LONG':
                    continue  # Don't scalp short against a bullish 4D trend
            # ------------------------------------------

            # --- LTF Ribbon Confirmation (Critical / Strict) ---
            # The 15m Mango Dynamic ribbon *itself* must EXPLICITLY agree with the trade direction.
            # NEUTRAL is NOT allowed — it means the ribbon has not fully confirmed the scalp momentum yet.
            ltf_ribbon_dir = self._get_htf_direction(ltf_data)
            if htf_direction == 'LONG' and ltf_ribbon_dir != 'LONG':
                continue  # 15m ribbon must be explicitly bullish for a scalp LONG
            if htf_direction == 'SHORT' and ltf_ribbon_dir != 'SHORT':
                continue  # 15m ribbon must be explicitly bearish for a scalp SHORT
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
            
            ltf_entry = self._check_ltf_entry(ltf_data, htf_direction, is_scalp=True)
            if not ltf_entry['valid']:
                continue

            # --- Secondary Confirmation: Mango Equilibrium Tracker (LTF required) ---
            htf_eq = self._check_equilibrium(htf_data, htf_direction)
            ltf_eq = self._check_equilibrium(ltf_data, htf_direction)
            if not ltf_eq['expanding']:
                continue  # LTF color diverges or is compressing → skip
            # HTF is checked for bonus only (not required)
            # -----------------------------------------------------------------------
            
            # Calculate confidence (stricter for scalps)
            confidence = self._calculate_confidence(htf_data, ltf_data, is_swing=False, is_bounce=ltf_entry.get('is_bounce', False))
            # +3 bonus when BOTH TFs are expanding
            if htf_eq['expanding'] and ltf_eq['expanding']:
                confidence += ltf_eq['confidence_bonus']
            
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
                asset_name=name,
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
                'partial_tp': tp_sl['partial_tp'],
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
        
        # The Mango Dynamic ribbon direction is determined by BOTH which band is on top
        # AND where price is relative to the bands.
        # Key insight: if price is ABOVE max(D1,D2), it's above the whole ribbon → bullish structure.
        #              if price is BELOW min(D1,D2), it's below the whole ribbon → bearish structure.
        #              if price is BETWEEN D1 and D2, it's inside the ribbon → in transition (NEUTRAL).
        ribbon_top    = max(mango_d1, mango_d2)  # highest ribbon band (ceiling)
        ribbon_bottom = min(mango_d1, mango_d2)  # lowest ribbon band (floor)
        is_bullish_ribbon = mango_d1 > mango_d2  # D1 on top = bullish crossover
        
        if price > ribbon_top:
            # Price is ABOVE the entire ribbon → bullish structure regardless of band order
            return 'LONG'
        elif price < ribbon_bottom:
            # Price is BELOW the entire ribbon → bearish structure regardless of band order
            return 'SHORT'
        else:
            # Price is INSIDE the ribbon → transitioning / neutral
            # Use ribbon direction as a tiebreaker: if D1>D2 lean LONG, else lean SHORT
            if is_bullish_ribbon:
                return 'LONG'   # Bullish crossover, price consolidating inside ribbon
            else:
                return 'SHORT'  # Bearish crossover, price consolidating inside ribbon
    
    def _check_equilibrium(self, data: Dict, signal_direction: str = None) -> Dict:
        """
        Secondary confirmation using Mango Equilibrium Tracker.
        
        Infers the band COLOR from expansion state + price position relative to the ribbon:
        
          GREEN  = expanding + bullish ribbon (price above ribbon) → confirms LONG
          RED    = expanding + bearish ribbon (price below ribbon) → confirms SHORT
          BLUE   = compressing + bullish ribbon                    → no momentum, risky
          ORANGE = compressing + bearish ribbon                    → no momentum, risky
        
        When signal_direction is provided:
          - GREEN aligns with LONG  → pass + bonus
          - RED   aligns with SHORT → pass + bonus
          - GREEN for SHORT (or RED for LONG) → divergence → BLOCK
          - BLUE/ORANGE → compressing → BLOCK
        
        When eq data is missing → pass through silently (no false negatives).
        """
        eq1       = data.get('eq_band1')
        eq2       = data.get('eq_band2')
        upper_vol = data.get('upper_vol_b')
        lower_vol = data.get('lower_vol_b')
        
        if not (eq1 and eq2 and upper_vol and lower_vol):
            # No equilibrium data yet — pass through silently
            return {'expanding': True, 'confidence_bonus': 0, 'color': 'UNKNOWN'}
        
        # --- Expansion state ---
        eq_spread  = abs(eq1 - eq2)
        vol_spread = abs(upper_vol - lower_vol)
        is_expanding = eq_spread >= vol_spread
        
        # --- Infer direction of expansion from price vs Mango Dynamic ribbon ---
        price = data.get('close')
        d1    = data.get('mango_d1')
        d2    = data.get('mango_d2')
        
        ribbon_dir = None
        if price and d1 and d2:
            ribbon_top    = max(d1, d2)
            ribbon_bottom = min(d1, d2)
            if price > ribbon_top:
                ribbon_dir = 'LONG'
            elif price < ribbon_bottom:
                ribbon_dir = 'SHORT'
            else:
                ribbon_dir = 'NEUTRAL'  # price inside ribbon = transitioning
        
        # --- Map to color ---
        if   is_expanding and ribbon_dir == 'LONG':    color = 'GREEN'
        elif is_expanding and ribbon_dir == 'SHORT':   color = 'RED'
        elif not is_expanding and ribbon_dir == 'LONG':  color = 'BLUE'
        elif not is_expanding and ribbon_dir == 'SHORT': color = 'ORANGE'
        else:                                            color = 'UNKNOWN'
        
        # --- No direction context → use simple expansion check ---
        if signal_direction is None:
            return {
                'expanding': is_expanding,
                'confidence_bonus': 3.0 if is_expanding else 0.0,
                'color': color
            }
        
        # --- Unknown color with direction context → block or unconfirmed ---
        if color == 'UNKNOWN':
            return {'expanding': False, 'confidence_bonus': 0, 'color': color}
        
        # --- Direction-aware color alignment check ---
        if color == 'GREEN' and signal_direction == 'LONG':
            # Bullish expansion confirming a LONG — best case
            return {'expanding': True, 'confidence_bonus': 3.0, 'color': color}
        
        elif color == 'RED' and signal_direction == 'SHORT':
            # Bearish expansion confirming a SHORT — best case
            return {'expanding': True, 'confidence_bonus': 3.0, 'color': color}
        
        elif color == 'GREEN' and signal_direction == 'SHORT':
            # Bullish expansion vs SHORT signal = divergence → block
            return {'expanding': False, 'confidence_bonus': 0, 'color': color}
        
        elif color == 'RED' and signal_direction == 'LONG':
            # Bearish expansion vs LONG signal = divergence → block
            return {'expanding': False, 'confidence_bonus': 0, 'color': color}
        
        else:
            # BLUE / ORANGE — compressing regardless of direction → block
            return {'expanding': False, 'confidence_bonus': 0, 'color': color}
    
    def _check_ltf_entry(self, ltf_data: Dict, direction: str, is_scalp: bool = False) -> Dict:
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
        
        # 0. Volume Filter (Phase 3) — reject low-volume candles
        # Low volume = no conviction behind the move, higher chance of false signal.
        # Only applied when volume data is available (TradFi may not always have it).
        volume = ltf_data.get('volume')
        if volume is not None and volume <= 0:
            return {'valid': False, 'reason': 'Zero volume candle — no market participation'}
        
        # 1. Chop Filter (Prop Firm Rule #1)
        # Verify the zone has enough width to be a valid trend, not a squeeze/chop
        # Width is difference between Entry Up and Entry Down relative to Price
        zone_width_pct = abs(entry_up - entry_down) / price
        min_width = 0.002  # 0.2% — loosened from 0.3% (diagnostics showed NDX/US30 at 0.25-0.28%)
        
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
        
        # 3. Momentum Confirmation (Close position)
        # Only reject truly terrible closes
        if candle_range > 0:
            close_position = (price - low) / candle_range
            
            # Stricter momentum check for scalps (35%), looser for swings (20%)
            min_close_pos = 0.35 if is_scalp else 0.20
            
            if direction == 'LONG' and close_position < min_close_pos:
                return {'valid': False, 'reason': f'Weak close for long (bottom {min_close_pos*100:.0f}%)'}
                
            if direction == 'SHORT' and close_position > (1.0 - min_close_pos):
                return {'valid': False, 'reason': f'Weak close for short (top {min_close_pos*100:.0f}%)'}

        # 4. Optimal Entry Zone Filter — REMOVED
        # If price is inside the Mango Dynamic zone (between entry_down and entry_up),
        # that is a valid entry by definition. The indicator already defines the boundaries.
        # Previously this rejected entries in the top 15% of the zone, which was too strict
        # and killed legitimate pullback entries on trending days.
        
        # --- END PHASE 1 IMPROVEMENTS ---

        # 5. Check Entry Position
        # Check if price is in entry zone
        in_zone = entry_down <= price <= entry_up
        
        near_entry = False
        is_bounce = False
        valid = False
        
        # Dynamic breakout capture % (auto-adjusted by Market Regime Detector)
        breakout_pct = float(self.datastore.get_setting('BREAKOUT_CAPTURE_PCT', 0.003))
        
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
                
            # OR if Bounce + close to top (dynamic breakout capture)
            # For swings, allow near-entry breakout capture. For scalps, strictly require in-zone.
            elif not is_scalp and is_bounce and price > entry_up and (price - entry_up) / entry_up < breakout_pct:
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
                
            # OR if Bounce + close to bottom (dynamic breakout capture)
            elif not is_scalp and is_bounce and price < entry_down and (entry_down - price) / entry_down < breakout_pct:
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
        
        # Soft Zone Position Penalty
        # Entries at extreme zone positions get a confidence penalty instead of a hard block.
        # For longs: entering at the TOP of the zone is risky (less room to TP).
        # For shorts: entering at the BOTTOM of the zone is risky.
        # Zone position > 90% or < 10% = -5 confidence.
        if ltf_price and entry_down and entry_up and (entry_up - entry_down) > 0:
            zone_pos = (ltf_price - entry_down) / (entry_up - entry_down)
            if zone_pos > 0.90 or zone_pos < 0.10:
                confidence -= 5
                
        # Cap at 100%
        return min(confidence, 100.0)
    
    # ── Asset-Specific RR Profiles (Phase 3) ─────────────────────────────────
    # BTC/ETH and major indices sustain bigger moves; altcoins mean-revert faster.
    ASSET_RR_PROFILES = {
        # Large-cap crypto — can sustain 2R moves on daily swings
        'BTC': {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'ETH': {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'SOL': {'swing_rr': 1.8, 'scalp_rr': 1.75},
        'BNB': {'swing_rr': 1.8, 'scalp_rr': 1.75},
        # Mid-cap altcoins — faster mean reversion, need tighter targets
        'XRP':  {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'DOGE': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'LINK': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'ADA':  {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'AVAX': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'ARB':  {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'HYPE': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'TRX':  {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'INJ':  {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'ONDO': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        'NEAR': {'swing_rr': 1.8, 'scalp_rr': 1.5},
        # TradFi indices — sustained trends, can hold 2R+ targets
        'NDX':    {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'SPX':    {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'US30':   {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'AUS200': {'swing_rr': 2.0, 'scalp_rr': 1.75},
        'DXY':    {'swing_rr': 2.0, 'scalp_rr': 1.75},
        # Commodities / Gold-backed Crypto — strong trends, hold 2.2R targets
        'PAXG':   {'swing_rr': 2.2, 'scalp_rr': 1.75},
        'SILVER': {'swing_rr': 2.2, 'scalp_rr': 1.75},
        'OIL':    {'swing_rr': 2.2, 'scalp_rr': 1.75},
    }
    # Default for any unlisted asset
    DEFAULT_RR = {'swing_rr': 1.8, 'scalp_rr': 1.5}
    # ────────────────────────────────────────────────────────────────────────

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
        asset_name: str = '',
        buffer_pct: float = None
    ) -> Optional[Dict]:
        """
        Calculate Take Profit and Stop Loss levels
        
        Uses Mango Dynamic boundaries as natural stops.
        Phase 3: Asset-specific RR ratios via ASSET_RR_PROFILES lookup.
        """
        
        # Small buffer beyond Mango Dynamic boundaries
        if buffer_pct is None:
            buffer_pct = 0.008 if is_scalp else 0.015
        
        # Define a minimum SL distance to avoid micro-wicks stopping us out instantly
        if is_scalp:
            if asset_type == 'crypto':
                MIN_RISK_PCT = 0.018  # 1.8% min SL for crypto scalps
            else:
                MIN_RISK_PCT = 0.015  # 1.5% min SL for tradfi scalps
        else:
            if asset_type == 'tradfi':
                MIN_RISK_PCT = 0.020  # 2% SL for tradfi swings
            else:
                MIN_RISK_PCT = 0.025  # 2.5% SL for crypto swings
        
        # Determine RR ratio — Phase 3: asset-specific lookup
        profile = self.ASSET_RR_PROFILES.get(asset_name.upper(), self.DEFAULT_RR)
        if is_scalp:
            if timeframe in ['3m', '5m']:
                rr_ratio = 1.2
            else:  # 15m
                rr_ratio = profile['scalp_rr']
        else:
            rr_ratio = profile['swing_rr']
        
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
            # Partial TP at exactly +1R (close 50%, move SL to breakeven)
            partial_tp = entry_price + risk
            
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
            # Partial TP at exactly +1R (close 50%, move SL to breakeven)
            partial_tp = entry_price - risk
        
        # Calculate actual RR ratio
        actual_rr = abs(take_profit - entry_price) / risk
        
        return {
            'take_profit': round(take_profit, 2 if entry_price > 1 else 6),
            'partial_tp': round(partial_tp, 2 if entry_price > 1 else 6),
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