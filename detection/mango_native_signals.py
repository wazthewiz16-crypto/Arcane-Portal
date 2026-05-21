"""
Mango-Native Signal Detector
Generates trade signals directly from the Mango Research Dashboard.

Trigger: badge flip (NEUTRAL→LONG or SHORT→LONG etc.) AND ≥60% timeframe alignment.
TP/SL:   Fixed percentage from entry (configurable via env vars).
Dedup:   No re-fire for the same asset+direction within 4 hours.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Configurable defaults (override via Railway / .env)
# -------------------------------------------------------------------
DEFAULT_TP_PCT  = float(os.getenv("MANGO_NATIVE_TP_PCT",  "3.0"))   # +3 % TP
DEFAULT_SL_PCT  = float(os.getenv("MANGO_NATIVE_SL_PCT",  "1.5"))   # -1.5 % SL
ALIGNMENT_THRESHOLD  = 0.60   # ≥60 % of timeframes must agree
MIN_TIMEFRAMES       = 2      # need at least 2 TF readings to qualify
DEDUP_WINDOW_HOURS   = 4      # don't re-fire same asset+direction within 4 h
VOL_MIN              = 25     # below → dormant, skip
VOL_MAX              = 85     # above → exhaustion, skip
DB_KEY_PREV_BADGES   = "MANGO_PREVIOUS_BADGES"
DB_KEY_LAST_FIRED    = "MANGO_NATIVE_LAST_FIRED"


class MangoNativeSignalDetector:
    """
    Detects trade signals sourced entirely from the Mango Research Dashboard.

    Workflow per scrape cycle:
        1. Load current dashboard cache (badges, timeframes, volatility, global trend).
        2. Compare each asset's badge against the previously saved badge state.
        3. On a flip: check timeframe alignment ≥ ALIGNMENT_THRESHOLD.
        4. Apply volatility gate (VOL_MIN < vol < VOL_MAX).
        5. Apply global market-trend gate (signal must agree with market_trend,
           or market_trend is NEUTRAL).
        6. Deduplication: skip if same asset+direction fired within DEDUP_WINDOW_HOURS.
        7. Calculate TP/SL from fixed percentages.
        8. Save new badge state to DB; return list of signal dicts.
    """

    def __init__(self, datastore):
        self.datastore = datastore

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self) -> List[Dict]:
        """
        Run the full detection cycle. Returns a (possibly empty) list of
        Mango-native signal dicts ready for Discord + DB storage.
        """
        try:
            from scraper.mango_dashboard import MangoDashboardScraper
            scraper = MangoDashboardScraper()

            if not scraper.is_enabled():
                logger.debug("[MangoNative] Dashboard confluence not enabled — skipping.")
                return []

            cache = self._load_cache()
            if not cache:
                logger.warning("[MangoNative] No cached dashboard data found — skipping.")
                return []

            current_badges  = {sym: data.get("trend", "NEUTRAL").upper()
                               for sym, data in cache.get("assets", {}).items()}
            previous_badges = self._load_previous_badges()
            global_trend    = cache.get("market_trend", "NEUTRAL").upper()
            global_vol      = cache.get("market_volatility", 50)
            assets_data     = cache.get("assets", {})

            signals: List[Dict] = []

            for symbol, current_trend in current_badges.items():
                prev_trend = previous_badges.get(symbol, "UNKNOWN")

                # ── 1. Badge flip check ─────────────────────────────────────
                if not self._is_flip(prev_trend, current_trend):
                    continue

                direction = current_trend  # "LONG" or "SHORT"
                asset_data = assets_data.get(symbol, {})
                volatility = asset_data.get("volatility", 50)
                flags      = asset_data.get("flags", [])
                timeframes = asset_data.get("timeframes", {})

                logger.info(f"[MangoNative] {symbol}: badge flip detected "
                            f"{prev_trend} → {current_trend}")

                # ── 2. Timeframe alignment ──────────────────────────────────
                tf_ok, tf_pct, tf_summary = self._check_timeframe_alignment(
                    timeframes, direction
                )
                if not tf_ok:
                    logger.info(f"[MangoNative] {symbol} skipped — "
                                f"TF alignment too low ({tf_pct:.0%}): {tf_summary}")
                    continue

                # ── 3. Volatility gate ──────────────────────────────────────
                if volatility <= VOL_MIN:
                    logger.info(f"[MangoNative] {symbol} skipped — "
                                f"volatility too low ({volatility} ≤ {VOL_MIN}), dormant range.")
                    continue
                if volatility >= VOL_MAX:
                    logger.info(f"[MangoNative] {symbol} skipped — "
                                f"volatility too high ({volatility} ≥ {VOL_MAX}), exhaustion zone.")
                    continue

                # ── 4. Global market trend gate ─────────────────────────────
                if global_trend != "NEUTRAL":
                    if direction == "LONG" and global_trend == "SHORT":
                        logger.info(f"[MangoNative] {symbol} LONG blocked — "
                                    f"global market trend is SHORT.")
                        continue
                    if direction == "SHORT" and global_trend == "LONG":
                        logger.info(f"[MangoNative] {symbol} SHORT blocked — "
                                    f"global market trend is LONG.")
                        continue

                # ── 5. Deduplication ────────────────────────────────────────
                if self._is_duplicate(symbol, direction):
                    logger.info(f"[MangoNative] {symbol} {direction} skipped — "
                                f"duplicate within {DEDUP_WINDOW_HOURS}h window.")
                    continue

                # ── 6. Build signal ─────────────────────────────────────────
                entry_price = self._get_latest_price(symbol)
                if entry_price is None:
                    logger.warning(f"[MangoNative] {symbol} — no price data available, skipping.")
                    continue

                signal = self._build_signal(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    prev_trend=prev_trend,
                    volatility=volatility,
                    flags=flags,
                    timeframes=timeframes,
                    tf_pct=tf_pct,
                    tf_summary=tf_summary,
                    global_trend=global_trend,
                    global_vol=global_vol,
                )

                signals.append(signal)
                logger.info(f"[MangoNative] ✅ Signal generated: {symbol} {direction} "
                            f"@ ${entry_price:,.4f}")

            # ── 7. Persist updated badge state ──────────────────────────────
            self._save_badges(current_badges)

            # ── 8. Record fired signals for dedup ───────────────────────────
            for sig in signals:
                self._record_fired(sig["asset_name"], sig["signal_type"])

            return signals

        except Exception as e:
            logger.error(f"[MangoNative] Detection error: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_cache(self) -> Optional[Dict]:
        """Load the Mango dashboard cache from DB or local file."""
        from pathlib import Path
        CACHE_FILE = Path("data/mango_dashboard.json")

        try:
            if self.datastore:
                raw = self.datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
                if raw:
                    return json.loads(raw)
        except Exception as e:
            logger.error(f"[MangoNative] DB cache read error: {e}")

        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[MangoNative] Local cache read error: {e}")

        return None

    def _load_previous_badges(self) -> Dict[str, str]:
        """Load the previously saved badge states from the DB."""
        try:
            raw = self.datastore.get_setting(DB_KEY_PREV_BADGES)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.error(f"[MangoNative] Error loading previous badges: {e}")
        return {}

    def _save_badges(self, badges: Dict[str, str]) -> None:
        """Persist the current badge states to the DB for next-cycle comparison."""
        try:
            self.datastore.set_setting(DB_KEY_PREV_BADGES, json.dumps(badges))
        except Exception as e:
            logger.error(f"[MangoNative] Error saving badge states: {e}")

    def _is_flip(self, prev: str, current: str) -> bool:
        """
        A flip is any directional change that ends up at LONG or SHORT.
        NEUTRAL → NEUTRAL is not a flip. LONG → LONG is not a flip.
        UNKNOWN (first-ever scrape) does NOT trigger a signal — we need
        a baseline first.
        """
        if prev == "UNKNOWN":
            return False  # First scrape — establish baseline only
        if current not in ("LONG", "SHORT"):
            return False  # Flipping to NEUTRAL is not actionable
        return prev != current

    def _check_timeframe_alignment(
        self, timeframes: Dict[str, str], direction: str
    ):
        """
        Returns (ok: bool, pct: float, summary: str).
        ok  = True if pct ≥ ALIGNMENT_THRESHOLD and len ≥ MIN_TIMEFRAMES
        """
        if not timeframes or len(timeframes) < MIN_TIMEFRAMES:
            # If no per-TF data scraped yet — treat as passing with a note
            # (the scraper may not have navigated to the detail page yet)
            logger.info("[MangoNative] No per-timeframe data available — "
                        "alignment check bypassed (badge flip alone used).")
            return True, 1.0, {}

        total   = len(timeframes)
        agrees  = sum(1 for t in timeframes.values()
                      if t.upper() in (direction, "LONG" if direction == "LONG" else "SHORT"))
        pct     = agrees / total
        summary = {tf: t for tf, t in timeframes.items()}
        ok      = pct >= ALIGNMENT_THRESHOLD

        return ok, pct, summary

    def _is_duplicate(self, symbol: str, direction: str) -> bool:
        """Check if the same asset+direction was fired within DEDUP_WINDOW_HOURS."""
        try:
            raw = self.datastore.get_setting(DB_KEY_LAST_FIRED)
            if not raw:
                return False
            last_fired: Dict = json.loads(raw)
            key = f"{symbol}_{direction}"
            ts  = last_fired.get(key)
            if not ts:
                return False
            fired_at = datetime.fromisoformat(ts)
            age      = (datetime.utcnow() - fired_at).total_seconds() / 3600.0
            return age < DEDUP_WINDOW_HOURS
        except Exception as e:
            logger.error(f"[MangoNative] Dedup check error: {e}")
            return False

    def _record_fired(self, symbol: str, signal_type: str) -> None:
        """Record that this asset+direction just fired."""
        try:
            direction = "LONG" if "LONG" in signal_type else "SHORT"
            raw = self.datastore.get_setting(DB_KEY_LAST_FIRED)
            last_fired: Dict = json.loads(raw) if raw else {}
            key = f"{symbol}_{direction}"
            last_fired[key] = datetime.utcnow().isoformat()
            self.datastore.set_setting(DB_KEY_LAST_FIRED, json.dumps(last_fired))
        except Exception as e:
            logger.error(f"[MangoNative] Error recording fired signal: {e}")

    def _get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Fetch the most recent close price for an asset from the DB scrapes table.
        Tries the shortest timeframe first (15m → 1h → 4h → 1d).
        """
        try:
            scrapes = self.datastore.get_latest_for_asset(symbol)
            if not scrapes:
                return None

            tf_priority = ["15m", "1h", "4h", "1d"]
            scrape_map  = {s["timeframe"]: s for s in scrapes}

            for tf in tf_priority:
                if tf in scrape_map:
                    price = scrape_map[tf].get("close")
                    if price:
                        return float(price)

            # Fallback: any scrape with a close
            for s in scrapes:
                p = s.get("close")
                if p:
                    return float(p)
        except Exception as e:
            logger.error(f"[MangoNative] Price lookup error for {symbol}: {e}")

        return None

    def _build_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        prev_trend: str,
        volatility: int,
        flags: List[str],
        timeframes: Dict[str, str],
        tf_pct: float,
        tf_summary: Dict,
        global_trend: str,
        global_vol: int,
    ) -> Dict:
        """Construct the standardised signal dictionary."""
        tp_pct = DEFAULT_TP_PCT / 100.0
        sl_pct = DEFAULT_SL_PCT / 100.0

        if direction == "LONG":
            take_profit = round(entry_price * (1 + tp_pct), 6)
            stop_loss   = round(entry_price * (1 - sl_pct), 6)
            signal_type = "MANGO_LONG"
        else:
            take_profit = round(entry_price * (1 - tp_pct), 6)
            stop_loss   = round(entry_price * (1 + sl_pct), 6)
            signal_type = "MANGO_SHORT"

        risk       = abs(entry_price - stop_loss)
        rr_ratio   = round(abs(take_profit - entry_price) / risk, 2) if risk else 2.0
        confidence = round(tf_pct * 100, 1)   # % of TFs that agreed

        # Trend badge emoji helpers
        def trend_emoji(t: str) -> str:
            return {"LONG": "🟢 LONG", "SHORT": "🔴 SHORT"}.get(t, "🟣 NEUTRAL")

        return {
            # Core signal fields (compatible with existing Discord notifier)
            "asset_name":   symbol,
            "signal_type":  signal_type,
            "entry_price":  entry_price,
            "take_profit":  take_profit,
            "stop_loss":    stop_loss,
            "rr_ratio":     rr_ratio,
            "confidence":   confidence,
            "entry_time":   datetime.utcnow().isoformat() + "Z",
            "htf":          "Mango Dashboard",
            "ltf":          "Mango Dashboard",

            # Mango-native metadata (used by Discord notifier formatting)
            "is_mango_native":   True,
            "badge_flip_from":   prev_trend,
            "badge_flip_to":     direction,
            "timeframes":        tf_summary,
            "tf_alignment_pct":  tf_pct,
            "volatility":        volatility,
            "flags":             flags,

            # Global market context
            "market_trend":      trend_emoji(global_trend),
            "market_volatility": global_vol,
        }
