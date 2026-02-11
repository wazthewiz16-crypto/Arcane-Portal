"""SQLite datastore for scraper results"""
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DB_PATH = Path("data/mango_scraper.db")

class MangoDataStore:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            # Scrapes table (existing)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scrapes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    tf_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    mango_d1 REAL,
                    mango_d2 REAL,
                    entry_up REAL,
                    entry_down REAL,
                    candle_time TEXT,
                    UNIQUE(name, timeframe, candle_time)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scrapes_lookup 
                ON scrapes(name, timeframe, candle_time)
            """)
            
            # Signals table (new)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    take_profit REAL,
                    stop_loss REAL,
                    rr_ratio REAL,
                    entry_zone_low REAL,
                    entry_zone_high REAL,
                    htf TEXT NOT NULL,
                    ltf TEXT NOT NULL,
                    status TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    alerted_discord BOOLEAN DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_lookup 
                ON signals(asset_name, status, entry_time)
            """)
    
    @contextmanager
    def get_connection(self):
        """Context manager for DB connections"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_scrape(self, scrape_data):
        """Save a single scrape result"""
        with self.get_connection() as conn:
            pv = scrape_data.get('PlotValues', {})
            
            candle_time = self._get_candle_time(
                scrape_data['timestamp'],
                scrape_data['timeframe']
            )
            
            conn.execute("""
                INSERT OR REPLACE INTO scrapes (
                symbol, name, timeframe, tf_type, timestamp,
                    open, high, low, close, volume,
                    mango_d1, mango_d2, entry_up, entry_down, candle_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scrape_data['symbol'],
                scrape_data['name'],
                scrape_data['timeframe'],
                scrape_data.get('tf_type', 'general'),  # Default to 'general' if not provided
                scrape_data['timestamp'],
                pv.get('Open'),
                pv.get('High'),
                pv.get('Low'),
                pv.get('Close'),
                pv.get('Volume'),
                pv.get('D1'),
                pv.get('D2'),
                pv.get('EntryUp'),
                pv.get('EntryDown'),
                candle_time
            ))
    
    def save_scrapes(self, scrape_list):
        """Save multiple scrape results"""
        for scrape in scrape_list:
            self.save_scrape(scrape)
    
    def save_signal(self, signal_data):
        """Save a trading signal (prevents duplicates within 1 hour)"""
        from datetime import datetime, timedelta
        
        with self.get_connection() as conn:
            # Check for duplicate signal in the last hour
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            
            existing = conn.execute("""
                SELECT id FROM signals
                WHERE asset_name = ?
                AND signal_type = ?
                AND status = 'ACTIVE'
                AND entry_time > ?
            """, (
                signal_data['asset_name'],
                signal_data['signal_type'],
                one_hour_ago
            )).fetchone()
            
            if existing:
                # Signal already exists, return existing ID
                return existing[0]
            
            # No duplicate found, insert new signal
            now = datetime.utcnow().isoformat()
            
            conn.execute("""
                INSERT INTO signals (
                    asset_name, asset_type, signal_type, confidence,
                    entry_price, take_profit, stop_loss, rr_ratio,
                    entry_zone_low, entry_zone_high,
                    htf, ltf, status, entry_time,
                    created_at, updated_at, alerted_discord
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data['asset_name'],
                signal_data['asset_type'],
                signal_data['signal_type'],
                signal_data['confidence'],
                signal_data['entry_price'],
                signal_data.get('take_profit'),
                signal_data.get('stop_loss'),
                signal_data.get('rr_ratio'),
                signal_data.get('entry_zone_low'),
                signal_data.get('entry_zone_high'),
                signal_data['htf'],
                signal_data['ltf'],
                signal_data.get('status', 'ACTIVE'),
                signal_data['entry_time'],
                now,
                now,
                signal_data.get('alerted_discord', False)
            ))
            
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    def get_active_signals(self):
        """Get all active signals"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM signals
                WHERE status = 'ACTIVE'
                ORDER BY entry_time DESC
            """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_signal_history(self, hours=24):
        """Get signal history for the last N hours"""
        from datetime import datetime, timedelta
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM signals
                WHERE entry_time >= ?
                ORDER BY entry_time DESC
            """, (cutoff,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def mark_signal_alerted(self, signal_id):
        """Mark a signal as alerted to Discord"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE signals
                SET alerted_discord = 1, updated_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), signal_id))
    
    def close_signal(self, signal_id):
        """Close a signal"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE signals
                SET status = 'CLOSED', updated_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), signal_id))
    
    def update_signal_statuses(self):
        """Update all active signals based on current prices"""
        with self.get_connection() as conn:
            # Get all active signals
            active_signals = conn.execute("""
                SELECT id, asset_name, signal_type, entry_price, take_profit, stop_loss
                FROM signals
                WHERE status = 'ACTIVE'
            """).fetchall()
            
            for signal in active_signals:
                signal_id, asset_name, signal_type, entry_price, take_profit, stop_loss = signal
                
                # Get latest price for this asset
                latest_price = conn.execute("""
                    SELECT close FROM scrapes
                    WHERE name = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (asset_name,)).fetchone()
                
                if not latest_price:
                    continue
                
                current_price = latest_price[0]
                
                # Check if TP or SL was hit
                is_long = 'LONG' in signal_type
                
                if is_long:
                    if current_price >= take_profit:
                        conn.execute("""
                            UPDATE signals
                            SET status = 'TP_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                    elif current_price <= stop_loss:
                        conn.execute("""
                            UPDATE signals
                            SET status = 'SL_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                else:  # SHORT
                    if current_price <= take_profit:
                        conn.execute("""
                            UPDATE signals
                            SET status = 'TP_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                    elif current_price >= stop_loss:
                        conn.execute("""
                            UPDATE signals
                            SET status = 'SL_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
    
    def get_history(self, name, timeframe, limit=10):
        """Get historical data for an asset/timeframe"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM scrapes
                WHERE name = ? AND timeframe = ?
                ORDER BY candle_time DESC
                LIMIT ?
            """, (name, timeframe, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_latest_for_all_assets(self):
        """Get latest scrape for each asset/timeframe combo"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM scrapes s1
                WHERE timestamp = (
                    SELECT MAX(timestamp)
                    FROM scrapes s2
                    WHERE s1.name = s2.name AND s1.timeframe = s2.timeframe
                )
                ORDER BY name, timeframe
            """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def _get_candle_time(self, timestamp_str, timeframe):
        """Align timestamp to candle start"""
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        if timeframe == "15m":
            aligned_min = (dt.minute // 15) * 15
            dt = dt.replace(minute=aligned_min, second=0, microsecond=0)
        elif timeframe == "1h":
            dt = dt.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "4h":
            aligned_hour = (dt.hour // 4) * 4
            dt = dt.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
        elif timeframe == "1d":
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return dt.isoformat()
