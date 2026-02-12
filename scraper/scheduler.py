"""
Smart Timeframe Scheduler

Only scrapes timeframes when needed based on candle close times.
Reduces unnecessary scraping by ~70%.
"""

from datetime import datetime, timedelta
import pytz

class TimeframeScheduler:
    """Determines which timeframes need to be scraped based on current time"""
    
    def __init__(self):
        self.utc = pytz.utc
    
    def get_timeframes_to_scrape(self):
        """
        Returns list of timeframes that should be scraped now
        
        Logic (UTC-based):
        - 3m: Every run (every 15m cron)
        - 15m: Every run (every 15m cron)
        - 1h: First 20 mins of the hour
        - 4h: First 20 mins of 00, 04, 08, 12, 16, 20 UTC
        - 12h: First 20 mins of 00, 12 UTC
        - 1d: First 20 mins of 00 UTC (runs at 7pm EST/8pm EDT)
        - 4d: First 20 mins of 00 UTC every 4 days
        """
        now = datetime.now(self.utc)
        timeframes_to_scrape = []
        
        # 3m: Scrape every time the worker runs
        timeframes_to_scrape.append('3m')
        
        # 15m: Scrape every time the worker runs
        timeframes_to_scrape.append('15m')
        
        # 1h: Scrape every time (Live updates)
        timeframes_to_scrape.append('1h')
        
        # 4h: Scrape every time (Live updates)
        timeframes_to_scrape.append('4h')

        # 1d: Twice daily at 00:00 UTC and 12:00 UTC (with 35m window)
        # Covers daily close (00:00) and mid-day check (12:00)
        if now.hour % 12 == 0 and now.minute < 35:
            timeframes_to_scrape.append('1d')
        
        # 12h: Run during first 20 mins of 12-hour intervals (keep efficient)
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
