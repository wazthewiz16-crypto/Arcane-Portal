import pandas as pd
from typing import Dict, List
from backtester.backtest_engine import run_backtest

def run_optimization_sweep(df: pd.DataFrame, mapping: Dict[str, str], sweep_config: Dict) -> List[Dict]:
    """Run an exhaustive grid search parameter sweep.
    
    sweep_config:
      sl_buffers: List[float] (e.g. [0.005, 0.008, 0.012, 0.015])
      min_risk_pcts: List[float] (e.g. [0.015, 0.018, 0.022, 0.025])
      rr_ratios: List[float] (e.g. [1.5, 1.8, 2.0])
      aggressive_rr_ratios: List[float] (e.g. [2.0, 2.5, 3.0])
      use_dynamic_zone: List[bool] (e.g. [True, False])
    """
    sl_buffers = sweep_config.get('sl_buffers', [0.008, 0.012, 0.016])
    min_risk_pcts = sweep_config.get('min_risk_pcts', [0.018, 0.022])
    rr_ratios = sweep_config.get('rr_ratios', [1.5, 1.8, 2.0])
    aggressive_rr_ratios = sweep_config.get('aggressive_rr_ratios', [2.0, 2.5, 3.0])
    use_dynamic_zone = sweep_config.get('use_dynamic_zone', [True])
    
    results = []
    
    # Calculate total combinations
    total_combinations = (
        len(sl_buffers) *
        len(min_risk_pcts) *
        len(rr_ratios) *
        len(aggressive_rr_ratios) *
        len(use_dynamic_zone)
    )
    
    import logging
    logging.getLogger(__name__).info(f"Starting parameter sweep: {total_combinations} combinations to test...")
    
    for zone_flag in use_dynamic_zone:
        for buf in sl_buffers:
            for r_floor in min_risk_pcts:
                for rr in rr_ratios:
                    for agg_rr in aggressive_rr_ratios:
                        params = {
                            'sl_buffer': buf,
                            'min_risk_pct': r_floor,
                            'rr_ratio': rr,
                            'aggressive_rr_ratio': agg_rr,
                            'use_dynamic_zone': zone_flag,
                            'aggressive_lookback': 3,
                            'max_bars_held': 0
                        }
                        
                        metrics = run_backtest(df, mapping, params)
                        
                        results.append({
                            'sl_buffer': buf,
                            'min_risk_pct': r_floor,
                            'rr_ratio': rr,
                            'aggressive_rr_ratio': agg_rr,
                            'use_dynamic_zone': zone_flag,
                            'total_trades': metrics['total_trades'],
                            'win_rate_pct': metrics['win_rate_pct'],
                            'net_profit_r': metrics['net_profit_r'],
                            'profit_factor': metrics['profit_factor'],
                            'max_drawdown_r': metrics['max_drawdown_r'],
                            'net_profit_pct': metrics['net_profit_pct']
                        })
                        
    # Sort by Net Profit R (descending), then Profit Factor
    results_sorted = sorted(results, key=lambda x: (-x['net_profit_r'], -x['profit_factor']))
    return results_sorted
