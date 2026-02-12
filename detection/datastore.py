"""SQLite/PostgreSQL datastore for scraper results"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# Check if we should use PostgreSQL (Railway) or SQLite (local)
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print(f"Using PostgreSQL database")
else:
    DB_PATH = Path("data/mango_scraper.db")
    print(f"Using SQLite database: {DB_PATH}")

class MangoDataStore:
    def __init__(self):
        if not USE_POSTGRES:
            DB_PATH.parent.mkdir(exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            if USE_POSTGRES:
                # PostgreSQL syntax
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS scrapes (
                        id SERIAL PRIMARY KEY,
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
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_scrapes_lookup 
                    ON scrapes(name, timeframe, candle_time)
                """)
                
                # Signals table
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS signals (
                        id SERIAL PRIMARY KEY,
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
                        alerted_discord BOOLEAN DEFAULT FALSE
                    )
                """)
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_signals_lookup 
                    ON signals(asset_name, status, entry_time)
                """)
            else:
                # SQLite syntax (existing code)
                self._execute_query(conn, """
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
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_scrapes_lookup 
                    ON scrapes(name, timeframe, candle_time)
                """)
                
                # Signals table (new)
                self._execute_query(conn, """
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
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_signals_lookup 
                    ON signals(asset_name, status, entry_time)
                """)
    
    @contextmanager
    def get_connection(self):
        """Context manager for DB connections"""
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
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
    
    def _execute_query(self, conn, query, params=None):
        """Execute query with database-specific syntax"""
        if USE_POSTGRES:
            # Convert ? to %s for PostgreSQL
            pg_query = query.replace('?', '%s')
            # Convert INSERT OR REPLACE to INSERT ... ON CONFLICT
            if 'INSERT OR REPLACE' in pg_query:
                pg_query = pg_query.replace('INSERT OR REPLACE', 'INSERT')
                if 'scrapes' in pg_query:
                    pg_query = pg_query.replace(
                        ') VALUES',
                        ') VALUES'
                    ) + ' ON CONFLICT (name, timeframe, candle_time) DO UPDATE SET ' + \
                        'symbol=EXCLUDED.symbol, tf_type=EXCLUDED.tf_type, timestamp=EXCLUDED.timestamp, ' + \
                        'open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close, ' + \
                        'volume=EXCLUDED.volume, mango_d1=EXCLUDED.mango_d1, mango_d2=EXCLUDED.mango_d2, ' + \
                        'entry_up=EXCLUDED.entry_up, entry_down=EXCLUDED.entry_down'
            
            # Handle last_insert_rowid() for PostgreSQL
            if 'last_insert_rowid()' in pg_query:
                pg_query = pg_query.replace('last_insert_rowid()', 'lastval()')
            
            cursor = conn.cursor()
            cursor.execute(pg_query, params or ())
            return cursor
        else:
            return conn.execute(query, params or ())
    
    def _fetch_query(self, conn, query, params=None):
        """Execute SELECT query and return results"""
        cursor = self._execute_query(conn, query, params)
        if USE_POSTGRES:
            # Fetch all and convert to dict
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:
            # SQLite already returns Row objects
            return [dict(row) for row in cursor.fetchall()]
    
    def save_scrape(self, scrape_data):
        """Save a single scrape result"""
        with self.get_connection() as conn:
            pv = scrape_data.get('PlotValues', {})
            
            candle_time = self._get_candle_time(
                scrape_data['timestamp'],
                scrape_data['timeframe']
            )
            
            self._execute_query(conn, """
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
        """Save a trading signal (prevents duplicates of ACTIVE signals)"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            # Check for ANY duplicate active signal
            cursor = self._execute_query(conn, """
                SELECT id FROM signals
                WHERE asset_name = ?
                AND signal_type = ?
                AND status = 'ACTIVE'
            """, (
                signal_data['asset_name'],
                signal_data['signal_type']
            ))
            existing = cursor.fetchone()
            
            if existing:
                # Signal already exists, return existing ID
                return existing[0]
            
            # No duplicate found, insert new signal
            now = datetime.utcnow().isoformat()
            
            self._execute_query(conn, """
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
            
            cursor = self._execute_query(conn, "SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
    
    def get_active_signals(self):
        """Get all active signals"""
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT * FROM signals
                WHERE status = 'ACTIVE'
                ORDER BY entry_time DESC
            """)
    
    def get_signal_history(self, hours=24):
        """Get signal history for the last N hours"""
        from datetime import datetime, timedelta
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT * FROM signals
                WHERE entry_time >= ?
                ORDER BY entry_time DESC
            """, (cutoff,))
    
    def mark_signal_alerted(self, signal_id):
        """Mark a signal as alerted to Discord"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            self._execute_query(conn, """
                UPDATE signals
                SET alerted_discord = 1, updated_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), signal_id))
    
    def close_signal(self, signal_id):
        """Close a signal"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            self._execute_query(conn, """
                UPDATE signals
                SET status = 'CLOSED', updated_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), signal_id))
    
    def update_signal_statuses(self):
        """Update all active signals based on current prices"""
        from datetime import datetime
        
        with self.get_connection() as conn:
            # Get all active signals
            active_signals = self._fetch_query(conn, """
                SELECT id, asset_name, signal_type, entry_price, take_profit, stop_loss
                FROM signals
                WHERE status = 'ACTIVE'
            """)
            
            for signal in active_signals:
                signal_id = signal['id']
                asset_name = signal['asset_name']
                signal_type = signal['signal_type']
                entry_price = signal['entry_price']
                take_profit = signal['take_profit']
                stop_loss = signal['stop_loss']
                
                # Get latest price for this asset
                latest_prices = self._fetch_query(conn, """
                    SELECT close FROM scrapes
                    WHERE name = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (asset_name,))
                
                if not latest_prices:
                    continue
                
                current_price = latest_prices[0]['close']
                
                # Check if TP or SL was hit
                is_long = 'LONG' in signal_type
                
                if is_long:
                    if current_price >= take_profit:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET status = 'TP_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                    elif current_price <= stop_loss:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET status = 'SL_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                else:  # SHORT
                    if current_price <= take_profit:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET status = 'TP_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
                    elif current_price >= stop_loss:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET status = 'SL_HIT', updated_at = ?
                            WHERE id = ?
                        """, (datetime.utcnow().isoformat(), signal_id))
    
    def get_history(self, name, timeframe, limit=10):
        """Get historical data for an asset/timeframe"""
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT * FROM scrapes
                WHERE name = ? AND timeframe = ?
                ORDER BY candle_time DESC
                LIMIT ?
            """, (name, timeframe, limit))
    
    def get_latest_for_all_assets(self):
        """Get latest scrape for each asset/timeframe combo"""
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT * FROM scrapes s1
                WHERE timestamp = (
                    SELECT MAX(timestamp)
                    FROM scrapes s2
                    WHERE s1.name = s2.name AND s1.timeframe = s2.timeframe
                )
                ORDER BY name, timeframe
            """)
    
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
