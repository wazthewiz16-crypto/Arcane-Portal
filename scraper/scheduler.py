"""
Smart Timeframe Scheduler

Only scrapes timeframes when needed based on candle close times.
Reduces unnecessary scraping by ~70%.
Full scans on first and last cron run of the EST trading day.
"""

from datetime import datetime, timedelta
import pytz

# All tradeable timeframes (excluding deprecated 3m)
ALL_TIMEFRAMES = ['15m', '1h', '4h', '12h', '1d', '4d']

# Cron schedule is */15 10-23,0-3 * * * UTC
# That maps to 05:00-03:59 EST (UTC-5), or 06:00-04:59 EDT (UTC-4)
# First scrape of day = 10:00 UTC (exactly) = 5:00 AM EST
# Last scrape window  = 03:30-03:59 UTC     = 10:30-10:59 PM EST
FIRST_SCRAPE_UTC_HOUR      = 10   # First cron run of day = 10:00 UTC
FIRST_SCRAPE_UTC_MINUTE_MAX = 14  # Window: 10:00-10:14 UTC
LAST_SCRAPE_UTC_HOUR       = 3    # Last cron run of day  = 03:30-03:45 UTC
LAST_SCRAPE_UTC_MINUTE_MIN = 30   # Window starts at :30

class TimeframeScheduler:
    """Determines which timeframes need to be scraped based on current time"""
    
    def __init__(self):
        self.utc = pytz.utc
    
    def _is_full_scan_run(self, now: datetime) -> bool:
        """
        Returns True if this is the FIRST or LAST cron run of the trading day in EST.
        
        Cron schedule: */15 10-23,0-3 * * * (UTC)
          = 5:00 AM – 10:59 PM EST (UTC-5)
        
        First run: UTC 10:00–10:14 (5:00–5:14 AM EST)
        Last  run: UTC 03:30–03:59 (10:30–10:59 PM EST)
        """
        is_first = (now.hour == FIRST_SCRAPE_UTC_HOUR and
                    now.minute <= FIRST_SCRAPE_UTC_MINUTE_MAX)
        is_last  = (now.hour == LAST_SCRAPE_UTC_HOUR and
                    now.minute >= LAST_SCRAPE_UTC_MINUTE_MIN)
        return is_first or is_last

    def get_timeframes_to_scrape(self):
        """
        Returns list of timeframes that should be scraped now.

        Special cases:
        - FIRST scrape of day (10:00 UTC / 5:00 AM EST): full scan of ALL timeframes
        - LAST  scrape of day (03:30 UTC / 10:30 PM EST): full scan of ALL timeframes

        Normal rules (cost-optimised):
        - 15m : every run
        - 1h  : twice per hour (minutes 0-14 and 25-44)
        - 4h  : once per hour  (minutes 0-14)
        - 1d  : at 00:00 and 12:00 UTC (first 35 mins)
        - 12h : at 00:00 and 12:00 UTC (first 20 mins)
        - 4d  : every 4 days at 00:00 UTC (minutes 5-34)
        """
        now = datetime.now(self.utc)

        # ── Full-scan on first / last EST cron run of the day ──────────────
        if self._is_full_scan_run(now):
            label = "FIRST" if now.hour == FIRST_SCRAPE_UTC_HOUR else "LAST"
            import logging
            logging.getLogger(__name__).info(
                f"Full scan triggered ({label} EST cron run): scraping ALL timeframes"
            )
            return list(ALL_TIMEFRAMES)
        # ───────────────────────────────────────────────────────────────────

        timeframes_to_scrape = []
        
        # 15m: Scrape every time the worker runs (for scalps)
        timeframes_to_scrape.append('15m')
        
        # 1h: Scrape twice per hour (first 15 mins, and around the 30-min mark)
        if now.minute < 15 or (25 <= now.minute < 45):
            timeframes_to_scrape.append('1h')
        
        # 4h: Scrape once per hour (first 15 minutes only)
        if now.minute < 15:
            timeframes_to_scrape.append('4h')

        # 1d: Twice daily at 00:00 UTC and 12:00 UTC (with 35m window)
        if now.hour % 12 == 0 and now.minute < 35:
            timeframes_to_scrape.append('1d')
        
        # 12h: Run during first 20 mins of 12-hour candle intervals
        if now.minute < 20 and now.hour % 12 == 0:
            timeframes_to_scrape.append('12h')
        
        # 4d: Every 4 days at 00 UTC (>5 mins after close)
        days_since_epoch = (now - datetime(2024, 1, 1, tzinfo=self.utc)).days
        if days_since_epoch % 4 == 0 and now.hour == 0 and 5 <= now.minute < 35:
            timeframes_to_scrape.append('4d')
        
        return timeframes_to_scrape
    
    def should_scrape_timeframe(self, timeframe):
        """Check if a specific timeframe should be scraped now"""
        return timeframe in self.get_timeframes_to_scrape()
    
    def get_next_scrape_time(self, timeframe):
        """Get the next time this timeframe should be scraped"""
        now = datetime.now(self.utc)
        
        if timeframe == '3m':
            # Next 15-minute mark (since we scrape every run)
            minutes_until_next = 15 - (now.minute % 15)
            return now + timedelta(minutes=minutes_until_next)
        
        elif timeframe == '15m':
            # Next 15-minute mark
            minutes_until_next = 15 - (now.minute % 15)
            return now + timedelta(minutes=minutes_until_next)
        
        elif timeframe == '1h':
            # Next hour
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        elif timeframe == '4h':
            # Next 4-hour mark
            hours_until_next = 4 - (now.hour % 4)
            next_time = now + timedelta(hours=hours_until_next)
            return next_time.replace(minute=0, second=0, microsecond=0)
        
        elif timeframe == '12h':
            # Next 12-hour mark
            if now.hour < 12:
                return now.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        elif timeframe == '1d':
            # Next day at 00:00 UTC
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        elif timeframe == '4d':
            # Next 4-day mark at 00:00 UTC
            days_since_epoch = (now - datetime(2024, 1, 1, tzinfo=self.utc)).days
            days_until_next = 4 - (days_since_epoch % 4)
            next_time = now + timedelta(days=days_until_next)
            return next_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return None
    
    def get_scrape_summary(self):
        """Get a summary of what will be scraped and when"""
        timeframes = ['3m', '15m', '1h', '4h', '12h', '1d', '4d']
        to_scrape = self.get_timeframes_to_scrape()
        
        summary = {
            'current_time': datetime.now(self.utc).strftime('%Y-%m-%d %H:%M:%S %Z'),
            'timeframes_to_scrape': to_scrape,
            'timeframes_to_skip': [tf for tf in timeframes if tf not in to_scrape],
            'next_scrape_times': {
                tf: self.get_next_scrape_time(tf).strftime('%Y-%m-%d %H:%M:%S %Z')
                for tf in timeframes
            }
        }
        
        return summary


# Example usage
if __name__ == '__main__':
    scheduler = TimeframeScheduler()
    
    print("=" * 60)
    print("SMART TIMEFRAME SCHEDULER")
    print("=" * 60)
    
    summary = scheduler.get_scrape_summary()
    
    print(f"\nCurrent Time: {summary['current_time']}")
    print(f"\n✅ Timeframes to SCRAPE now: {summary['timeframes_to_scrape'] or 'None'}")
    print(f"⏭️  Timeframes to SKIP now: {summary['timeframes_to_skip'] or 'None'}")
    
    print("\n📅 Next Scrape Times:")
    for tf, next_time in summary['next_scrape_times'].items():
        status = "✅ NOW" if tf in summary['timeframes_to_scrape'] else f"⏰ {next_time}"
        print(f"  {tf:>3} → {status}")
    
    print("\n" + "=" * 60)
