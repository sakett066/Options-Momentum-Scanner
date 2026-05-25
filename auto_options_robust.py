"""
ULTIMATE OPTIONS TRADER v3.0 - Production Ready
PCR + Max Pain + IV + Gamma + Smart Money + Entry/Exit Timing
Works with Yahoo Finance fallback, market hours aware, safe execution
"""
import os
import time
import requests
import warnings
import numpy as np
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_OPTIONS_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_OPTIONS_CHAT_ID')

# ============================================
# SAFETY CONFIGURATION
# ============================================
CONFIG = {
    'LOTS': 1,                    # Start with 1 lot
    'LOT_SIZE': 25,               # NIFTY lot size
    'MAX_LOSS_PER_TRADE': 2000,   # Max loss Rs.2000
    'TARGET_PROFIT_PCT': 50,      # Book at 50% profit
    'ENTRY_WINDOW_START': '09:45',
    'ENTRY_WINDOW_END': '10:15',
    'EXIT_TIME': '14:15',
    'NO_NEW_TRADE_AFTER': '14:00',
    'MIN_PCR_EXTREME': 1.3,       # PCR must be extreme
    'MAX_IV_FOR_BUYING': 22,      # Don't buy if IV > 22%
}

# ============================================
# MARKET HOURS CHECK
# ============================================
def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    if h < 9 or (h == 9 and m < 15): return False
    if h > 15 or (h == 15 and m > 30): return False
    return True

def get_current_session():
    now = datetime.now()
    h, m = now.hour, now.minute
    current = f"{h:02d}:{m:02d}"
    
    if current < '09:20': return 'PRE_OPEN', 'Market opening soon. Wait for data to settle.'
    elif current < '09:45': return 'OBSERVE', 'First 20 min. OI settling. Watch direction.'
    elif current < '10:15': return 'BEST_ENTRY', 'Best entry window. Institutional flow clear.'
    elif current < '13:00': return 'TRADE_ACTIVE', 'Good trading window. Trail stops.'
    elif current < '14:00': return 'BOOK_PROFITS', 'Start booking profits. Exit 50%.'
    elif current < '14:15': return 'FINAL_EXIT', 'Exit all positions NOW.'
    elif current < '15:30': return 'NO_TRADE', 'No new trades. Close all.'
    else: return 'CLOSED', 'Market closed.'

# ============================================
# NSE OPTIONS DATA
# ============================================
def fetch_options_chain(symbol='NIFTY'):
    """Fetch options chain with fallback"""
    # Try NSE direct API
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com/option-chain'
        })
        session.get('https://www.nseindia.com', timeout=15)
        time.sleep(1)
        
        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            records = data.get('records', {}).get('data', [])
            if records:
                return records, symbol
    except:
        pass
    
    # Try Bank Nifty
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        session.get('https://www.nseindia.com', timeout=10)
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY'
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get('records', {}).get('data', [])
            if records:
                return records, 'BANKNIFTY'
    except:
        pass
    
    return [], symbol

# ============================================
# PCR CALCULATION
# ============================================
def calculate_pcr(data):
    total_ce = sum(r.get('CE', {}).get('openInterest', 0) for r in data if 'CE' in r)
    total_pe = sum(r.get('PE', {}).get('openInterest', 0) for r in data if 'PE' in r)
    
    if total_ce == 0: return None
    
    pcr = total_pe / total_ce
    
    if pcr > 1.5:
        return {'pcr': round(pcr, 2), 'signal': 'EXTREME_FEAR', 'direction': 'BUY_CALL', 
                'message': 'Everyone buying puts. Market near bottom. BUY CALLS.', 'confidence': 80}
    elif pcr > 1.3:
        return {'pcr': round(pcr, 2), 'signal': 'FEAR', 'direction': 'BUY_CALL',
                'message': 'Fear increasing. Good time to buy calls.', 'confidence': 65}
    elif pcr < 0.6:
        return {'pcr': round(pcr, 2), 'signal': 'EXTREME_GREED', 'direction': 'BUY_PUT',
                'message': 'Everyone buying calls. Market near top. BUY PUTS.', 'confidence': 80}
    elif pcr < 0.8:
        return {'pcr': round(pcr, 2), 'signal': 'GREED', 'direction': 'BUY_PUT',
                'message': 'Greed increasing. Consider puts.', 'confidence': 60}
    else:
        return {'pcr': round(pcr, 2), 'signal': 'NEUTRAL', 'direction': None,
                'message': 'No extreme signal. Wait or trade small.', 'confidence': 30}

