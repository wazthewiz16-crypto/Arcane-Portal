"""Arcane Portal V2 - Streamlit Dashboard"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from config.assets import get_active_assets
from utils.logger import setup_logger

# Cached Data Functions
@st.cache_data(ttl=60)
def get_cached_active_signals():
    ds = MangoDataStore()
    return ds.get_active_signals()

@st.cache_data(ttl=600)
def get_cached_history(hours):
    ds = MangoDataStore()
    return ds.get_signal_history(hours=hours)

@st.cache_data(ttl=60)
def get_cached_latest_assets():
    ds = MangoDataStore()
    return ds.get_latest_for_all_assets()

# Setup logging
logger = setup_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="Arcane Portal V2",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .signal-card {
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 5px solid;
    }
    .signal-long {
        border-left-color: #00ff00;
        background-color: rgba(0, 255, 0, 0.05);
    }
    .signal-short {
        border-left-color: #ff0000;
        background-color: rgba(255, 0, 0, 0.05);
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True

def render_header():
    """Render dashboard header"""
    import pytz
    
    st.markdown('<h1 class="main-header">🔮 Arcane Portal V2</h1>', unsafe_allow_html=True)
    st.markdown("**Mango Dynamic Trading Signals** • Real-time signal detection and analysis")
    
    # Last update time (Convert to EST)
    est = pytz.timezone('America/New_York')
    utc = pytz.utc
    
    last_refresh = st.session_state.last_refresh
    # Handle naive datetime (assume UTC if server time)
    if last_refresh.tzinfo is None:
        last_refresh = utc.localize(last_refresh)
    
    est_time = last_refresh.astimezone(est)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.caption(f"Last updated: {est_time.strftime('%Y-%m-%d %I:%M:%S %p')} EST")
    with col2:
        if st.button("🔄 Refresh Now"):
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    with col3:
        st.session_state.auto_refresh = st.checkbox("Auto-refresh (60s)", value=st.session_state.auto_refresh, key="auto_refresh_cb")

def render_active_signals():
    """Render active trading signals"""
    st.header("🚨 Active Signals")
    
    # Get signals
    # Get active signals from DB (persistent)
    datastore = MangoDataStore()
    # detector = MangoSignalDetector(datastore) # Not needed for viewing
    
    try:
        signals = get_cached_active_signals()
        
        if not signals:
            st.info("No active signals at the moment. Waiting for setups...")
            return
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            signal_type_filter = st.selectbox(
                "Signal Type",
                ["All", "Swing", "Scalp"],
                key="signal_type_filter"
            )
        with col2:
            direction_filter = st.selectbox(
                "Direction",
                ["All", "Long", "Short"],
                key="direction_filter"
            )
        with col3:
            asset_type_filter = st.selectbox(
                "Asset Type",
                ["All", "Crypto", "TradFi"],
                key="asset_type_filter"
            )
        
        # Apply filters
        filtered_signals = signals
        if signal_type_filter != "All":
            filtered_signals = [s for s in filtered_signals if signal_type_filter.upper() in s['signal_type']]
        if direction_filter != "All":
            filtered_signals = [s for s in filtered_signals if direction_filter.upper() in s['signal_type']]
        if asset_type_filter != "All":
            filtered_signals = [s for s in filtered_signals if s['asset_type'] == asset_type_filter.lower()]
        
        st.caption(f"Showing {len(filtered_signals)} of {len(signals)} signals")
        
        # Display signals in cards
        for signal in filtered_signals:
            render_signal_card(signal)
            
    except Exception as e:
        st.error(f"Error loading signals: {e}")
        logger.error(f"Error in render_active_signals: {e}")

def render_signal_card(signal):
    """Render individual signal card"""
    from datetime import datetime
    import pytz
    
    # Determine card style
    is_long = 'LONG' in signal['signal_type']
    card_class = "signal-long" if is_long else "signal-short"
    
    # Signal type emoji
    if 'SWING' in signal['signal_type']:
        type_emoji = "🎯"
    else:
        type_emoji = "⚡"
    
    direction_emoji = "📈" if is_long else "📉"
    
    # Convert entry time to EST
    entry_time_utc = datetime.fromisoformat(signal['entry_time'].replace('Z', '+00:00'))
    est = pytz.timezone('America/New_York')
    entry_time_est = entry_time_utc.astimezone(est)
    
    # Determine decimal precision based on price
    entry_price = signal['entry_price']
    if entry_price < 1:
        decimals = 4  # Low price assets (ADA, etc.)
    elif entry_price < 100:
        decimals = 3  # Medium price assets (LINK, etc.)
    else:
        decimals = 2  # High price assets (BTC, ETH, etc.)
    
    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            st.markdown(f"### {type_emoji} {signal['asset_name']}")
            st.caption(f"{signal['signal_type'].replace('_', ' ')}")
            st.caption(f"⏰ {entry_time_est.strftime('%Y-%m-%d %I:%M %p EST')}")
        
        with col2:
            st.metric("Entry Price", f"${signal['entry_price']:.{decimals}f}")
            st.caption(f"Timeframes: {signal['htf']} → {signal['ltf']}")
        
        with col3:
            st.metric("Take Profit", f"${signal['take_profit']:.{decimals}f}", delta=f"+{((signal['take_profit'] - signal['entry_price']) / signal['entry_price'] * 100):.1f}%")
            st.metric("Stop Loss", f"${signal['stop_loss']:.{decimals}f}", delta=f"{((signal['stop_loss'] - signal['entry_price']) / signal['entry_price'] * 100):.1f}%")
        
        with col4:
            # Confidence gauge
            confidence = signal['confidence']
            if confidence >= 75:
                conf_color = "🟢"
            elif confidence >= 50:
                conf_color = "🟡"
            else:
                conf_color = "🟠"
            
            st.metric("Confidence", f"{confidence:.0f}%", delta=conf_color)
            st.caption(f"RR: {signal['rr_ratio']:.1f}:1")
        
        # Display Signal Screenshot
        import os
        signal_id = signal.get('id')
        if signal_id:
            # Try local first, then DB
            img_path = os.path.join("data", "screenshots", "signals", f"{signal_id}.png")
            
            image_data = None
            if os.path.exists(img_path):
                image_data = img_path
            else:
                # Fetch from DB
                from detection.datastore import MangoDataStore
                ds = MangoDataStore()
                img_bytes = ds.get_signal_image(signal_id)
                if img_bytes:
                    image_data = bytes(img_bytes)
            
            if image_data:
                 with st.expander("📸 View Signal Chart"):
                     st.image(image_data, use_column_width=True, caption=f"Chart at Signal Generation ({signal['entry_time']})")
        
        st.divider()

def render_signal_history():
    """Render signal history table"""
    st.header("📊 Signal History")

    # ── Time range selector ───────────────────────────────────────────────────
    RANGE_OPTIONS = {
        "Last 6 hours":  6,
        "Last 12 hours": 12,
        "Last 24 hours": 24,
        "Last 48 hours": 48,
        "Last 72 hours": 72,
        "Last 7 days":   7  * 24,
        "Last 14 days":  14 * 24,
        "Last 30 days":  30 * 24,
    }
    col1, col2 = st.columns([1, 3])
    with col1:
        range_label = st.selectbox(
            "Time Range",
            list(RANGE_OPTIONS.keys()),
            index=2,          # default = Last 24 hours
            key="history_hours_label"
        )
    hours = RANGE_OPTIONS[range_label]
    # ─────────────────────────────────────────────────────────────────────────

    datastore = MangoDataStore()

    try:
        history = get_cached_history(hours)

        # Fetch current prices for floating PnL
        current_prices = {}
        try:
            latest_scrapes = get_cached_latest_assets()
            for scrape in latest_scrapes:
                current_prices[scrape['name']] = scrape['close']
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")

        if not history:
            st.info(f"No signals in the {range_label.lower()}")
            return

        # Convert to DataFrame
        import pandas as pd
        df = pd.DataFrame(history)

        # Helper for timezone conversion
        import pytz
        from datetime import datetime

        def format_time_est(time_str):
            """Convert time string to EST"""
            try:
                if not time_str: return "-"
                dt = pd.to_datetime(time_str, format='mixed', utc=True)
                est = pytz.timezone('America/New_York')
                return dt.tz_convert(est).strftime('%m-%d %H:%M')
            except:
                return str(time_str)

        # 1. Start Time
        df['Time'] = df['entry_time'].apply(format_time_est)

        # 2. Exit Time
        def get_exit_time(row):
            if row['status'] in ['ACTIVE', 'CREATED']:
                return "-"
            return format_time_est(row['updated_at'])

        df['Exit Time'] = df.apply(get_exit_time, axis=1)

        # 3. Duration
        def calculate_duration(row):
            if row['status'] in ['ACTIVE', 'CREATED']:
                try:
                    start = pd.to_datetime(row['entry_time'], format='mixed', utc=True)
                    now = pd.Timestamp.now(tz='UTC')
                    diff = now - start
                    h = int(diff.total_seconds() // 3600)
                    m = int((diff.total_seconds() % 3600) // 60)
                    return f"{h}h {m}m (Open)"
                except:
                    return "-"
            try:
                start = pd.to_datetime(row['entry_time'], format='mixed', utc=True)
                end   = pd.to_datetime(row['updated_at'], format='mixed', utc=True)
                diff  = end - start
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                return f"{h}h {m}m"
            except:
                return "-"

        df['Duration'] = df.apply(calculate_duration, axis=1)

        # 4. P&L %
        def calculate_pnl(row):
            exit_price = None
            if row['status'] == 'TP_HIT':
                exit_price = row['take_profit']
            elif row['status'] == 'SL_HIT':
                exit_price = row['stop_loss']
            elif row['status'] in ['ACTIVE', 'CREATED']:
                exit_price = current_prices.get(row['asset_name'])
            if exit_price is None:
                return None
            try:
                if 'LONG' in row['signal_type']:
                    pnl = (exit_price - row['entry_price']) / row['entry_price']
                else:
                    pnl = (row['entry_price'] - exit_price) / row['entry_price']
                return round(pnl * 100, 2)
            except:
                return None

        df['PnL %'] = df.apply(calculate_pnl, axis=1)

        # Clean up Confidence
        df['confidence'] = df['confidence'].round(0).astype(int)

        # Format Timeframe
        def format_tf(row):
            htf = row.get('htf', '-')
            ltf = row.get('ltf', '-')
            return f"{htf} → {ltf}"

        df['TF'] = df.apply(format_tf, axis=1)

        # Select columns for display
        display_columns = [
            'Time', 'asset_name', 'signal_type', 'TF', 'confidence',
            'entry_price', 'take_profit', 'stop_loss', 'status',
            'Exit Time', 'Duration', 'PnL %'
        ]
        available_cols = [c for c in display_columns if c in df.columns]
        display_df = df[available_cols].copy()
        display_df.columns = [
            'Entry Time', 'Asset', 'Type', 'TF', 'Conf',
            'Entry', 'TP', 'SL', 'Status',
            'Exit Time', 'Duration', 'PnL %'
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "PnL %": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
            }
        )

        # ── Summary Stats ─────────────────────────────────────────────────────
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        completed = df[df['status'].isin(['TP_HIT', 'SL_HIT'])]
        wins      = len(completed[completed['status'] == 'TP_HIT'])
        win_rate  = (wins / len(completed) * 100) if not completed.empty else 0
        total_pnl = df['PnL %'].sum()

        with col1:
            st.metric("Total Signals", len(df))
        with col2:
            active_count = len(df[df['status'] == 'ACTIVE'])
            st.metric("Active", active_count)
        with col3:
            st.metric("Win Rate", f"{win_rate:.0f}%" if not completed.empty else "0%")
        with col4:
            st.metric("Total PnL", f"{total_pnl:+.2f}%")

        # ── Per-Type Breakdown (shown for ranges > 72h) ───────────────────────
        if hours > 72:
            st.subheader("🔍 Performance Breakdown by Signal Type")
            st.caption("Closed trades only (TP\_HIT / SL\_HIT). Active trades excluded.")

            breakdown_rows = []
            for sig_type in sorted(df['signal_type'].unique()):
                subset    = df[df['signal_type'] == sig_type]
                closed    = subset[subset['status'].isin(['TP_HIT', 'SL_HIT'])]
                tp        = len(closed[closed['status'] == 'TP_HIT'])
                sl        = len(closed[closed['status'] == 'SL_HIT'])
                total_cl  = tp + sl
                wr        = f"{tp/total_cl*100:.0f}%" if total_cl else "N/A"
                avg_conf  = round(subset['confidence'].mean(), 0) if len(subset) else 0
                pnl_sum   = subset['PnL %'].sum()
                breakdown_rows.append({
                    'Type':        sig_type,
                    'Total':       len(subset),
                    'Active':      len(subset[subset['status'] == 'ACTIVE']),
                    'TP':          tp,
                    'SL':          sl,
                    'Win Rate':    wr,
                    'Avg Conf':    f"{avg_conf:.0f}%",
                    'PnL Sum %':   round(pnl_sum, 2),
                })

            bdf = pd.DataFrame(breakdown_rows)
            st.dataframe(
                bdf,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PnL Sum %": st.column_config.NumberColumn("PnL Sum %", format="%.2f%%"),
                }
            )

            # ── Top / Worst assets ────────────────────────────────────────────
            st.subheader("🏆 Asset Performance")
            asset_rows = []
            for asset in sorted(df['asset_name'].unique()):
                subset   = df[df['asset_name'] == asset]
                closed   = subset[subset['status'].isin(['TP_HIT', 'SL_HIT'])]
                tp       = len(closed[closed['status'] == 'TP_HIT'])
                sl       = len(closed[closed['status'] == 'SL_HIT'])
                total_cl = tp + sl
                wr       = f"{tp/total_cl*100:.0f}%" if total_cl else "N/A"
                pnl_sum  = subset['PnL %'].sum()
                asset_rows.append({
                    'Asset':     asset,
                    'Signals':   len(subset),
                    'TP':        tp,
                    'SL':        sl,
                    'Win Rate':  wr,
                    'PnL Sum %': round(pnl_sum, 2),
                })

            adf = pd.DataFrame(asset_rows).sort_values('PnL Sum %', ascending=False)
            st.dataframe(
                adf,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PnL Sum %": st.column_config.NumberColumn("PnL Sum %", format="%.2f%%"),
                }
            )
        # ─────────────────────────────────────────────────────────────────────

    except Exception as e:
        st.error(f"Error loading history: {e}")
        logger.error(f"Error in render_signal_history: {e}")
        import traceback
        st.code(traceback.format_exc())


def render_asset_monitor(datastore=None):
    """Render asset monitoring section"""
    st.header("👁️ Asset Monitor")
    
    if not datastore:
        from detection.datastore import MangoDataStore
        datastore = MangoDataStore()
    
    assets = get_active_assets()
    
    try:
        latest_data = get_cached_latest_assets()
        
        # Group by asset with smart timeframe selection
        asset_data = {}
        for row in latest_data:
            name = row['name']
            if name not in asset_data:
                asset_data[name] = {'htf': None, 'ltf': None}
            
            tf = row['timeframe']
            
            # Smart categorization
            if tf in ['4d', '1d', '12h', '4h']:
                # Prioritize 4H for HTF view, otherwise take what's available
                current = asset_data[name]['htf']
                if not current or tf == '4h' or (tf == '1d' and current['timeframe'] != '4h'):
                    asset_data[name]['htf'] = row
            else:
                # Prioritize 15m for LTF view
                current = asset_data[name]['ltf']
                if not current or tf == '15m' or (tf == '1h' and current['timeframe'] != '15m'):
                    asset_data[name]['ltf'] = row
        
        # Display in grid
        cols = st.columns(3)
        for idx, asset in enumerate(assets):
            name = asset['name']
            data = asset_data.get(name, {})
            
            with cols[idx % 3]:
                with st.container():
                    st.subheader(f"{name}")
                    htf_row = data.get('htf')
                    ltf_row = data.get('ltf')
                    
                    htf_tf = htf_row.get('timeframe', 'HTF') if htf_row else 'HTF'
                    ltf_tf = ltf_row.get('timeframe', 'LTF') if ltf_row else 'LTF'
                    st.caption(f"{asset['type'].upper()} • {htf_tf}/{ltf_tf}")
                    
                    if ltf_row:
                        precision = asset.get('precision', 2)
                        price = ltf_row.get('close')
                        
                        if price is not None:
                            st.metric("Price", f"${price:,.{precision}f}")
                            
                            # Show if in entry zone
                            if ltf_row.get('entry_up') and ltf_row.get('entry_down'):
                                in_zone = ltf_row['entry_down'] <= price <= ltf_row['entry_up']
                                if in_zone:
                                    st.success("✅ In Entry Zone")
                                else:
                                    st.caption("Waiting for pullback")
                        else:
                            st.warning("Price data unavailable")
                    else:
                        st.caption("No recent data")
                    
                    # Chart Screenshots
                    with st.expander("📸 View Charts"):
                        import os
                        
                        def get_chart_image(asset, tf):
                            # Try local
                            path = os.path.join("data", "screenshots", f"{asset}_{tf}.png")
                            if os.path.exists(path): return path
                            # Try DB
                            res = datastore.get_screenshot(asset, tf)
                            # Handle current dict return (image_data, updated_at)
                            if res and isinstance(res, dict):
                                return bytes(res['image_data'])
                            return None

                        # HTF
                        htf_img = get_chart_image(name, htf_tf)
                        if htf_img:
                            st.caption(f"HTF ({htf_tf})")
                            st.image(htf_img, use_column_width=True)
                        
                        # LTF
                        ltf_img = get_chart_image(name, ltf_tf)
                        if ltf_img:
                            st.caption(f"LTF ({ltf_tf})")
                            st.image(ltf_img, use_column_width=True)
                        
                        if not htf_img and not ltf_img:
                            st.info("No screenshots available yet")

                    st.divider()
                    
    except Exception as e:
        st.error(f"Error loading asset data: {e}")
        logger.error(f"Error in render_asset_monitor: {e}")

def render_system_health():
    """Render system health section"""
    with st.sidebar:
        st.header("⚙️ System Health")
        
        datastore = MangoDataStore()
        
        try:
            import pytz
            # Check database
            latest = datastore.get_latest_for_all_assets()
            if latest:
                last_scrape = latest[0]['timestamp']
                last_scrape_dt = datetime.fromisoformat(last_scrape.replace('Z', '+00:00'))
                
                # Make timezone aware if it isn't
                if last_scrape_dt.tzinfo is None:
                    last_scrape_dt = pytz.utc.localize(last_scrape_dt)
                    
                time_since = datetime.now(pytz.utc) - last_scrape_dt
                
                total_minutes = int(time_since.total_seconds() // 60)
                
                if time_since.total_seconds() < 1800:  # 30 minutes
                    st.success("✅ Scraper Active")
                else:
                    st.warning("⚠️ Scraper Delayed")
                
                st.caption(f"Last scrape: {total_minutes}m ago")
            else:
                st.error("❌ No data")
            
            # Asset count
            assets = get_active_assets()
            st.metric("Tracked Assets", len(assets))
            
            # Signal count
            signals = datastore.get_active_signals()
            st.metric("Active Signals", len(signals))
            
        except Exception as e:
            st.error(f"Health check failed: {e}")

def render_dynamic_levels(datastore):
    """Render list of assets with expandable timeframe screenshots"""
    st.subheader("Dynamic Levels")
    
    # Get active assets
    from config.assets import get_active_assets
    assets = get_active_assets()
    
    # Layout: 2 Columns to save vertical space
    cols = st.columns(2)
    
    # Scraped timeframes (excluding 5m as it's not scraped)
    timeframes = ['15m', '1h', '4h', '12h', '1d', '4d']
    
    for i, asset in enumerate(assets):
        with cols[i % 2]:
            st.markdown(f"### {asset['name']}")
            
            # Fetch indicator data for trends (optimize DB calls)
            latest = datastore.get_latest_for_asset(asset['name'])
            scrapes_map = {r['timeframe']: r for r in latest} if latest else {}
            
            for tf in timeframes:
                # Fetch screenshot from DB/Local
                res = datastore.get_screenshot(asset['name'], tf)
                
                # Determine Trend (Prefer scraped, fallback to calc)
                scrape = scrapes_map.get(tf, {})
                trend_label = ""
                scraped_trend = scrape.get('trend')
                
                if scraped_trend:
                    # Use scraped value directly (Single Source of Truth)
                    t_lower = scraped_trend.lower()
                    if 'bullish' in t_lower:
                        trend_label = f" - 🟢 {scraped_trend}"
                    elif 'bearish' in t_lower:
                        trend_label = f" - 🔴 {scraped_trend}"
                    else:
                        trend_label = f" - ⚪ {scraped_trend}"
                elif scrape.get('close') and scrape.get('mango_d1') and scrape.get('mango_d2'):
                     # Fallback to calculation
                     p, d1, d2 = scrape['close'], scrape['mango_d1'], scrape['mango_d2']
                     if p > d2: trend_label = " - 🟢 Bullish (Calc)"
                     elif p < d1: trend_label = " - 🔴 Bearish (Calc)"
                     else: trend_label = " - ⚪ Neutral (Calc)"

                label = f"Timeframe: {tf}{trend_label}"
                updated_at_str = ""
                
                if res and isinstance(res, dict) and res.get('updated_at'):
                    # Parse timestamp for display
                    try:
                        dt = datetime.fromisoformat(res['updated_at'])
                        # Convert to EST for display consistency
                        import pytz
                        est = pytz.timezone('America/New_York')
                        if dt.tzinfo is None:
                             dt = pytz.utc.localize(dt)
                        dt_est = dt.astimezone(est)
                        updated_at_str = dt_est.strftime("%m-%d %H:%M")
                        label += f" (Updated {updated_at_str})"
                    except:
                        pass
                
def render_backtest_optimizer():
    """Render the Backtesting and Parameter Optimization Tab"""
    st.subheader("🧪 Trading Strategy Backtester & Parameter Sweep")
    
    # Define sub-tabs at the top level
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📊 Strategy Simulation", "⚡ Parameter Sweep (Grid Search)", "💾 Saved Backtests"])
    
    with sub_tab1:
        st.markdown("""
        Simulate historical trading performance of your **Mutanabby_AI** and **Mango Ribbon (TK Cross)** strategy.
        
        ### How to get the CSV data:
        1. Open your **TradingView chart** with the backtesting layout.
        2. Ensure the indicator style settings have **Mutanabby Buy/Sell** signals and **TK Bull/Bear crosses** visible/enabled for export.
        3. Click **Chart Menu** (top left/right) -> **Export chart data** -> Choose **UNIX timestamp** or **ISO time**.
        4. Save and upload it below.
        """)
        
        uploaded_file = st.file_uploader("Upload TradingView Export (CSV or Tab-Separated TXT)", type=["csv", "txt"], key="uploader_sim")
        
        if uploaded_file is not None:
            # Import engine locally
            from backtester.backtest_engine import load_data, run_backtest
            
            # Load the data
            df, mapping = load_data(uploaded_file)
            
            if df is None or not mapping:
                st.error("❌ Failed to parse the uploaded file. Please ensure it is a valid TradingView export with time, open, high, low, close columns.")
            else:
                st.success(f"✅ Successfully loaded **{len(df)}** rows of historical data.")
                
                # Show mapping
                with st.expander("🔍 Column Mapping & Data Preview"):
                    mapping_data = [{"Indicator Field": k, "CSV Column Name": v} for k, v in mapping.items()]
                    st.dataframe(pd.DataFrame(mapping_data))
                    st.markdown("First few rows:")
                    st.dataframe(df.head(5))
                    
                st.markdown("### Configure Backtest Parameters")
                col1, col2 = st.columns(2)
                with col1:
                    sl_buffer_pct = st.slider("Stop Loss Buffer (%)", min_value=0.0, max_value=5.0, value=1.2, step=0.1, help="Buffer distance below Zone Lower (for longs) or above Zone Upper (for shorts)")
                    min_risk_pct_val = st.slider("Minimum Risk Floor (%)", min_value=0.5, max_value=5.0, value=2.2, step=0.1, help="Minimum distance for SL to protect against too-tight stops")
                    rr_ratio_val = st.number_input("Baseline Take Profit R:R Ratio", min_value=0.5, max_value=10.0, value=1.8, step=0.1, help="Target risk-to-reward ratio for standard signal entries")
                with col2:
                    aggressive_rr_ratio_val = st.number_input("Aggressive Take Profit R:R Ratio (Confluence)", min_value=0.5, max_value=10.0, value=2.5, step=0.1, help="Target risk-to-reward ratio when TK Cross confluence exists")
                    aggressive_lookback_val = st.slider("TK Cross Confluence Lookback (candles)", min_value=0, max_value=10, value=3, help="Number of candles prior to Mutanabby signal to search for TK cross")
                    use_dynamic_zone_val = st.checkbox("Filter by Mango Dynamic Zone", value=True, help="Only entry signals that close within the Entry Zone Upper/Lower boundaries are executed")
                    max_bars_held_val = st.number_input("Max Bars Held (Time Exit, 0 to disable)", min_value=0, max_value=200, value=0, help="Force exit trades after this many bars regardless of TP/SL")

                # Run Backtest
                params = {
                    'sl_buffer': sl_buffer_pct / 100.0,
                    'min_risk_pct': min_risk_pct_val / 100.0,
                    'rr_ratio': rr_ratio_val,
                    'aggressive_rr_ratio': aggressive_rr_ratio_val,
                    'aggressive_lookback': aggressive_lookback_val,
                    'use_dynamic_zone': use_dynamic_zone_val,
                    'max_bars_held': max_bars_held_val
                }
                
                metrics = run_backtest(df, mapping, params)
                
                if metrics['total_trades'] == 0:
                    st.warning("⚠️ No trades were executed with the current parameters and data. Ensure your CSV has Mutanabby buy/sell signals.")
                else:
                    # Display metrics cards
                    st.markdown("### Simulation Results")
                    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
                    with m_col1:
                        st.metric("Total Trades", f"{metrics['total_trades']}")
                    with m_col2:
                        st.metric("Win Rate", f"{metrics['win_rate_pct']}%")
                    with m_col3:
                        st.metric("Net Profit (R)", f"{metrics['net_profit_r']} R")
                    with m_col4:
                        st.metric("Profit Factor", f"{metrics['profit_factor']}")
                    with m_col5:
                        st.metric("Max Drawdown (R)", f"{metrics['max_drawdown_r']} R")
                        
                    st.info(f"Cumulative percentage return of simulated trades: **{metrics['net_profit_pct']:.2f}%** (assuming fixed trade sizing)")

                    # Plot
                    trades_df = pd.DataFrame(metrics['trades'])
                    trades_df['trade_num'] = range(1, len(trades_df) + 1)
                    trades_df['cumulative_r'] = trades_df['r_return'].cumsum()
                    
                    st.markdown("#### Cumulative R-Return Curve")
                    st.line_chart(trades_df.set_index('trade_num')[['cumulative_r']])
                    
                    # Save block
                    st.markdown("### 💾 Save This Simulation Result")
                    save_col1, save_col2 = st.columns([3, 1])
                    with save_col1:
                        default_run_name = "BTC 1D Simulation"
                        try:
                            filename = uploaded_file.name.upper()
                            parts = filename.split('_')
                            asset = parts[1] if len(parts) > 1 else "BTC"
                            tf = parts[2].split(',')[0] if len(parts) > 2 else "1D"
                            asset = asset.split(',')[0].replace('USDT.P', '').replace('USDT', '')
                            default_run_name = f"{asset} {tf} Simulation"
                        except Exception:
                            pass
                        run_name_input = st.text_input("Configuration Name", value=default_run_name, key="save_run_name_sim")
                    with save_col2:
                        st.markdown("<div style='padding-top: 1.6rem;'></div>", unsafe_allow_html=True)
                        save_clicked = st.button("💾 Save Run", key="save_run_btn_sim")
                        
                    if save_clicked:
                        if not run_name_input.strip():
                            st.error("Please enter a valid configuration name.")
                        else:
                            try:
                                asset_name = "BTC"
                                tf_name = "1D"
                                filename = uploaded_file.name.upper()
                                if "_" in filename:
                                    parts = filename.split("_")
                                    asset_name = parts[1].split(",")[0].replace("USDT.P", "").replace("USDT", "")
                                    if len(parts) > 2:
                                        tf_name = parts[2].split("_")[0].split(",")[0]
                                tf_name = tf_name.replace(".CSV", "").replace(".TXT", "").strip()
                                
                                from detection.datastore import MangoDataStore
                                ds = MangoDataStore()
                                ds.save_backtest_run(
                                    run_name=run_name_input.strip(),
                                    asset_name=asset_name,
                                    timeframe=tf_name,
                                    parameters=params,
                                    metrics={
                                        'total_trades': metrics['total_trades'],
                                        'win_rate_pct': metrics['win_rate_pct'],
                                        'net_profit_r': metrics['net_profit_r'],
                                        'profit_factor': metrics['profit_factor'],
                                        'max_drawdown_r': metrics['max_drawdown_r'],
                                        'net_profit_pct': metrics['net_profit_pct']
                                    }
                                )
                                st.success(f"✅ Successfully saved backtest run '{run_name_input.strip()}'!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to save run: {e}")
                    
                    # Detailed trade history
                    with st.expander("📜 View Detailed Trade Log"):
                        display_df = trades_df.copy()
                        try:
                            if pd.api.types.is_numeric_dtype(display_df['entry_time']):
                                display_df['entry_time'] = pd.to_datetime(display_df['entry_time'], unit='s', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
                            if pd.api.types.is_numeric_dtype(display_df['exit_time']):
                                display_df['exit_time'] = pd.to_datetime(display_df['exit_time'], unit='s', errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logger.warning(f"Error formatting timestamps in trade log: {e}")
                        
                        st.dataframe(display_df[[
                            'entry_time', 'exit_time', 'type', 'entry_price', 
                            'exit_price', 'stop_loss', 'take_profit', 'result', 
                            'r_return', 'percent_return', 'aggressive'
                        ]])
        else:
            st.info("💡 Please upload a TradingView CSV or TXT export file below to begin backtesting.")

    with sub_tab2:
        st.markdown("### Parameter Sweep Optimizer")
        st.write("Grid search sweeps will test multiple combinations of SL buffers, risk floors, and reward ratios to mathematically identify the highest-performing configurations.")
        
        uploaded_file_sweep = st.file_uploader("Upload TradingView Export (CSV or Tab-Separated TXT)", type=["csv", "txt"], key="uploader_sweep")
        
        if uploaded_file_sweep is not None:
            # Import engine locally
            from backtester.backtest_engine import load_data
            from backtester.parameter_optimizer import run_optimization_sweep
            
            # Load the data
            df, mapping = load_data(uploaded_file_sweep)
            
            if df is None or not mapping:
                st.error("❌ Failed to parse the uploaded file. Please ensure it is a valid TradingView export with time, open, high, low, close columns.")
            else:
                st.success(f"✅ Successfully loaded **{len(df)}** rows of historical data.")
                
                # Configure Sweep Ranges
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    sweep_sl_buffers = st.multiselect("SL Buffers to test (%)", options=[0.5, 0.8, 1.0, 1.2, 1.5, 2.0], default=[0.8, 1.2, 1.5], help="Percentage buffer added to the dynamic zone borders.")
                    sweep_min_risk = st.multiselect("Min Risk Floors to test (%)", options=[1.5, 1.8, 2.2, 2.5, 3.0], default=[1.8, 2.2], help="Protects against tiny risk calculations causing extremely tight stops.")
                    sweep_zone_filter = st.multiselect("Filter by Zone", options=[True, False], default=[True])
                with col_s2:
                    sweep_rr = st.multiselect("Baseline R:R to test", options=[1.2, 1.5, 1.8, 2.0, 2.2], default=[1.5, 1.8, 2.0])
                    sweep_agg_rr = st.multiselect("Aggressive R:R to test", options=[2.0, 2.5, 3.0, 3.5], default=[2.5, 3.0])
                    
                sweep_button = st.button("🚀 Run Parameter Sweep")
                
                if sweep_button:
                    if not sweep_sl_buffers or not sweep_min_risk or not sweep_rr or not sweep_agg_rr:
                        st.error("Please select at least one value for each parameter range.")
                    else:
                        sweep_config = {
                            'sl_buffers': [b / 100.0 for b in sweep_sl_buffers],
                            'min_risk_pcts': [r / 100.0 for r in sweep_min_risk],
                            'rr_ratios': sweep_rr,
                            'aggressive_rr_ratios': sweep_agg_rr,
                            'use_dynamic_zone': sweep_zone_filter
                        }
                        
                        with st.spinner("Running parameter sweeps... This may take a few moments."):
                            sweep_results = run_optimization_sweep(df, mapping, sweep_config)
                            
                        st.success(f"Sweep complete! Tested {len(sweep_results)} configurations.")
                        
                        # Convert to dataframe for display
                        sweep_df = pd.DataFrame(sweep_results)
                        # Convert back to percent for user-friendly table
                        sweep_df['sl_buffer (%)'] = sweep_df['sl_buffer'] * 100.0
                        sweep_df['min_risk_pct (%)'] = sweep_df['min_risk_pct'] * 100.0
                        
                        display_cols = [
                            'sl_buffer (%)', 'min_risk_pct (%)', 'rr_ratio', 
                            'aggressive_rr_ratio', 'use_dynamic_zone', 'total_trades', 
                            'win_rate_pct', 'net_profit_r', 'profit_factor', 'max_drawdown_r'
                        ]
                        
                        st.markdown("#### Top 10 Configurations (Sorted by Net Profit R)")
                        st.dataframe(sweep_df[display_cols].head(10))
                        
                        # Detailed results
                        with st.expander("View Full Sweep Results"):
                            st.dataframe(sweep_df[display_cols])
        else:
            st.info("💡 Please upload a TradingView CSV or TXT export file below to begin parameter sweep optimization.")

    with sub_tab3:
        st.markdown("### 💾 Saved Backtest Runs")
        st.write("Review your historical backtesting configurations and compare their performance side-by-side.")
        
        from detection.datastore import MangoDataStore
        ds = MangoDataStore()
        saved_runs = ds.get_backtest_runs()
        
        if not saved_runs:
            st.info("No saved backtest runs found. Run a simulation and save it to see it listed here.")
        else:
            # 1. Comparison section
            st.markdown("#### 🔍 Compare Saved Configurations")
            
            run_options = {f"{r['run_name']} ({r['asset_name']} {r['timeframe']}) - {r['metrics'].get('net_profit_r', 0.0)} R": r for r in saved_runs}
            selected_compare_labels = st.multiselect(
                "Select configurations to compare side-by-side:",
                options=list(run_options.keys()),
                default=list(run_options.keys())[:2] if len(run_options) >= 2 else list(run_options.keys())
            )
            
            if selected_compare_labels:
                compare_data = []
                for label in selected_compare_labels:
                    run = run_options[label]
                    p = run['parameters']
                    m = run['metrics']
                    compare_data.append({
                        "Run Name": run['run_name'],
                        "Asset": run['asset_name'],
                        "Timeframe": run['timeframe'],
                        "Net Profit (R)": f"{m.get('net_profit_r', 0.0)} R",
                        "Net Profit (%)": f"{m.get('net_profit_pct', 0.0):.2f}%",
                        "Win Rate": f"{m.get('win_rate_pct', 0.0)}%",
                        "Profit Factor": m.get('profit_factor', 1.0),
                        "Max Drawdown (R)": f"{m.get('max_drawdown_r', 0.0)} R",
                        "Total Trades": m.get('total_trades', 0),
                        "SL Buffer (%)": f"{p.get('sl_buffer', 0.0)*100.0:.2f}%",
                        "Min Risk Floor (%)": f"{p.get('min_risk_pct', 0.0)*100.0:.2f}%",
                        "Baseline R:R": p.get('rr_ratio', 1.8),
                        "Aggressive R:R": p.get('aggressive_rr_ratio', 2.5),
                        "Zone Filtered": "Yes" if p.get('use_dynamic_zone', True) else "No",
                        "Max Bars Held": p.get('max_bars_held', 0),
                        "Date Run (UTC)": run['created_at'].split('T')[0]
                    })
                
                st.dataframe(pd.DataFrame(compare_data).set_index("Run Name"))
                
            st.divider()
            
            # 2. List & Management section
            st.markdown("#### ⚙️ Manage Saved Runs")
            
            runs_list = []
            for r in saved_runs:
                m = r['metrics']
                runs_list.append({
                    "ID": r['id'],
                    "Run Name": r['run_name'],
                    "Asset": r['asset_name'],
                    "TF": r['timeframe'],
                    "Trades": m.get('total_trades', 0),
                    "Win Rate": f"{m.get('win_rate_pct', 0.0)}%",
                    "Net R": f"{m.get('net_profit_r', 0.0)} R",
                    "Profit Factor": m.get('profit_factor', 1.0),
                    "Date Saved": r['created_at'].replace('T', ' ').split('.')[0]
                })
            
            st.dataframe(pd.DataFrame(runs_list).set_index("ID"))
            
            # Delete configuration
            delete_col1, delete_col2 = st.columns([3, 1])
            with delete_col1:
                delete_options = {f"{r['run_name']} (ID: {r['id']})": r['id'] for r in saved_runs}
                to_delete_label = st.selectbox("Select run to delete:", options=list(delete_options.keys()))
            with delete_col2:
                st.markdown("<div style='padding-top: 1.6rem;'></div>", unsafe_allow_html=True)
                delete_clicked = st.button("🗑️ Delete Run", type="secondary")
                
            if delete_clicked:
                run_id = delete_options[to_delete_label]
                try:
                    ds.delete_backtest_run(run_id)
                    st.success(f"🗑️ Successfully deleted saved run '{to_delete_label}'!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete saved run: {e}")

def main():
    """Main dashboard function"""
    
    # Initialize Datastore for Dashboard
    # Using simple connection pooling via new instance
    from detection.datastore import MangoDataStore
    datastore = MangoDataStore()
    
    # Render header
    render_header()
    
    # Render system health in sidebar
    render_system_health()
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚨 Active Signals", "📊 History", "👁️ Assets", "📈 Dynamic Levels", "🧪 Backtest Optimizer"])
    
    with tab1:
        render_active_signals()
    
    with tab2:
        render_signal_history()
    
    with tab3:
        render_asset_monitor(datastore)
    
    with tab4:
        render_dynamic_levels(datastore)
        
    with tab5:
        render_backtest_optimizer()
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(60)
        st.session_state.last_refresh = datetime.now()
        st.rerun()

if __name__ == "__main__":
    main()