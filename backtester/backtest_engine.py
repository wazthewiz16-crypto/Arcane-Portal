import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional

def map_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Robustly map CSV column headers case-insensitively and via substrings."""
    cols = {c: c.strip().lower() for c in df.columns}
    mapping = {}
    
    # 1. Map standard price fields
    for orig, clean in cols.items():
        if clean == 'time': mapping['time'] = orig
        elif clean == 'open': mapping['open'] = orig
        elif clean == 'high': mapping['high'] = orig
        elif clean == 'low': mapping['low'] = orig
        elif clean == 'close': mapping['close'] = orig
        elif clean == 'volume': mapping['volume'] = orig

    # 2. Prioritized indicator matching: search for "mutanabby" or "tk" first
    for orig, clean in cols.items():
        if 'mutanabby' in clean and 'buy' in clean:
            mapping['buy_sig'] = orig
            break
    if 'buy_sig' not in mapping:
        for orig, clean in cols.items():
            if clean in ['buy', 'buy_sig', 'buy_signal', 'buyop']:
                mapping['buy_sig'] = orig
                break

    for orig, clean in cols.items():
        if 'mutanabby' in clean and 'sell' in clean:
            mapping['sell_sig'] = orig
            break
    if 'sell_sig' not in mapping:
        for orig, clean in cols.items():
            if clean in ['sell', 'sell_sig', 'sell_signal']:
                mapping['sell_sig'] = orig
                break

    for orig, clean in cols.items():
        if 'tk' in clean and 'bull' in clean:
            mapping['tk_bull'] = orig
            break
    if 'tk_bull' not in mapping:
        for orig, clean in cols.items():
            if clean in ['tk_bull', 'tk_bull_cross', 'tk bull cross']:
                mapping['tk_bull'] = orig
                break

    for orig, clean in cols.items():
        if 'tk' in clean and 'bear' in clean:
            mapping['tk_bear'] = orig
            break
    if 'tk_bear' not in mapping:
        for orig, clean in cols.items():
            if clean in ['tk_bear', 'tk_bear_cross', 'tk bear cross']:
                mapping['tk_bear'] = orig
                break

    # 3. Map dynamic zones and boundaries
    for orig, clean in cols.items():
        if 'entry zone upper' in clean or 'entryzoneupper' in clean: mapping['zone_upper'] = orig
        elif 'entry zone lower' in clean or 'entryzonelower' in clean: mapping['zone_lower'] = orig
        elif 'mangod1' in clean: mapping['d1'] = orig
        elif 'mangod2' in clean: mapping['d2'] = orig
        
    return mapping

def load_data(file_path_or_buffer) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, str]]]:
    """Load backtesting CSV data, dynamically determining separator and mapping columns."""
    try:
        # Dynamically detect delimiter (handles tabs and commas)
        df = pd.read_csv(file_path_or_buffer, sep=None, engine='python')
        mapping = map_columns(df)
        
        # Verify required columns are mapped
        required = ['time', 'open', 'high', 'low', 'close']
        missing = [r for r in required if r not in mapping]
        if missing:
            raise ValueError(f"Missing required price columns: {missing}")
            
        # Clean numeric fields
        for key in ['open', 'high', 'low', 'close']:
            col_name = mapping[key]
            df[col_name] = pd.to_numeric(df[col_name].astype(str).str.replace(',', ''), errors='coerce')
            
        # Drop rows with invalid prices
        df = df.dropna(subset=[mapping['close']])
        
        # Sort by timestamp
        df = df.sort_values(by=mapping['time'])
        return df, mapping
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error loading backtest data: {e}")
        return None, None

def run_backtest(df: pd.DataFrame, mapping: Dict[str, str], params: Dict) -> Dict:
    """Run historical strategy simulation on the dataframe using parameters.
    
    Parameters:
      sl_buffer: float (e.g. 0.012 for 1.2% buffer on zone boundaries)
      min_risk_pct: float (e.g. 0.022 for 2.2% min risk floor)
      rr_ratio: float (e.g. 1.8 for standard R:R target)
      aggressive_rr_ratio: float (e.g. 2.5 for TK cross confluence target)
      aggressive_lookback: int (e.g. 3 bars to look back for TK cross)
      use_dynamic_zone: bool (if True, filters entries to be inside entry zones)
      max_bars_held: int (optional time-based exit, e.g. 48 bars)
    """
    sl_buffer = params.get('sl_buffer', 0.012)
    min_risk_pct = params.get('min_risk_pct', 0.022)
    rr_ratio = params.get('rr_ratio', 1.8)
    aggressive_rr_ratio = params.get('aggressive_rr_ratio', 2.5)
    aggressive_lookback = params.get('aggressive_lookback', 3)
    use_dynamic_zone = params.get('use_dynamic_zone', True)
    max_bars_held = params.get('max_bars_held', 0)
    
    records = df.to_dict('records')
    trades = []
    
    in_position = False
    position_type = None
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    entry_time = None
    entry_index = 0
    aggressive = False
    risk = 0.0
    
    for i, row in enumerate(records):
        # 1. Update active position first
        if in_position:
            high = row[mapping['high']]
            low = row[mapping['low']]
            close = row[mapping['close']]
            current_time = row[mapping['time']]
            
            if position_type == 'LONG':
                if high >= take_profit:
                    # TP Hit
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': take_profit,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'TP_HIT',
                        'r_return': aggressive_rr_ratio if aggressive else rr_ratio,
                        'percent_return': (take_profit - entry_price) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False
                elif low <= stop_loss:
                    # SL Hit
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': stop_loss,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'SL_HIT',
                        'r_return': -1.0,
                        'percent_return': (stop_loss - entry_price) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False
                elif max_bars_held and (i - entry_index) >= max_bars_held:
                    # Time limit reached
                    r_ret = (close - entry_price) / risk
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'LONG',
                        'entry_price': entry_price,
                        'exit_price': close,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'EXPIRED',
                        'r_return': r_ret,
                        'percent_return': (close - entry_price) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False
                    
            elif position_type == 'SHORT':
                if low <= take_profit:
                    # TP Hit
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': take_profit,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'TP_HIT',
                        'r_return': aggressive_rr_ratio if aggressive else rr_ratio,
                        'percent_return': (entry_price - take_profit) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False
                elif high >= stop_loss:
                    # SL Hit
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': stop_loss,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'SL_HIT',
                        'r_return': -1.0,
                        'percent_return': (entry_price - stop_loss) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False
                elif max_bars_held and (i - entry_index) >= max_bars_held:
                    # Time limit reached
                    r_ret = (entry_price - close) / risk
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'type': 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': close,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'result': 'EXPIRED',
                        'r_return': r_ret,
                        'percent_return': (entry_price - close) / entry_price * 100,
                        'aggressive': aggressive
                    })
                    in_position = False

        # 2. Check position entry if not in position
        if not in_position:
            buy_sig = row.get(mapping.get('buy_sig', ''))
            sell_sig = row.get(mapping.get('sell_sig', ''))
            close = row[mapping['close']]
            current_time = row[mapping['time']]
            
            # LONG Entry
            if buy_sig == 1:
                zone_lower = row.get(mapping.get('zone_lower', ''))
                zone_upper = row.get(mapping.get('zone_upper', ''))
                
                is_in_zone = True
                if use_dynamic_zone and zone_lower is not None and zone_upper is not None:
                    is_in_zone = zone_lower <= close <= zone_upper
                    
                if is_in_zone:
                    # Check TK Bull cross confluence (aggressive)
                    is_aggressive = False
                    if 'tk_bull' in mapping and mapping['tk_bull'] in row:
                        for idx in range(max(0, i - aggressive_lookback), i + 1):
                            if records[idx].get(mapping['tk_bull']) == 1:
                                is_aggressive = True
                                break
                                
                    # Calculate Stop Loss
                    # Natural stop below zone lower boundary
                    base_sl = zone_lower * (1 - sl_buffer) if zone_lower else close * (1 - 0.02)
                    # Enforce minimum risk floor
                    min_sl = close * (1 - min_risk_pct)
                    stop_loss = min(base_sl, min_sl)
                    
                    risk = close - stop_loss
                    if risk > 0:
                        current_rr = aggressive_rr_ratio if is_aggressive else rr_ratio
                        take_profit = close + (risk * current_rr)
                        
                        in_position = True
                        position_type = 'LONG'
                        entry_price = close
                        entry_time = current_time
                        entry_index = i
                        aggressive = is_aggressive
                        
            # SHORT Entry
            elif sell_sig == 1:
                zone_lower = row.get(mapping.get('zone_lower', ''))
                zone_upper = row.get(mapping.get('zone_upper', ''))
                
                is_in_zone = True
                if use_dynamic_zone and zone_lower is not None and zone_upper is not None:
                    is_in_zone = zone_lower <= close <= zone_upper
                    
                if is_in_zone:
                    # Check TK Bear cross confluence (aggressive)
                    is_aggressive = False
                    if 'tk_bear' in mapping and mapping['tk_bear'] in row:
                        for idx in range(max(0, i - aggressive_lookback), i + 1):
                            if records[idx].get(mapping['tk_bear']) == 1:
                                is_aggressive = True
                                break
                                
                    # Calculate Stop Loss
                    # Natural stop above zone upper boundary
                    base_sl = zone_upper * (1 + sl_buffer) if zone_upper else close * (1 + 0.02)
                    # Enforce minimum risk floor
                    min_sl = close * (1 + min_risk_pct)
                    stop_loss = max(base_sl, min_sl)
                    
                    risk = stop_loss - close
                    if risk > 0:
                        current_rr = aggressive_rr_ratio if is_aggressive else rr_ratio
                        take_profit = close - (risk * current_rr)
                        
                        in_position = True
                        position_type = 'SHORT'
                        entry_price = close
                        entry_time = current_time
                        entry_index = i
                        aggressive = is_aggressive

    return compile_metrics(trades)

def compile_metrics(trades: List[Dict]) -> Dict:
    """Compile and summarize trades into metrics and returns curve."""
    if not trades:
        return {
            'trades': [],
            'total_trades': 0,
            'win_rate_pct': 0.0,
            'net_profit_r': 0.0,
            'profit_factor': 0.0,
            'max_drawdown_r': 0.0,
            'net_profit_pct': 0.0
        }
        
    df_trades = pd.DataFrame(trades)
    
    total_trades = len(df_trades)
    winners = df_trades[df_trades['r_return'] > 0]
    losers = df_trades[df_trades['r_return'] <= 0]
    
    win_rate_pct = len(winners) / total_trades * 100
    net_profit_r = df_trades['r_return'].sum()
    
    # Profit factor: total gains / total losses
    gross_gains = winners['r_return'].sum()
    gross_losses = abs(losers['r_return'].sum())
    profit_factor = gross_gains / gross_losses if gross_losses > 0 else (gross_gains if gross_gains > 0 else 1.0)
    
    # Cumulative R-Returns and Drawdown curve
    df_trades['cum_r'] = df_trades['r_return'].cumsum()
    peak = df_trades['cum_r'].cummax()
    # If cum_r drops below peak, drawdown is peak - cum_r (measured in R)
    drawdowns = peak - df_trades['cum_r']
    max_drawdown_r = drawdowns.max()
    
    net_profit_pct = df_trades['percent_return'].sum()
    
    return {
        'trades': trades,
        'total_trades': total_trades,
        'win_rate_pct': round(win_rate_pct, 2),
        'net_profit_r': round(net_profit_r, 2),
        'profit_factor': round(profit_factor, 2),
        'max_drawdown_r': round(max_drawdown_r, 2),
        'net_profit_pct': round(net_profit_pct, 2)
    }