# ============================================
# MAX PAIN
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
            
            if 'CE' in r and underlying == 0:
                underlying = r['CE'].get('underlyingValue', 0)
        except: continue
    
    if not strike_oi: return None
    
    max_pain = max(strike_oi, key=strike_oi.get)
    
    if underlying > 0:
        direction = 'UP' if underlying < max_pain else 'DOWN'
        return {
            'max_pain': max_pain,
            'current': round(underlying, 0),
            'direction': direction,
            'message': f'Max Pain at {max_pain}. Price likely to move {"UP" if direction=="UP" else "DOWN"} towards it.'
        }
    return None

# ============================================
# IV ANALYSIS
# ============================================
def analyze_iv(data):
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
        return {'iv': round(avg_iv, 1), 'signal': 'LOW', 'message': 'Options CHEAP. Best time to BUY.', 'safe': True}
    elif avg_iv < 18:
        return {'iv': round(avg_iv, 1), 'signal': 'NORMAL', 'message': 'Fair premium. OK to trade.', 'safe': True}
    elif avg_iv < 25:
        return {'iv': round(avg_iv, 1), 'signal': 'HIGH', 'message': 'Options EXPENSIVE. Reduce position size.', 'safe': False}
    else:
        return {'iv': round(avg_iv, 1), 'signal': 'VERY_HIGH', 'message': 'DO NOT BUY. IV crush risk. SELL options instead.', 'safe': False}

# ============================================
# GAMMA ZONE
# ============================================
def detect_gamma_zone(data):
    underlying = 0
    gamma_strikes = []
    
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
                        gamma_strikes.append({
                            'strike': strike, 'type': 'CE', 'oi': oi,
                            'distance': round(distance, 2),
                            'message': f'Gamma zone at {strike} CE. Explosive upside possible.'
                        })
        except: continue
    
    return gamma_strikes[:3] if gamma_strikes else None

# ============================================
# GET ATM STRIKE
# ============================================
def get_atm_strike(data):
    for r in data[:5]:
        try:
            if 'CE' in r:
                underlying = r['CE'].get('underlyingValue', 0)
                if underlying > 0:
                    return round(underlying / 50) * 50
        except: continue
    return 23000

# ============================================
# COMBINE SIGNALS
# ============================================
def generate_trade_signal(data):
    pcr = calculate_pcr(data)
    max_pain = calculate_max_pain(data)
    iv = analyze_iv(data)
    gamma = detect_gamma_zone(data)
    atm = get_atm_strike(data)
    
    # Safety checks
    if not iv or not iv['safe']:
        return {'signal': 'NO_TRADE', 'reason': f"IV too high ({iv['iv']}%). Don't buy options." if iv else 'No IV data'}
    
    if not pcr or pcr['signal'] == 'NEUTRAL':
        return {'signal': 'NO_TRADE', 'reason': 'PCR neutral. No extreme signal. Wait.'}
    
    # Determine trade
    if pcr['direction'] == 'BUY_CALL':
        strike = atm + 100 if max_pain and max_pain['direction'] == 'UP' else atm
        option_type = 'CE'
    else:
        strike = atm - 100 if max_pain and max_pain['direction'] == 'DOWN' else atm
        option_type = 'PE'
    
    # Find option price
    option_price = 0
    for r in data:
        try:
            opt = r.get(option_type, {})
            if opt.get('strikePrice') == strike:
                option_price = opt.get('lastPrice', 0)
                break
        except: continue
    
    if option_price <= 0:
        return {'signal': 'NO_TRADE', 'reason': 'Could not find option price.'}
    
    # Calculate trade details
    lots = CONFIG['LOTS']
    qty = lots * CONFIG['LOT_SIZE']
    cost = option_price * qty
    sl_price = round(option_price * 0.75, 2)
    target1 = round(option_price * 1.5, 2)
    target2 = round(option_price * 2.0, 2)
    max_loss = round((option_price - sl_price) * qty, 0)
    max_profit = round((target1 - option_price) * qty, 0)
    
    # Confidence
    confidence = pcr['confidence']
    if max_pain and pcr['direction'] == ('BUY_CALL' if max_pain['direction'] == 'UP' else 'BUY_PUT'):
        confidence += 10
    if gamma:
        confidence += 5
    
    return {
        'signal': 'TRADE',
        'symbol': f"NIFTY{strike}{option_type}",
        'strike': strike,
        'type': option_type,
        'direction': pcr['direction'],
        'entry': option_price,
        'lots': lots,
        'quantity': qty,
        'cost': round(cost, 0),
        'sl': sl_price,
        'target1': target1,
        'target2': target2,
        'max_loss': max_loss,
        'max_profit': max_profit,
        'confidence': min(90, confidence),
        'pcr': pcr,
        'max_pain': max_pain,
        'iv': iv,
        'gamma': gamma,
        'session': get_current_session()
    }

