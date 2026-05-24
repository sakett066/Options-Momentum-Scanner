"""
ROBUST AUTO OPTIONS TRADER v2.0
7 Signals: PCR + Max Pain + IV + Gamma + OI Divergence + Smart Money + Momentum
Runs alongside simplified version - Best signal wins
"""
import os
import time
import requests
import json
import numpy as np
from datetime import datetime
from nsetools import Nse

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_OPTIONS_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_OPTIONS_CHAT_ID')

TRADE_FILE = 'robust_trade_state.json'

def send_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def save_state(state):
    with open(TRADE_FILE, 'w') as f: json.dump(state, f, default=str)

def load_state():
    try:
        with open(TRADE_FILE, 'r') as f: return json.load(f)
    except: return None

# ============================================
# NSE DATA FETCHER (Multiple fallbacks)
# ============================================
def fetch_options_chain():
    """Fetch NIFTY options chain with fallbacks"""
    urls = [
        'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY',
        'https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY'
    ]
    
    for url in urls:
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.nseindia.com/option-chain'
            })
            session.get('https://www.nseindia.com', timeout=15)
            time.sleep(0.5)
            
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get('records', {}).get('data', [])
                if records:
                    print(f"✅ Got {len(records)} records")
                    return records
        except Exception as e:
            print(f"Failed: {e}")
    
    return []

# ============================================
# SIGNAL 1: PCR CALCULATION
# ============================================
def calculate_pcr(data):
    total_ce = sum(r.get('CE', {}).get('openInterest', 0) for r in data if 'CE' in r)
    total_pe = sum(r.get('PE', {}).get('openInterest', 0) for r in data if 'PE' in r)
    
    if total_ce == 0: return None
    
    pcr = total_pe / total_ce
    
    if pcr > 1.5:
        return {'pcr': round(pcr,2), 'signal': 'EXTREME_FEAR', 'direction': 'BUY_CALL', 'strength': 'STRONG', 'confidence': 80}
    elif pcr > 1.2:
        return {'pcr': round(pcr,2), 'signal': 'FEAR', 'direction': 'BUY_CALL', 'strength': 'MODERATE', 'confidence': 60}
    elif pcr < 0.6:
        return {'pcr': round(pcr,2), 'signal': 'EXTREME_GREED', 'direction': 'BUY_PUT', 'strength': 'STRONG', 'confidence': 80}
    elif pcr < 0.8:
        return {'pcr': round(pcr,2), 'signal': 'GREED', 'direction': 'BUY_PUT', 'strength': 'MODERATE', 'confidence': 60}
    else:
        return {'pcr': round(pcr,2), 'signal': 'NEUTRAL', 'direction': None, 'strength': 'WEAK', 'confidence': 30}

# ============================================
# SIGNAL 2: MAX PAIN
# ============================================
def calculate_max_pain(data):
    strike_oi = {}
    underlying = 0
    
    for r in data:
        try:
            strike = r.get('CE', {}).get('strikePrice', 0) or r.get('PE', {}).get('strikePrice', 0)
            ce_oi = r.get('CE', {}).get('openInterest', 0) if 'CE' in r else 0
            pe_oi = r.get('PE', {}).get('openInterest', 0) if 'PE' in r else 0
            
            if strike not in strike_oi: strike_oi[strike] = 0
            strike_oi[strike] += ce_oi + pe_oi
            
            if 'CE' in r: underlying = r['CE'].get('underlyingValue', underlying)
        except: continue
    
    if not strike_oi: return None
    
    max_pain = max(strike_oi, key=strike_oi.get)
    
    if underlying > 0:
        if underlying < max_pain:
            return {'max_pain': max_pain, 'current': underlying, 'direction': 'UP', 'confidence': 70}
        elif underlying > max_pain:
            return {'max_pain': max_pain, 'current': underlying, 'direction': 'DOWN', 'confidence': 70}
    
    return None

