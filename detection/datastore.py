"""SQLite/PostgreSQL datastore for scraper results"""
import sqlite3
import os
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check if we should use PostgreSQL (Railway) or SQLite (local)
DATABASE_URL = os.getenv('DATABASE_URL')
# Only use Postgres if DATABASE_URL is set AND starts with postgres (not sqlite://)
USE_POSTGRES = DATABASE_URL is not None and DATABASE_URL.startswith('postgres')

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
        # Auto-expire orphaned ACTIVE signals on every startup
        try:
            self.expire_stale_signals()
            self.expire_stale_scalps()
            self.cleanup_old_data()
        except Exception as e:
            logger.warning(f"Could not perform startup cleanup: {e}")
    
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
                        trend TEXT,
                        upper_vol_b REAL,
                        lower_vol_b REAL,
                        eq_band1 REAL,
                        eq_band2 REAL,
                        UNIQUE(name, timeframe, candle_time)
                    )
                """)
                
                # Ensure new columns exist (Migrations)
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN IF NOT EXISTS trend TEXT")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN IF NOT EXISTS upper_vol_b REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN IF NOT EXISTS lower_vol_b REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN IF NOT EXISTS eq_band1 REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN IF NOT EXISTS eq_band2 REAL")
                except: pass
                
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
                        partial_tp REAL,
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
                        alerted_discord BOOLEAN DEFAULT FALSE,
                        partial_tp_hit BOOLEAN DEFAULT FALSE,
                        tier TEXT DEFAULT 'B'
                    )
                """)
                # Migrations: add new columns if they don't exist on old DBs
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN IF NOT EXISTS partial_tp REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN IF NOT EXISTS partial_tp_hit BOOLEAN DEFAULT FALSE")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'B'")
                except: pass
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_signals_lookup 
                    ON signals(asset_name, status, entry_time)
                """)

                # Screenshots table (Postgres)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS screenshots (
                        asset_name TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        image_data BYTEA,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (asset_name, timeframe)
                    )
                """)

                # Signal Images table (Postgres)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS signal_images (
                        signal_id INTEGER PRIMARY KEY,
                        image_data BYTEA,
                        FOREIGN KEY(signal_id) REFERENCES signals(id) ON DELETE CASCADE
                    )
                """)
                
                # System Settings table (Postgres)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # Mango Scrapes table (Postgres)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS mango_scrapes (
                        id SERIAL PRIMARY KEY,
                        timestamp TEXT NOT NULL UNIQUE,
                        market_trend TEXT,
                        market_volatility REAL,
                        assets_json TEXT NOT NULL
                    )
                """)
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_mango_scrapes_timestamp 
                    ON mango_scrapes(timestamp)
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
                        trend TEXT,
                        upper_vol_b REAL,
                        lower_vol_b REAL,
                        eq_band1 REAL,
                        eq_band2 REAL,
                        UNIQUE(name, timeframe, candle_time)
                    )
                """)
                
                # Ensure new columns exist (Migrations)
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN trend TEXT")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN upper_vol_b REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN lower_vol_b REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN eq_band1 REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE scrapes ADD COLUMN eq_band2 REAL")
                except: pass
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_scrapes_lookup 
                    ON scrapes(name, timeframe, candle_time)
                """)
                
                # Signals table
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_name TEXT NOT NULL,
                        asset_type TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        entry_price REAL NOT NULL,
                        take_profit REAL,
                        partial_tp REAL,
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
                        alerted_discord BOOLEAN DEFAULT 0,
                        partial_tp_hit BOOLEAN DEFAULT 0,
                        tier TEXT DEFAULT 'B'
                    )
                """)
                # Migrations
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN partial_tp REAL")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN partial_tp_hit BOOLEAN DEFAULT 0")
                except: pass
                try: self._execute_query(conn, "ALTER TABLE signals ADD COLUMN tier TEXT DEFAULT 'B'")
                except: pass
                
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_signals_lookup 
                    ON signals(asset_name, status, entry_time)
                """)

                # Screenshots table (SQLite)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS screenshots (
                        asset_name TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        image_data BLOB,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (asset_name, timeframe)
                    )
                """)

                # Signal Images table (SQLite)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS signal_images (
                        signal_id INTEGER PRIMARY KEY,
                        image_data BLOB,
                        FOREIGN KEY(signal_id) REFERENCES signals(id) ON DELETE CASCADE
                    )
                """)
                
                # System Settings table (SQLite)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # Mango Scrapes table (SQLite)
                self._execute_query(conn, """
                    CREATE TABLE IF NOT EXISTS mango_scrapes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL UNIQUE,
                        market_trend TEXT,
                        market_volatility REAL,
                        assets_json TEXT NOT NULL
                    )
                """)
                self._execute_query(conn, """
                    CREATE INDEX IF NOT EXISTS idx_mango_scrapes_timestamp 
                    ON mango_scrapes(timestamp)
                """)

    def get_setting(self, key, default_value=None):
        """Get a system setting value"""
        with self.get_connection() as conn:
            cursor = self._execute_query(conn, "SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row[0] if isinstance(row, tuple) else row['value']
            return default_value

    def set_setting(self, key, value):
        """Set a system setting value"""
        from datetime import datetime
        with self.get_connection() as conn:
            if USE_POSTGRES:
                self._execute_query(conn, """
                    INSERT INTO system_settings (key, value, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """, (key, str(value), datetime.utcnow().isoformat()))
            else:
                self._execute_query(conn, """
                    INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, str(value), datetime.utcnow().isoformat()))
    
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
            # Escape literal % characters for psycopg2 by doubling them (except parameters %s)
            pg_query = pg_query.replace('%', '%%').replace('%%s', '%s')
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
                        'entry_up=EXCLUDED.entry_up, entry_down=EXCLUDED.entry_down, ' + \
                        'upper_vol_b=EXCLUDED.upper_vol_b, lower_vol_b=EXCLUDED.lower_vol_b, ' + \
                        'eq_band1=EXCLUDED.eq_band1, eq_band2=EXCLUDED.eq_band2'
            
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
    
    def save_mango_scrapes(self, market_trend, market_volatility, assets, timestamp=None):
        """Save a Mango Dashboard scrape result containing assets and global market variables"""
        import json
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        if not timestamp.endswith('Z') and 'T' in timestamp:
            if '+' not in timestamp and '-' not in timestamp[10:]:
                timestamp = timestamp + 'Z'
                
        assets_json = json.dumps(assets)
        with self.get_connection() as conn:
            if USE_POSTGRES:
                self._execute_query(conn, """
                    INSERT INTO mango_scrapes (timestamp, market_trend, market_volatility, assets_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (timestamp) DO UPDATE SET 
                        market_trend = EXCLUDED.market_trend,
                        market_volatility = EXCLUDED.market_volatility,
                        assets_json = EXCLUDED.assets_json
                """, (timestamp, market_trend, market_volatility, assets_json))
            else:
                self._execute_query(conn, """
                    INSERT OR REPLACE INTO mango_scrapes (timestamp, market_trend, market_volatility, assets_json)
                    VALUES (?, ?, ?, ?)
                """, (timestamp, market_trend, market_volatility, assets_json))
        logger.info(f"Saved mango scrape to DB at {timestamp}")

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
                    mango_d1, mango_d2, entry_up, entry_down, candle_time, trend,
                    upper_vol_b, lower_vol_b, eq_band1, eq_band2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scrape_data['symbol'],
                scrape_data['name'],
                scrape_data['timeframe'],
                scrape_data.get('tf_type', 'general'),
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
                candle_time,
                pv.get('Trend'),
                pv.get('UpperVolB'),
                pv.get('LowerVolB'),
                pv.get('EqBand1'),
                pv.get('EqBand2')
            ))
    
    def save_scrapes(self, scrape_list):
        """Save multiple scrape results"""
        for scrape in scrape_list:
            self.save_scrape(scrape)
    
    def save_signal(self, signal_data):
        """Save a trading signal.
        
        Deduplication rules:
        1. Never create a new signal if one of the same type is still ACTIVE.
        2. Never create a new signal within 4 hours of the last one for the same
           asset+direction (even if the old one already closed via TP/SL).
           This prevents re-entry spam when a signal closes quickly.
        """
        from datetime import datetime, timedelta
        
        with self.get_connection() as conn:
            # Rule 1: Block if an ACTIVE signal already exists
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
                return existing[0]

            # Rule 2: 2-hour cooldown per asset+direction (any status)
            cooldown_cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()
            cursor = self._execute_query(conn, """
                SELECT id FROM signals
                WHERE asset_name = ?
                AND signal_type = ?
                AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (
                signal_data['asset_name'],
                signal_data['signal_type'],
                cooldown_cutoff
            ))
            recent = cursor.fetchone()
            if recent:
                import logging
                logging.getLogger(__name__).info(
                    f"Cooldown: suppressing {signal_data['signal_type']} for "
                    f"{signal_data['asset_name']} — signal already created within 4h"
                )
                return recent[0]
            
            # No duplicate found, insert new signal
            now = datetime.utcnow().isoformat()
            
            self._execute_query(conn, """
                INSERT INTO signals (
                    asset_name, asset_type, signal_type, confidence,
                    entry_price, take_profit, partial_tp, stop_loss, rr_ratio,
                    entry_zone_low, entry_zone_high,
                    htf, ltf, status, entry_time,
                    created_at, updated_at, alerted_discord, tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data['asset_name'],
                signal_data['asset_type'],
                signal_data['signal_type'],
                signal_data['confidence'],
                signal_data['entry_price'],
                signal_data.get('take_profit'),
                signal_data.get('partial_tp'),
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
                signal_data.get('alerted_discord', False),
                signal_data.get('tier', 'B')
            ))
            
            cursor = self._execute_query(conn, "SELECT last_insert_rowid()")
            return cursor.fetchone()[0]
    
    def get_active_signals(self, max_age_days: int = 7):
        """Get all active signals, excluding stale orphans older than max_age_days.
        
        Signals left ACTIVE indefinitely are usually orphans — the monitor
        never closed them because it missed cycles. Capping at 7 days ensures
        they don't pollute the correlated position cap and open position count.
        """
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT * FROM signals
                WHERE status = 'ACTIVE'
                AND entry_time >= ?
                ORDER BY entry_time DESC
            """, (cutoff,))
    
    def expire_stale_signals(self, max_age_days: int = 5):
        """Mark ACTIVE signals older than max_age_days as EXPIRED.
        
        Prevents indefinite accumulation of orphaned ACTIVE signals that were
        never closed by the status monitor. Called automatically on startup.
        """
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            result = self._execute_query(conn, """
                UPDATE signals
                SET status = 'EXPIRED', updated_at = ?
                WHERE status = 'ACTIVE'
                AND entry_time < ?
            """, (now, cutoff))
            if hasattr(result, 'rowcount') and result.rowcount:
                logger.info(f"Expired {result.rowcount} stale ACTIVE signal(s) older than {max_age_days} days")

    def expire_stale_scalps(self, max_age_hours: int = 12):
        """Auto-expire ACTIVE scalp signals older than max_age_hours.
        
        Scalp trades (4H→15m, 1H→15m) are designed to resolve within hours.
        If they haven't hit TP or SL within 12 hours, the setup is invalidated
        and keeping them open just clutters the dashboard. This lets the user
        focus on swing trades without worrying about stale scalps.
        """
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            result = self._execute_query(conn, """
                UPDATE signals
                SET status = 'EXPIRED', updated_at = ?
                WHERE status = 'ACTIVE'
                AND signal_type LIKE '%SCALP%'
                AND entry_time < ?
            """, (now, cutoff))
            if hasattr(result, 'rowcount') and result.rowcount and result.rowcount > 0:
                logger.info(f"Auto-expired {result.rowcount} scalp signal(s) older than {max_age_hours} hours")

    def cleanup_old_data(self):
        """Auto-delete old images and scrapes to prevent database bloat"""
        from datetime import datetime, timedelta
        # Keep 7 days of signal images (for recent dashboard history)
        img_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        # Keep 60 days of scrapes (ML regime needs max 45 days)
        scrape_cutoff = (datetime.utcnow() - timedelta(days=60)).isoformat()
        
        try:
            with self.get_connection() as conn:
                # 1. Delete signal images for old signals (reduces 172MB+ bloat)
                res1 = self._execute_query(conn, """
                    DELETE FROM signal_images 
                    WHERE signal_id IN (
                        SELECT id FROM signals WHERE entry_time < ?
                    )
                """, (img_cutoff,))
                if hasattr(res1, 'rowcount') and res1.rowcount and res1.rowcount > 0:
                    logger.info(f"Cleaned up {res1.rowcount} old signal images")
                
                # 2. Delete old scrapes (reduces 32MB+ bloat)
                res2 = self._execute_query(conn, """
                    DELETE FROM scrapes WHERE timestamp < ?
                """, (scrape_cutoff,))
                if hasattr(res2, 'rowcount') and res2.rowcount and res2.rowcount > 0:
                    logger.info(f"Cleaned up {res2.rowcount} old scrapes")
                    
                # 3. Delete old mango scrapes
                res3 = self._execute_query(conn, """
                    DELETE FROM mango_scrapes WHERE timestamp < ?
                """, (scrape_cutoff,))
                if hasattr(res3, 'rowcount') and res3.rowcount and res3.rowcount > 0:
                    logger.info(f"Cleaned up {res3.rowcount} old mango scrapes")
                    
        except Exception as e:
            logger.error(f"Data cleanup error: {e}")
    
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
                SET alerted_discord = TRUE, updated_at = ?
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
        """Update all active signals based on current prices.
        
        Two-stage exit logic:
          Stage 1: Price hits partial_tp (+1R) → mark partial_tp_hit, move SL to entry (breakeven).
          Stage 2a: Price hits full take_profit → TP_HIT.
          Stage 2b: Price hits stop_loss (now at entry after stage 1) → BREAKEVEN or SL_HIT.
        """
        from datetime import datetime
        
        with self.get_connection() as conn:
            # Get all active signals with partial_tp fields
            active_signals = self._fetch_query(conn, """
                SELECT id, asset_name, signal_type, entry_price, take_profit,
                       partial_tp, stop_loss, partial_tp_hit
                FROM signals
                WHERE status = 'ACTIVE'
            """)
            
            for signal in active_signals:
                signal_id    = signal['id']
                asset_name   = signal['asset_name']
                signal_type  = signal['signal_type']
                entry_price  = signal['entry_price']
                take_profit  = signal['take_profit']
                partial_tp   = signal.get('partial_tp')
                stop_loss    = signal['stop_loss']
                partial_hit  = signal.get('partial_tp_hit', False)
                
                # Get latest price for this asset
                latest_prices = self._fetch_query(conn, """
                    SELECT close, high, low FROM scrapes
                    WHERE name = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (asset_name,))
                
                if not latest_prices:
                    continue
                
                current_price = latest_prices[0]['close']
                candle_high = latest_prices[0].get('high') or current_price
                candle_low = latest_prices[0].get('low') or current_price
                is_long = 'LONG' in signal_type
                now = datetime.utcnow().isoformat()
                
                if is_long:
                    # ── Stage 1: Partial TP hit → move SL to breakeven ──
                    if partial_tp and not partial_hit and candle_high >= partial_tp:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET partial_tp_hit = TRUE, stop_loss = ?, updated_at = ?
                            WHERE id = ?
                        """, (entry_price, now, signal_id))
                        logger.info(f"Partial TP hit for {asset_name} LONG — SL moved to breakeven ({entry_price})")
                        stop_loss = entry_price  # Use updated SL for same-cycle check
                        partial_hit = True

                    # ── Stage 2: Full TP or SL ──
                    if candle_high >= take_profit:
                        self._execute_query(conn, """
                            UPDATE signals SET status = 'TP_HIT', updated_at = ? WHERE id = ?
                        """, (now, signal_id))
                    elif candle_low <= stop_loss:
                        status = 'BREAKEVEN' if partial_hit else 'SL_HIT'
                        self._execute_query(conn, """
                            UPDATE signals SET status = ?, updated_at = ? WHERE id = ?
                        """, (status, now, signal_id))

                else:  # SHORT
                    # ── Stage 1: Partial TP hit → move SL to breakeven ──
                    if partial_tp and not partial_hit and candle_low <= partial_tp:
                        self._execute_query(conn, """
                            UPDATE signals
                            SET partial_tp_hit = TRUE, stop_loss = ?, updated_at = ?
                            WHERE id = ?
                        """, (entry_price, now, signal_id))
                        logger.info(f"Partial TP hit for {asset_name} SHORT — SL moved to breakeven ({entry_price})")
                        stop_loss = entry_price
                        partial_hit = True

                    # ── Stage 2: Full TP or SL ──
                    if candle_low <= take_profit:
                        self._execute_query(conn, """
                            UPDATE signals SET status = 'TP_HIT', updated_at = ? WHERE id = ?
                        """, (now, signal_id))
                    elif candle_high >= stop_loss:
                        status = 'BREAKEVEN' if partial_hit else 'SL_HIT'
                        self._execute_query(conn, """
                            UPDATE signals SET status = ?, updated_at = ? WHERE id = ?
                        """, (status, now, signal_id))
    
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
                SELECT s1.* 
                FROM scrapes s1
                JOIN (
                    SELECT name, timeframe, MAX(timestamp) as max_ts
                    FROM scrapes
                    GROUP BY name, timeframe
                ) s2 
                ON s1.name = s2.name 
                AND s1.timeframe = s2.timeframe 
                AND s1.timestamp = s2.max_ts
            """)

    def get_latest_for_asset(self, asset_name):
        """Get latest scrape for a single asset (all timeframes)"""
        with self.get_connection() as conn:
            return self._fetch_query(conn, """
                SELECT s1.* 
                FROM scrapes s1
                JOIN (
                    SELECT name, timeframe, MAX(timestamp) as max_ts
                    FROM scrapes
                    WHERE name = ?
                    GROUP BY name, timeframe
                ) s2 
                ON s1.name = s2.name 
                AND s1.timeframe = s2.timeframe 
                AND s1.timestamp = s2.max_ts
            """, (asset_name,))
    
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

    def save_screenshot(self, asset_name, timeframe, image_bytes):
        """Save asset screenshot to DB"""
        from datetime import datetime
        with self.get_connection() as conn:
            # Upsert logic handled manually or via helper
            if USE_POSTGRES:
                query = """
                    INSERT INTO screenshots (asset_name, timeframe, image_data, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (asset_name, timeframe) 
                    DO UPDATE SET image_data = EXCLUDED.image_data, updated_at = EXCLUDED.updated_at
                """
            else:
                query = """
                    INSERT OR REPLACE INTO screenshots (asset_name, timeframe, image_data, updated_at)
                    VALUES (?, ?, ?, ?)
                """
            
            self._execute_query(conn, query, (
                asset_name, timeframe, image_bytes, datetime.utcnow().isoformat()
            ))

    def get_screenshot(self, asset_name, timeframe):
        """Get screenshot bytes and metadata from DB"""
        with self.get_connection() as conn:
            cursor = self._execute_query(conn, """
                SELECT image_data, updated_at FROM screenshots 
                WHERE asset_name = ? AND timeframe = ?
            """, (asset_name, timeframe))
            row = cursor.fetchone()
            
            if row:
                if isinstance(row, tuple):
                    return {'image_data': row[0], 'updated_at': row[1]}
                else:
                    return {'image_data': row['image_data'], 'updated_at': row['updated_at']}
            return None

    def save_signal_image(self, signal_id, image_bytes):
        """Save signal screenshot to DB"""
        with self.get_connection() as conn:
            if USE_POSTGRES:
                query = """
                    INSERT INTO signal_images (signal_id, image_data)
                    VALUES (?, ?)
                    ON CONFLICT (signal_id) DO UPDATE SET image_data = EXCLUDED.image_data
                """
            else:
                query = """
                    INSERT OR REPLACE INTO signal_images (signal_id, image_data)
                    VALUES (?, ?)
                """
                 
            self._execute_query(conn, query, (signal_id, image_bytes))

    def get_signal_image(self, signal_id):
        """Get signal screenshot bytes from DB"""
        with self.get_connection() as conn:
            cursor = self._execute_query(conn, """
                SELECT image_data FROM signal_images 
                WHERE signal_id = ?
            """, (signal_id,))
            row = cursor.fetchone()
            if row:
                return row[0] if isinstance(row, tuple) else row['image_data']
            return None
