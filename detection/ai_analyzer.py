"""
Arcane Portal - AI Multi-Timeframe Chart Analyzer Engine
=========================================================
Analyzes multi-timeframe TradingView & Mango scrape data for a requested asset across 
7 timeframes (1W, 4D, 1D, 12H, 4H, 1H, 15m). Evaluates trend grids, confluences, 
contradictions/negatives, formulates a trade plan, and rates the overall setup.
"""

import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger("AIAnalyzer")


class AssetChartAnalyzer:
    def __init__(self, datastore=None):
        self.datastore = datastore

    def analyze_asset_chart(self, asset_name: str, timeframes_data: Dict[str, Dict]) -> Dict:
        """
        Analyze multi-timeframe chart data and return a structured diagnostic report.
        """
        tf_order = ['1w', '4d', '2d', '1d', '12h', '4h', '1h', '15m']
        grid = {}
        confluences = []
        contradictions = []
        
        long_votes = 0
        short_votes = 0
        neutral_votes = 0
        
        # 1. Build Multi-Timeframe Trend Grid & Count Votes
        for tf in tf_order:
            tf_data = timeframes_data.get(tf)
            if not tf_data:
                grid[tf] = {'trend': 'NO_DATA', 'mutanabby': 'None', 'tk_cross': 'None'}
                continue
                
            close = tf_data.get('close', 0.0)
            d1 = tf_data.get('mango_d1', 0.0)
            d2 = tf_data.get('mango_d2', 0.0)
            e_up = tf_data.get('entry_up', 0.0)
            e_down = tf_data.get('entry_down', 0.0)
            trend_str = str(tf_data.get('trend') or '')
            m_sig = tf_data.get('mutanabby_sig')
            
            # Trend direction resolution:
            # 1. Price position relative to Entry Zone Upper/Lower
            # 2. Price position relative to Mango Ribbon D1/D2
            if close > 0 and e_up > 0 and e_down > 0:
                if close > e_up:
                    t_dir = 'BULLISH'
                    long_votes += 1
                elif close < e_down:
                    t_dir = 'BEARISH'
                    short_votes += 1
                else:
                    t_dir = 'NEUTRAL'
                    neutral_votes += 1
            elif close > 0 and d1 > 0 and d2 > 0:
                ribbon_top = max(d1, d2)
                ribbon_bottom = min(d1, d2)
                if close > ribbon_top:
                    t_dir = 'BULLISH'
                    long_votes += 1
                elif close < ribbon_bottom:
                    t_dir = 'BEARISH'
                    short_votes += 1
                else:
                    t_dir = 'NEUTRAL'
                    neutral_votes += 1
            else:
                if 'Bull' in trend_str or 'LONG' in trend_str:
                    t_dir = 'BULLISH'
                    long_votes += 1
                elif 'Bear' in trend_str or 'SHORT' in trend_str:
                    t_dir = 'BEARISH'
                    short_votes += 1
                else:
                    t_dir = 'NEUTRAL'
                    neutral_votes += 1
                    
            # TK Cross resolution
            tk_val = tf_data.get('tk_cross', 0.0)
            if tk_val == 1.0:
                tk_label = '🟢 Bull Cross'
                confluences.append(f"🟢 **{tf.upper()} Mango TK Bull Cross**")
            elif tk_val == -1.0:
                tk_label = '🔴 Bear Cross'
                confluences.append(f"🔴 **{tf.upper()} Mango TK Bear Cross**")
            else:
                tk_label = 'None'
                
            grid[tf] = {'trend': t_dir, 'tk_cross': tk_label}

        # --- Mango Dashboard Integration ---
        mango_dash_info = {}
        if self.datastore:
            try:
                with self.datastore.get_connection() as conn:
                    m_rows = self.datastore._fetch_query(conn, """
                        SELECT market_trend, market_volatility, assets_json
                        FROM mango_scrapes
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """)
                    if m_rows:
                        row = m_rows[0]
                        m_trend = str(row.get('market_trend', 'NEUTRAL')).upper()
                        m_vol = float(row.get('market_volatility', 50.0))
                        assets_json = row.get('assets_json')
                        asset_trend = 'NEUTRAL'
                        asset_vol = 50.0
                        
                        if assets_json:
                            import json
                            try:
                                assets = json.loads(assets_json)
                                a_data = assets.get(asset_name.upper(), {})
                                asset_trend = str(a_data.get('trend', 'NEUTRAL')).upper()
                                asset_vol = float(a_data.get('volatility', 50.0))
                            except Exception:
                                pass
                                
                        mango_dash_info = {
                            'market_trend': m_trend,
                            'market_volatility': m_vol,
                            'asset_trend': asset_trend,
                            'asset_volatility': asset_vol
                        }
            except Exception as me:
                logger.warning(f"Failed to fetch Mango Dashboard data in AI Analyzer: {me}")

        # Mango Dashboard Confluences
        if mango_dash_info.get('asset_trend') == 'LONG':
            confluences.append(f"🥭 **Mango Dashboard Confluence:** {asset_name.upper()} is flagged **LONG** on Mango Dashboard.")
        elif mango_dash_info.get('asset_trend') == 'SHORT':
            confluences.append(f"🥭 **Mango Dashboard Confluence:** {asset_name.upper()} is flagged **SHORT** on Mango Dashboard.")

        # --- Trend & Ribbon Confluences ---
        if long_votes == 7:
            confluences.append("🟢 **Full 7-Timeframe Bullish Ribbon Alignment** (1W through 15m all BULLISH)")
        elif long_votes >= 5:
            confluences.append(f"🟢 **Strong Multi-Timeframe Bullish Consensus** ({long_votes}/7 Timeframes BULLISH)")
        elif short_votes == 7:
            confluences.append("🔴 **Full 7-Timeframe Bearish Ribbon Alignment** (1W through 15m all BEARISH)")
        elif short_votes >= 5:
            confluences.append(f"🔴 **Strong Multi-Timeframe Bearish Consensus** ({short_votes}/7 Timeframes BEARISH)")

        # Macro + Intraday Alignment
        w1_dir = grid.get('1w', {}).get('trend')
        d1_dir = grid.get('1d', {}).get('trend')
        h4_dir = grid.get('4h', {}).get('trend')
        if w1_dir == 'BULLISH' and d1_dir == 'BULLISH' and h4_dir == 'BULLISH':
            confluences.append("🟢 **HTF & LTF Trend Confluence:** 1W Weekly, 1D Daily, and 4H ribbons are perfectly aligned BULLISH.")
        elif w1_dir == 'BEARISH' and d1_dir == 'BEARISH' and h4_dir == 'BEARISH':
            confluences.append("🔴 **HTF & LTF Trend Confluence:** 1W Weekly, 1D Daily, and 4H ribbons are perfectly aligned BEARISH.")

        # 2. Detect Contradictions & Negatives
        if w1_dir in ['BEARISH'] and h4_dir in ['BULLISH']:
            contradictions.append("⚠️ **Macro vs Intraday Clash:** 1W Weekly chart is BEARISH while 4H is BULLISH (counter-trend rally risk).")
        elif w1_dir in ['BULLISH'] and h4_dir in ['BEARISH']:
            contradictions.append("⚠️ **Macro vs Intraday Clash:** 1W Weekly chart is BULLISH while 4H is BEARISH (pullback against macro trend).")
            
        if d1_dir in ['BEARISH'] and h4_dir in ['BULLISH']:
            contradictions.append("⚠️ **1D / 4H Divergence:** 1D Daily trend is BEARISH while 4H is BULLISH (chop zone).")
        elif d1_dir in ['BULLISH'] and h4_dir in ['BEARISH']:
            contradictions.append("⚠️ **1D / 4H Divergence:** 1D Daily trend is BULLISH while 4H is BEARISH (dip-buy vs short conflict).")

        # Check opposing Mutanabby signals
        m_4h = grid.get('4h', {}).get('mutanabby')
        m_1d = grid.get('1d', {}).get('mutanabby')
        if 'Buy' in m_4h and 'Sell' in m_1d:
            contradictions.append("⚠️ **Mutanabby Divergence:** 4H Mutanabby BUY clashes with lagging 1D Mutanabby SELL.")
        elif 'Sell' in m_4h and 'Buy' in m_1d:
            contradictions.append("⚠️ **Mutanabby Divergence:** 4H Mutanabby SELL clashes with lagging 1D Mutanabby BUY.")

        # Check Overextension with explicit timeframe tag
        ltf_tf_name = '4H'
        ltf_ref = timeframes_data.get('4h') or timeframes_data.get('1h') or timeframes_data.get('15m')
        if timeframes_data.get('4h'): ltf_tf_name = '4H'
        elif timeframes_data.get('1h'): ltf_tf_name = '1H'
        elif timeframes_data.get('15m'): ltf_tf_name = '15m'

        price = 0.0
        e_up = 0.0
        e_down = 0.0
        if ltf_ref:
            price = ltf_ref.get('close', 0.0)
            e_up = ltf_ref.get('entry_up', 0.0)
            e_down = ltf_ref.get('entry_down', 0.0)
            
            if price > 0 and e_up > 0 and e_down > 0:
                zone_w = e_up - e_down
                if price > e_up + (zone_w * 0.5):
                    contradictions.append(f"⚠️ **Price Overextended ({ltf_tf_name} Timeframe):** Current price (${price:.2f}) is running >50% past upper {ltf_tf_name} entry zone limit (${e_up:.2f}). Expect pullback before entry.")
                elif price < e_down - (zone_w * 0.5):
                    contradictions.append(f"⚠️ **Price Overextended ({ltf_tf_name} Timeframe):** Current price (${price:.2f}) is running >50% below lower {ltf_tf_name} entry zone limit (${e_down:.2f}). Expect bounce before entry.")

        # 3. Determine Overall Direction Bias & Setup Score
        if long_votes >= 4 and short_votes <= 2:
            direction = 'LONG'
            base_score = 65 + (long_votes * 5)
        elif short_votes >= 4 and long_votes <= 2:
            direction = 'SHORT'
            base_score = 65 + (short_votes * 5)
        else:
            direction = 'NO_TRADE'
            base_score = 40.0
            contradictions.append("⚠️ **Heavy Timeframe Chop:** Equal distribution of Bullish and Bearish timeframes.")

        # Add/subtract score bonuses
        score = base_score
        if len(confluences) >= 2: score += 10.0
        if len(contradictions) >= 2: score -= 15.0
        score = max(10.0, min(99.0, score))

        # Assign Tier
        if score >= 85:
            tier = "🏆 Tier A+ Ultra Setup"
        elif score >= 72:
            tier = "🟢 Tier A High Conviction"
        elif score >= 60:
            tier = "🟡 Tier B Standard Setup"
        else:
            tier = "🔴 NO TRADE (High Risk / Conflict)"

        # 4. Formulate Suggested Trade Plan with explicit Anchor Timeframe
        plan = {}
        if direction in ['LONG', 'SHORT'] and price > 0 and e_up > 0 and e_down > 0:
            if direction == 'LONG':
                entry_price = price
                sl = e_down * 0.985
                risk = entry_price - sl
                if risk > 0:
                    tp1 = entry_price + (risk * 1.2)
                    tp2 = entry_price + (risk * 2.5)
                    plan = {
                        'direction': 'LONG',
                        'entry': entry_price,
                        'sl': sl,
                        'tp1': tp1,
                        'tp2': tp2,
                        'rr': 2.5,
                        'anchor_tf': ltf_tf_name
                    }
            else:  # SHORT
                entry_price = price
                sl = e_up * 1.015
                risk = sl - entry_price
                if risk > 0:
                    tp1 = entry_price - (risk * 1.2)
                    tp2 = entry_price - (risk * 2.5)
                    plan = {
                        'direction': 'SHORT',
                        'entry': entry_price,
                        'sl': sl,
                        'tp1': tp1,
                        'tp2': tp2,
                        'rr': 2.5,
                        'anchor_tf': ltf_tf_name
                    }

        return {
            'asset': asset_name.upper(),
            'direction': direction,
            'score': round(score, 1),
            'tier': tier,
            'grid': grid,
            'mango_dashboard': mango_dash_info,
            'confluences': confluences if confluences else ["None detected"],
            'contradictions': contradictions if contradictions else ["None — smooth timeframe alignment!"],
            'trade_plan': plan
        }