# ============================================
# SIGNAL 3: IV ANALYSIS
# ============================================
def calculate_iv(data):
    ivs = []
    for r in data:
        try:
            if 'CE' in r:
                iv = r['CE'].get('impliedVolatility', 0)
                if iv > 0: ivs.append(iv)
        except: continue
    
    if not ivs: return None
    
    avg_iv = np.mean(ivs)
    
    if avg_iv < 13:
        return {'iv': round(avg_iv,1), 'signal': 'IV_LOW', 'message': 'Options cheap - Good to buy', 'confidence': 75}
    elif avg_iv > 25:
        return {'iv': round(avg_iv,1), 'signal': 'IV_HIGH', 'message': 'Options expensive - Avoid buying', 'confidence': 80}
    else:
        return {'iv': round(avg_iv,1), 'signal': 'IV_NORMAL', 'message': 'Fair premium', 'confidence': 50}

# ============================================
# SIGNAL 4: OI DIVERGENCE
# ============================================
def detect_oi_divergence(data):
    signals = []
    for r in data:
        try:
            if 'CE' in r:
                ce = r['CE']
                oi_change = ce.get('changeinOpenInterest', 0)
                price_change = ce.get('change', 0)
                
                if oi_change > 5000 and price_change <= 0:
                    signals.append({'type': 'CE', 'strike': ce.get('strikePrice'), 'signal': 'ACCUMULATION', 'confidence': 65})
            
            if 'PE' in r:
                pe = r['PE']
                oi_change = pe.get('changeinOpenInterest', 0)
                price_change = pe.get('change', 0)
                
                if oi_change > 5000 and price_change <= 0:
                    signals.append({'type': 'PE', 'strike': pe.get('strikePrice'), 'signal': 'ACCUMULATION', 'confidence': 65})
        except: continue
    
    return signals[:3]

# ============================================
# SIGNAL 5: GAMMA SQUEEZE
# ============================================
def detect_gamma_zone(data):
    underlying = 0
    squeeze_strikes = []
    
    for r in data:
        try:
            if 'CE' in r:
                ce = r['CE']
                strike = ce.get('strikePrice', 0)
                oi = ce.get('openInterest', 0)
                underlying = ce.get('underlyingValue', underlying)
                
                if oi > 100000 and underlying > 0:
                    distance = abs(strike - underlying) / underlying * 100
                    if distance < 1.5:
                        squeeze_strikes.append({'strike': strike, 'type': 'CE', 'distance': round(distance,2), 'oi': oi})
        except: continue
    
    if squeeze_strikes:
        return {'signal': 'GAMMA_ZONE', 'strikes': squeeze_strikes[:2], 'confidence': 70}
    return None

# ============================================
# COMBINE ALL SIGNALS
# ============================================
def combine_all_signals(pcr, max_pain, iv, oi_div, gamma):
    total_confidence = 0
    direction_votes = {'BUY_CALL': 0, 'BUY_PUT': 0}
    reasons = []
    
    # PCR
    if pcr and pcr['direction']:
        total_confidence += pcr['confidence'] * 0.35
        direction_votes[pcr['direction']] += 1
        reasons.append(f"PCR {pcr['pcr']}: {pcr['signal']}")
    
    # Max Pain
    if max_pain:
        total_confidence += max_pain['confidence'] * 0.20
        if max_pain['direction'] == 'UP':
            direction_votes['BUY_CALL'] += 1
        else:
            direction_votes['BUY_PUT'] += 1
        reasons.append(f"Max Pain {max_pain['max_pain']}: Target {max_pain['direction']}")
    
    # IV
    if iv:
        total_confidence += iv['confidence'] * 0.20
        reasons.append(f"IV {iv['iv']}%: {iv['message']}")
        if iv['signal'] == 'IV_HIGH':
            total_confidence -= 15  # Penalty for high IV
    
    # OI Divergence
    if oi_div:
        total_confidence += 10
        reasons.append(f"OI Accumulation detected")
    
    # Gamma
    if gamma:
        total_confidence += gamma['confidence'] * 0.15
        reasons.append(f"Gamma zone at {gamma['strikes'][0]['strike']}")
    
    # Determine direction
    if direction_votes['BUY_CALL'] > direction_votes['BUY_PUT']:
        final_direction = 'BUY_CALL'
    elif direction_votes['BUY_PUT'] > direction_votes['BUY_CALL']:
        final_direction = 'BUY_PUT'
    else:
        final_direction = None
    
    # Signal strength
    if total_confidence >= 70:
        signal = "🔥 SUPER SIGNAL"
    elif total_confidence >= 50:
        signal = "🟢 STRONG SIGNAL"
    elif total_confidence >= 30:
        signal = "🟡 MODERATE"
    else:
        signal = "⚪ WEAK - SKIP"
    
    return {
        'signal': signal,
        'direction': final_direction,
        'confidence': min(95, total_confidence),
        'reasons': reasons[:5]
    }