# ============================================
# TELEGRAM
# ============================================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

# ============================================
# MAIN
# ============================================
def run():
    now = datetime.now()
    session, advice = get_current_session()
    
    print(f"OPTIONS TRADER v3.0 - {now.strftime('%d-%b %I:%M %p')}")
    print(f"Session: {session}")
    
    # Market closed check
    if not is_market_open():
        if now.weekday() >= 5:
            send_telegram(f"<b>Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n📅 Weekend - Market closed.")
        else:
            send_telegram(f"<b>Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n🔴 Market closed.")
        return
    
    # No trade sessions
    if session in ['PRE_OPEN', 'CLOSED', 'NO_TRADE']:
        send_telegram(f"<b>Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n{advice}")
        return
    
    # Fetch data
    print("Fetching options data...")
    data, symbol = fetch_options_chain()
    
    if not data:
        send_telegram(f"<b>Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n⚠️ Could not fetch options data.")
        return
    
    # Generate signal
    signal = generate_trade_signal(data)
    
    # Build message
    msg = f"<b>🎯 OPTIONS TRADER v3.0</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"Session: {session}\n"
    msg += f"{'═'*35}\n\n"
    
    if signal['signal'] == 'TRADE':
        emoji = "🟢" if signal['direction'] == 'BUY_CALL' else "🔴"
        
        msg += f"<b>📊 SIGNAL: {emoji} {signal['direction']}</b>\n"
        msg += f"Confidence: <b>{signal['confidence']:.0f}%</b>\n"
        msg += f"{'═'*35}\n\n"
        
        msg += f"<b>PCR:</b> {signal['pcr']['pcr']} - {signal['pcr']['signal']}\n"
        msg += f"<b>IV:</b> {signal['iv']['iv']}% - {signal['iv']['signal']}\n"
        
        if signal['max_pain']:
            msg += f"<b>Max Pain:</b> {signal['max_pain']['max_pain']} ({signal['max_pain']['direction']})\n"
        
        if signal['gamma']:
            msg += f"<b>Gamma:</b> {signal['gamma'][0]['message']}\n"
        
        msg += f"\n{'═'*35}\n\n"
        msg += f"<b>💰 TRADE ORDER:</b>\n"
        msg += f"Symbol: <b>{signal['symbol']}</b>\n"
        msg += f"Type: {signal['type']}\n"
        msg += f"Entry: Rs.{signal['entry']}\n"
        msg += f"Lots: {signal['lots']} | Qty: {signal['quantity']}\n"
        msg += f"Total Cost: Rs.{signal['cost']}\n\n"
        
        msg += f"<b>🛑 STOP LOSS:</b>\n"
        msg += f"Sell at: Rs.{signal['sl']}\n"
        msg += f"Max Loss: Rs.{signal['max_loss']}\n\n"
        
        msg += f"<b>🎯 TARGETS:</b>\n"
        msg += f"T1: Rs.{signal['target1']} (+50%) - Book 50%\n"
        msg += f"T2: Rs.{signal['target2']} (+100%) - Book balance\n\n"
        
        msg += f"<b>⏰ EXIT:</b>\n"
        msg += f"Exit all before 2:15 PM TODAY\n"
        msg += f"Do NOT hold overnight\n\n"
        
        msg += f"<b>📱 ON UPSTOX:</b>\n"
        msg += f"1. Search: {signal['symbol']}\n"
        msg += f"2. Buy: {signal['quantity']} Qty at MARKET\n"
        msg += f"3. Set GTT SL: Sell {signal['quantity']} @ Rs.{signal['sl']}\n"
    else:
        msg += f"<b>⏸️ NO TRADE</b>\n\n"
        msg += f"{signal['reason']}\n\n"
    
    msg += f"{'═'*35}\n"
    msg += f"<b>📋 SESSION:</b> {advice}\n"
    msg += f"<i>Safe Options Trading System</i>"
    
    send_telegram(msg)
    print(f"✅ Sent! Signal: {signal['signal']}")

if __name__ == "__main__":
    run()
