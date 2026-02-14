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
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    try:
        signals = detector.get_all_signals()
        
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
                    image_data = img_bytes
            
            if image_data:
                 with st.expander("📸 View Signal Chart"):
                     st.image(image_data, use_column_width=True, caption=f"Chart at Signal Generation ({signal['entry_time']})")
        
        st.divider()

def render_signal_history():
    """Render signal history table"""
    st.header("📊 Signal History")
    
    # Time range selector
    col1, col2 = st.columns([1, 3])
    with col1:
        hours = st.selectbox("Time Range", [6, 12, 24, 48, 72], index=2, key="history_hours")
    
    datastore = MangoDataStore()
    
    try:
        history = datastore.get_signal_history(hours=hours)
        
        if not history:
            st.info(f"No signals in the last {hours} hours")
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
                # Calculate time since entry
                try:
                    start = pd.to_datetime(row['entry_time'], format='mixed', utc=True)
                    now = pd.Timestamp.now(tz='UTC')
                    diff = now - start
                    hours = int(diff.total_seconds() // 3600)
                    mins = int((diff.total_seconds() % 3600) // 60)
                    return f"{hours}h {mins}m (Open)"
                except:
                    return "-"
            
            try:
                start = pd.to_datetime(row['entry_time'], format='mixed', utc=True)
                end = pd.to_datetime(row['updated_at'], format='mixed', utc=True)
                diff = end - start
                hours = int(diff.total_seconds() // 3600)
                mins = int((diff.total_seconds() % 3600) // 60)
                return f"{hours}h {mins}m"
            except:
                return "-"

        df['Duration'] = df.apply(calculate_duration, axis=1)

        # 4. P&L %
        def calculate_pnl(row):
            if row['status'] == 'TP_HIT':
                exit_price = row['take_profit']
            elif row['status'] == 'SL_HIT':
                exit_price = row['stop_loss']
            else:
                return None
            
            try:
                if 'LONG' in row['signal_type']:
                    pnl = (exit_price - row['entry_price']) / row['entry_price']
                else: # SHORT
                    pnl = (row['entry_price'] - exit_price) / row['entry_price']
                return round(pnl * 100, 2)
            except:
                return None

        df['PnL %'] = df.apply(calculate_pnl, axis=1)

        # Clean up Confidence
        df['confidence'] = df['confidence'].round(0).astype(int)
        
        # Select columns for display
        # Map raw column names to display names if needed, or just create new DF
        display_columns = [
            'Time', 'asset_name', 'signal_type', 'confidence',
            'entry_price', 'take_profit', 'stop_loss', 'status', 
            'Exit Time', 'Duration', 'PnL %'
        ]
        
        # Ensure columns exist (for robustness)
        available_cols = [c for c in display_columns if c in df.columns]
        display_df = df[available_cols].copy()
        
        # Rename for cleaner UI
        display_df.columns = [
            'Entry Time', 'Asset', 'Type', 'Conf', 
            'Entry', 'TP', 'SL', 'Status', 
            'Exit Time', 'Duration', 'PnL %'
        ]
        
        # Styling
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "PnL %": st.column_config.NumberColumn(
                    "PnL %",
                    format="%.2f%%",
                ),
            }
        )
        
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Signals", len(df))
        with col2:
            active_count = len(df[df['status'] == 'ACTIVE'])
            st.metric("Active", active_count)
        with col3:
            # Win Rate (TP vs SL)
            completed = df[df['status'].isin(['TP_HIT', 'SL_HIT'])]
            if not completed.empty:
                wins = len(completed[completed['status'] == 'TP_HIT'])
                win_rate = (wins / len(completed)) * 100
                st.metric("Win Rate", f"{win_rate:.0f}%")
            else:
                st.metric("Win Rate", "0%")
        with col4:
            # Total PnL
            total_pnl = df['PnL %'].sum()
            st.metric("Total PnL", f"{total_pnl:+.2f}%")
            
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
        latest_data = datastore.get_latest_for_all_assets()
        
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
                                return res['image_data']
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
            # Check database
            latest = datastore.get_latest_for_all_assets()
            if latest:
                last_scrape = latest[0]['timestamp']
                last_scrape_dt = datetime.fromisoformat(last_scrape.replace('Z', '+00:00'))
                time_since = datetime.now() - last_scrape_dt.replace(tzinfo=None)
                
                if time_since.total_seconds() < 1800:  # 30 minutes
                    st.success("✅ Scraper Active")
                else:
                    st.warning("⚠️ Scraper Delayed")
                
                st.caption(f"Last scrape: {time_since.seconds // 60}m ago")
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
    timeframes = ['3m', '15m', '1h', '4h', '12h', '1d', '4d']
    
    for i, asset in enumerate(assets):
        with cols[i % 2]:
            st.markdown(f"### {asset['name']}")
            
            for tf in timeframes:
                # Fetch screenshot from DB/Local
                # Ideally check DB for timestamp
                res = datastore.get_screenshot(asset['name'], tf)
                
                label = f"Timeframe: {tf}"
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
                
                with st.expander(label):
                    if res and isinstance(res, dict) and res.get('image_data'):
                        st.image(res['image_data'], use_column_width=True)
                        if updated_at_str:
                             st.caption(f"Last Scraped: {updated_at_str} EST")
                    else:
                        st.info("No screenshot data found")
            
            st.divider()

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
    tab1, tab2, tab3, tab4 = st.tabs(["🚨 Active Signals", "📊 History", "👁️ Assets", "📈 Dynamic Levels"])
    
    with tab1:
        render_active_signals()
    
    with tab2:
        render_signal_history()
    
    with tab3:
        render_asset_monitor(datastore)
    
    with tab4:
        render_dynamic_levels(datastore)
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(60)
        st.session_state.last_refresh = datetime.now()
        st.rerun()

if __name__ == "__main__":
    main()