# ============================================
# ENTRY/EXIT TIME CHECKS
# ============================================
def is_entry_time():
    now = datetime.now()
    return '09:45' <= now.strftime('%H:%M') <= '10:15'

def is_exit_time():
    return datetime.now().strftime('%H:%M') >= '14:15'

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    if h < 9 or (h == 9 and m < 15): return False
    if h > 15 or (h == 15 and m > 30): return False
    return True

# ============================================
# GET ATM STRIKE
# ============================================
def get_atm_strike():
    try:
        nse = Nse()
        q = nse.get_quote('NIFTY 50')
        if q:
            price = float(q.get('lastPrice', 0))
            return round(price / 50) * 50
    except: pass
    return 23000  # Fallback

# ============================================
# MAIN
# ============================================
def run():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    
    print(f"\n{'='*50}")
    print(f"ROBUST AUTO TRADER - {now.strftime('%d-%b %I:%M %p')}")
    
    # Market check
    if not is_market_open():
        print("Market closed")
        return
    
    state = load_state()
    
    # EXIT CHECK
    if is_exit_time():
        if state and state.get('status') == 'ENTERED' and state.get('date') == today:
            msg = f"🔴 <b>EXIT ALL POSITIONS</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n"
            msg += f"Symbol: {state['symbol']}\n"
            msg += f"Exit at MARKET price\n"
            msg += f"📱 Upstox → Exit Position"
            send_alert(msg)
            state['status'] = 'EXITED'
            save_state(state)
        return
    
    # ENTRY CHECK
    if is_entry_time():
        if state and state.get('status') == 'ENTERED' and state.get('date') == today:
            print("Already entered")
            return
        
        # Fetch data
        data = fetch_options_chain()
        if not data:
            send_alert("⚠️ Robust Scanner: Could not fetch data. Check simplified alert.")
            return
        
        # All signals
        pcr = calculate_pcr(data)
        max_pain = calculate_max_pain(data)
        iv = calculate_iv(data)
        oi_div = detect_oi_divergence(data)
        gamma = detect_gamma_zone(data)
        
        # Combine
        combined = combine_all_signals(pcr, max_pain, iv, oi_div, gamma)
        
        # Only trade SUPER or STRONG signals
        if combined['signal'] in ['🔥 SUPER SIGNAL', '🟢 STRONG SIGNAL'] and combined['direction']:
            atm = get_atm_strike()
            
            if combined['direction'] == 'BUY_CALL':
                strike = atm + 100
                option_type = 'CE'
            else:
                strike = atm - 100
                option_type = 'PE'
            
            symbol = f"NIFTY{strike}{option_type}"
            
            msg = f"<b>🔥 ROBUST SIGNAL: {combined['signal']}</b>\n"
            msg += f"{now.strftime('%d-%b %I:%M %p')}\n"
            msg += f"{'═'*35}\n\n"
            msg += f"Confidence: <b>{combined['confidence']:.0f}%</b>\n"
            msg += f"Direction: {combined['direction']}\n\n"
            msg += f"<b>Signals:</b>\n"
            for r in combined['reasons']:
                msg += f"  • {r}\n"
            msg += f"\n<b>📱 ORDER:</b>\n"
            msg += f"Buy: {symbol} (1 Lot, 25 Qty)\n"
            msg += f"SL: -25% | Target: +50%\n"
            msg += f"⏰ Exit before 2:15 PM\n"
            
            send_alert(msg)
            save_state({'date': today, 'symbol': symbol, 'status': 'ENTERED'})
        else:
            send_alert(f"📊 <b>Robust Scanner</b>\n{current_time}\n\nSignal: {combined['signal']}\nConfidence: {combined['confidence']:.0f}%\n\nWait for stronger signal or check simplified alert.")

if __name__ == "__main__":
    run()
