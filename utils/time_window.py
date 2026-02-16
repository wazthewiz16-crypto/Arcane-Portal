"""Time window utilities for controlling scraper operation hours"""
from datetime import datetime
import pytz


def is_within_operating_hours() -> bool:
    """
    Check if current time is within operating hours (5am - 11pm EST)
    
    Returns:
        True if within operating hours, False otherwise
    """
    est = pytz.timezone('America/New_York')
    now_est = datetime.now(est)
    
    # Operating hours: 5am (05:00) to 11pm (23:00) EST
    start_hour = 5
    end_hour = 23
    
    current_hour = now_est.hour
    
    # Check if within operating window
    return start_hour <= current_hour < end_hour


def get_operating_hours_info() -> dict:
    """
    Get information about operating hours and current status
    
    Returns:
        Dictionary with current time, status, and next operating period
    """
    est = pytz.timezone('America/New_York')
    now_est = datetime.now(est)
    
    start_hour = 5
    end_hour = 23
    
    is_operating = is_within_operating_hours()
    
    # Calculate time until next period
    if is_operating:
        # Currently operating - show when we'll stop
        hours_until_end = end_hour - now_est.hour
        next_change = f"Operations end in ~{hours_until_end} hours at 11:00 PM EST"
    else:
        # Currently sleeping - show when we'll resume
        if now_est.hour < start_hour:
            hours_until_start = start_hour - now_est.hour
            next_change = f"Operations resume in ~{hours_until_start} hours at 5:00 AM EST"
        else:  # After 11pm
            hours_until_start = (24 - now_est.hour) + start_hour
            next_change = f"Operations resume in ~{hours_until_start} hours at 5:00 AM EST"
    
    return {
        'current_time_est': now_est.strftime('%Y-%m-%d %I:%M:%S %p %Z'),
        'is_operating': is_operating,
        'operating_hours': '5:00 AM - 11:00 PM EST',
        'status': 'ACTIVE' if is_operating else 'SLEEPING',
        'next_change': next_change
    }
