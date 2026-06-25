import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector

def test_arb():
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    latest_data = datastore.get_latest_for_all_assets()
    assets_data = {}
    for row in latest_data:
        name = row['name']
        if name not in assets_data:
            assets_data[name] = {}
        assets_data[name][row['timeframe']] = row
        
    timeframes = assets_data.get('ARB')
    if not timeframes:
        print("No ARB data found!")
        return
        
    print("Evaluating ARB Swing Signal...")
    # Replicate _detect_swing_signal
    htf_tf, ltf_tf = '1d', '4h'
    htf_data = timeframes.get(htf_tf)
    ltf_data = timeframes.get(ltf_tf)
    
    htf_direction = detector._get_htf_direction(htf_data)
    print(f"HTF (1d) Direction: {htf_direction}")
    
    daily_data = timeframes.get('1d')
    weekly_data = timeframes.get('4d')
    
    daily_dir = detector._get_htf_direction(daily_data)
    weekly_dir = detector._get_htf_direction(weekly_data)
    print(f"Daily Direction: {daily_dir}, Weekly Direction: {weekly_dir}")
    
    ltf_direction = detector._get_htf_direction(ltf_data)
    print(f"LTF (4h) Direction: {ltf_direction}")
    
    ltf_entry = detector._check_ltf_entry(ltf_data, htf_direction)
    print(f"LTF Entry Valid: {ltf_entry['valid']}, Reason: {ltf_entry['reason']}")
    
    # Late entry / chase check
    ltf_price = ltf_data.get('close', 0)
    ltf_entry_up = ltf_data.get('entry_up', 0)
    ltf_entry_down = ltf_data.get('entry_down', 0)
    zone_width = ltf_entry_up - ltf_entry_down
    chase_buffer = max(zone_width * 1.5, ltf_price * 0.015)
    print(f"Chase Buffer: {chase_buffer}, ltf_price: {ltf_price}, boundary: {ltf_entry_down - chase_buffer}")
    is_chase = ltf_price < ltf_entry_down - chase_buffer
    print(f"Is Chase: {is_chase}")
    
    # Equilibrium check
    htf_eq = detector._check_equilibrium(htf_data, htf_direction)
    ltf_eq = detector._check_equilibrium(ltf_data, htf_direction)
    print(f"HTF Equilibrium Expanding: {htf_eq['expanding']}, Color: {htf_eq['color']}")
    print(f"LTF Equilibrium Expanding: {ltf_eq['expanding']}, Color: {ltf_eq['color']}")
    
    # Confidence
    confidence = detector._calculate_confidence(htf_data, ltf_data, is_swing=True, is_bounce=ltf_entry.get('is_bounce', False))
    print(f"Base Confidence: {confidence}")
    
    # TP/SL
    tp_sl = detector._calculate_tp_sl(
        entry_price=ltf_data['close'],
        direction=htf_direction,
        entry_zone_low=ltf_data['entry_down'],
        entry_zone_high=ltf_data['entry_up'],
        candle_low=ltf_data['low'],
        candle_high=ltf_data['high'],
        timeframe=ltf_tf,
        is_scalp=False,
        asset_type='crypto',
        asset_name='ARB',
        buffer_pct=0.025
    )
    print(f"TP/SL: {tp_sl}")
    
    if tp_sl:
        signal = {
            'asset_name': 'ARB',
            'asset_type': 'crypto',
            'signal_type': 'SWING_SHORT' if htf_direction == 'SHORT' else 'SWING_LONG',
            'confidence': confidence,
            'entry_price': ltf_data['close'],
            'take_profit': tp_sl['take_profit'],
            'partial_tp': tp_sl['partial_tp'],
            'stop_loss': tp_sl['stop_loss'],
            'rr_ratio': tp_sl['rr_ratio'],
            'entry_zone_low': ltf_data['entry_down'],
            'entry_zone_high': ltf_data['entry_up'],
            'htf': htf_tf,
            'ltf': ltf_tf
        }
        validated = detector._validate_mango_confluence('ARB', signal)
        print(f"Validated Signal: {validated}")

if __name__ == "__main__":
    test_arb()
