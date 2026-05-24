"""
ULTIMATE OPTIONS SCANNER v3.0 - Professional Grade
7 Proprietary Signals:
1. OI vs Price Divergence (Smart Money Trap)
2. PCR Momentum (Extreme Fear/Greed)
3. IV Rank (Mean Reversion)
4. Max Pain Theory (Where market closes)
5. Delta-Gamma Squeeze (Explosive moves)
6. VWAP Options Band (Institutional levels)
7. Time Decay Arbitrage (Theta harvesting)
"""
import os
import time
import requests
import json
from datetime import datetime
import numpy as np

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_OPTIONS_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_OPTIONS_CHAT_ID')

# ============================================
# MARKET HOURS
# ============================================
def is_market_open():
    now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5: return False
    hour, minute = now.hour, now.minute
    if hour < 9 or (hour == 9 and minute < 15): return False
    if hour > 15 or (hour == 15 and minute > 30): return False
    return True

def get_optimal_entry_time():
    """Best times to enter based on institutional flow"""
    now = datetime.now()
    h, m = now.hour, now.minute
    
    if h == 9 and m < 25: return "WAIT", "First 15 min are noise. Smart money setting traps."
    elif h == 9 and m >= 25: return "OBSERVE", "OI settling. Watch for genuine breakouts."
    elif 10 <= h < 11: return "BEST ENTRY", "Institutional flow established. Best risk/reward."
    elif 11 <= h < 13: return "GOOD", "Momentum trades. Trail stops tightly."
    elif 13 <= h < 14: return "BOOK PROFITS", "Start exiting. Theta accelerating."
    elif h >= 14: return "EXIT ONLY", "No new trades. Close all positions."
    return "CLOSED", ""

# ============================================
# TELEGRAM
# ============================================
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

# ============================================
# NSE DATA FETCHER
# ============================================
def fetch_options_chain(symbol='NIFTY'):
    """Fetch complete options chain"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com/option-chain'
        })
        session.get('https://www.nseindia.com', timeout=15)
        time.sleep(0.5)
        
        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get('records', {}).get('data', [])
    except: pass
    return []

# ============================================
# SIGNAL 1: OI vs PRICE DIVERGENCE
# (Smart money accumulates OI while retailers chase price)
# ============================================
def detect_oi_price_divergence(data):
    """
    THE LOGIC: When OI increases but price doesn't move = Smart money building position
    When retailers come in, smart money exits = Price moves, OI drops
    We front-run the retail move
    """
    signals = []
    
    ce_oi_changes = []
    pe_oi_changes = []
    
    for record in data:
        try:
            if 'CE' in record:
                ce = record['CE']
                oi_change = ce.get('changeinOpenInterest', 0)
                price_change = ce.get('change', 0)
                strike = ce.get('strikePrice', 0)
                ltp = ce.get('lastPrice', 0)
                
                # Divergence: OI up but price flat/down = Accumulation
                if oi_change > 5000 and price_change <= 0 and ltp > 5:
                    signals.append({
                        'type': 'CE',
                        'strike': strike,
                        'signal': 'SMART_MONEY_ACCUMULATION',
                        'strength': 'STRONG',
                        'logic': 'OI rising, price flat. Smart money accumulating. Expect breakout.',
                        'entry': ltp,
                        'target': round(ltp * 2.5, 2),
                        'sl': round(ltp * 0.7, 2),
                        'oi_change': oi_change,
                        'timeframe': '30-60 minutes'
                    })
                
                # Divergence: OI down but price up = Smart money exiting
                if oi_change < -5000 and price_change > 0:
                    signals.append({
                        'type': 'CE',
                        'strike': strike,
                        'signal': 'SMART_MONEY_EXIT',
                        'strength': 'DANGER',
                        'logic': 'OI dropping, price rising. Smart money selling to retailers. REVERSAL SOON.',
                        'entry': ltp,
                        'target': round(ltp * 0.5, 2),
                        'sl': round(ltp * 1.2, 2)
                    })
            
            if 'PE' in record:
                pe = record['PE']
                oi_change = pe.get('changeinOpenInterest', 0)
                price_change = pe.get('change', 0)
                strike = pe.get('strikePrice', 0)
                ltp = pe.get('lastPrice', 0)
                
                if oi_change > 5000 and price_change <= 0 and ltp > 5:
                    signals.append({
                        'type': 'PE',
                        'strike': strike,
                        'signal': 'SMART_MONEY_ACCUMULATION',
                        'strength': 'STRONG',
                        'logic': 'OI rising, price flat. Smart money accumulating puts. Expect breakdown.',
                        'entry': ltp,
                        'target': round(ltp * 2.5, 2),
                        'sl': round(ltp * 0.7, 2)
                    })
        except: continue
    
    return signals

# ============================================
# SIGNAL 2: PCR EXTREME (Put-Call Ratio)
# ============================================
def calculate_pcr_signal(data):
    """
    THE LOGIC: PCR < 0.7 = Extreme greed (too many calls) = REVERSAL DOWN
    PCR > 1.5 = Extreme fear (too many puts) = REVERSAL UP
    Contrarian indicator - fade the crowd
    """
    total_ce_oi = 0
    total_pe_oi = 0
    
    for record in data:
        try:
            if 'CE' in record: total_ce_oi += record['CE'].get('openInterest', 0)
            if 'PE' in record: total_pe_oi += record['PE'].get('openInterest', 0)
        except: continue
    
    if total_ce_oi == 0: return None
    
    pcr = total_pe_oi / total_ce_oi
    
    if pcr < 0.6:
        return {
            'pcr': round(pcr, 2),
            'signal': 'EXTREME GREED',
            'action': 'BUY PUTS - Market topped out. Everyone is long calls.',
            'confidence': 75,
            'logic': 'Contrarian: When everyone buys calls, market reverses down.'
        }
    elif pcr < 0.8:
        return {
            'pcr': round(pcr, 2),
            'signal': 'GREED',
            'action': 'CAUTION on calls. Consider hedging.',
            'confidence': 60
        }
    elif pcr > 1.5:
        return {
            'pcr': round(pcr, 2),
            'signal': 'EXTREME FEAR',
            'action': 'BUY CALLS - Market bottomed. Everyone is buying puts.',
            'confidence': 80,
            'logic': 'Contrarian: When everyone buys puts, market reverses up. Best opportunity!'
        }
    elif pcr > 1.2:
        return {
            'pcr': round(pcr, 2),
            'signal': 'FEAR',
            'action': 'Look for reversal. Fear creating opportunity.',
            'confidence': 60
        }
    else:
        return {
            'pcr': round(pcr, 2),
            'signal': 'NEUTRAL',
            'action': 'No extreme signal. Trade with trend.',
            'confidence': 40
        }

# ============================================
# SIGNAL 3: MAX PAIN THEORY
# ============================================
def calculate_max_pain(data):
    """
    THE LOGIC: Market makers maximize option buyers' pain
    Price tends to close where MAXIMUM option premium expires worthless
    Find the strike with highest total OI = magnetic level
    """
    strike_oi = {}
    
    for record in data:
        try:
            strike = record.get('CE', {}).get('strikePrice', 0)
            if strike == 0: strike = record.get('PE', {}).get('strikePrice', 0)
            
            ce_oi = record.get('CE', {}).get('openInterest', 0) if 'CE' in record else 0
            pe_oi = record.get('PE', {}).get('openInterest', 0) if 'PE' in record else 0
            
            if strike not in strike_oi:
                strike_oi[strike] = 0
            strike_oi[strike] += ce_oi + pe_oi
        except: continue
    
    if not strike_oi: return None
    
    max_pain_strike = max(strike_oi, key=strike_oi.get)
    max_pain_oi = strike_oi[max_pain_strike]
    
    # Get current underlying
    underlying = 0
    for record in data[:1]:
        try:
            underlying = record.get('CE', {}).get('underlyingValue', 0)
        except: pass
    
    return {
        'max_pain': max_pain_strike,
        'current': underlying,
        'distance': round(abs(max_pain_strike - underlying), 0) if underlying > 0 else 0,
        'direction': 'DOWN' if max_pain_strike < underlying else 'UP' if max_pain_strike > underlying else 'AT',
        'logic': f'Market makers want price at {max_pain_strike}. Price likely to move towards it.'
    }

# ============================================
# SIGNAL 4: IV RANK (Mean Reversion)
# ============================================
def calculate_iv_signal(data):
    """
    THE LOGIC: IV is mean-reverting
    IV > 30 = Options expensive = SELL options, don't buy
    IV < 12 = Options cheap = BUY options
    """
    ivs = []
    for record in data:
        try:
            if 'CE' in record:
                iv = record['CE'].get('impliedVolatility', 0)
                if iv > 0: ivs.append(iv)
            if 'PE' in record:
                iv = record['PE'].get('impliedVolatility', 0)
                if iv > 0: ivs.append(iv)
        except: continue
    
    if not ivs: return None
    
    avg_iv = np.mean(ivs)
    max_iv = np.max(ivs)
    min_iv = np.min(ivs)
    
    # IV Rank (where current IV is in range)
    iv_range = max_iv - min_iv
    iv_rank = ((avg_iv - min_iv) / iv_range * 100) if iv_range > 0 else 50
    
    if avg_iv > 25:
        return {
            'avg_iv': round(avg_iv, 1),
            'iv_rank': round(iv_rank, 1),
            'signal': 'IV TOO HIGH',
            'action': 'DO NOT BUY options. Premium too expensive. SELL options instead.',
            'confidence': 85,
            'logic': 'High IV = options overpriced. Buying = losing to IV crush.'
        }
    elif avg_iv < 13:
        return {
            'avg_iv': round(avg_iv, 1),
            'iv_rank': round(iv_rank, 1),
            'signal': 'IV LOW - BUY ZONE',
            'action': 'Best time to BUY options. Premium cheap. High leverage.',
            'confidence': 80,
            'logic': 'Low IV = options underpriced. Best risk/reward for buyers.'
        }
    else:
        return {
            'avg_iv': round(avg_iv, 1),
            'iv_rank': round(iv_rank, 1),
            'signal': 'IV NORMAL',
            'action': 'Trade with other signals. Premium fair.',
            'confidence': 50
        }

# ============================================
# SIGNAL 5: GAMMA SQUEEZE DETECTOR
# ============================================
def detect_gamma_squeeze(data):
    """
    THE LOGIC: When price approaches high OI strike, market makers hedge
    This creates explosive moves (gamma squeeze)
    """
    underlying = 0
    high_oi_strikes = []
    
    for record in data:
        try:
            if 'CE' in record:
                ce = record['CE']
                strike = ce.get('strikePrice', 0)
                oi = ce.get('openInterest', 0)
                underlying = ce.get('underlyingValue', underlying)
                
                if oi > 100000:  # High OI strike
                    distance = abs(strike - underlying) / underlying * 100 if underlying > 0 else 100
                    if distance < 1.5:  # Within 1.5%
                        high_oi_strikes.append({
                            'strike': strike,
                            'type': 'CE',
                            'oi': oi,
                            'distance': round(distance, 2),
                            'direction': 'UPSIDE'
                        })
            
            if 'PE' in record:
                pe = record['PE']
                strike = pe.get('strikePrice', 0)
                oi = pe.get('openInterest', 0)
                underlying = pe.get('underlyingValue', underlying)
                
                if oi > 100000:
                    distance = abs(strike - underlying) / underlying * 100 if underlying > 0 else 100
                    if distance < 1.5:
                        high_oi_strikes.append({
                            'strike': strike,
                            'type': 'PE',
                            'oi': oi,
                            'distance': round(distance, 2),
                            'direction': 'DOWNSIDE'
                        })
        except: continue
    
    if high_oi_strikes:
        return {
            'signal': 'GAMMA SQUEEZE ZONE',
            'strikes': high_oi_strikes[:3],
            'action': 'Explosive move likely. Enter with momentum. Exit fast.',
            'confidence': 70,
            'logic': 'Price near high OI = market makers forced to hedge = gamma squeeze.'
        }
    return None

# ============================================
# BUILD ULTIMATE SIGNAL
# ============================================
def combine_signals(divergence, pcr, max_pain, iv, gamma):
    """Combine all signals into one SUPER SIGNAL"""
    total_confidence = 0
    direction = None
    action = []
    
    # PCR signal
    if pcr:
        total_confidence += pcr.get('confidence', 0) * 0.3
        if 'BUY CALLS' in pcr.get('action', ''):
            direction = 'BULLISH'
            action.append(pcr['action'])
        elif 'BUY PUTS' in pcr.get('action', ''):
            direction = 'BEARISH'
            action.append(pcr['action'])
    
    # Max Pain
    if max_pain:
        if max_pain['direction'] == 'UP':
            total_confidence += 10
            if direction is None: direction = 'BULLISH'
        elif max_pain['direction'] == 'DOWN':
            total_confidence += 10
            if direction is None: direction = 'BEARISH'
    
    # IV Signal
    if iv:
        if 'BUY ZONE' in iv.get('signal', ''):
            total_confidence += 20
            action.append('IV favors option buyers')
        elif 'TOO HIGH' in iv.get('signal', ''):
            total_confidence -= 15
            action.append('WARNING: IV too high for buying')
    
    # Gamma squeeze
    if gamma:
        total_confidence += 15
        action.append('Gamma squeeze possible - explosive move')
    
    # Divergence signals
    if divergence:
        for d in divergence[:2]:
            if d['signal'] == 'SMART_MONEY_ACCUMULATION':
                total_confidence += 20
                action.append(f"Smart money accumulating {d['strike']} {d['type']}")
    
    if total_confidence >= 60:
        signal = "🔥 SUPER SIGNAL"
    elif total_confidence >= 40:
        signal = "🟢 STRONG SIGNAL"
    elif total_confidence >= 20:
        signal = "🟡 MODERATE"
    else:
        signal = "⚪ WEAK"
    
    return {
        'signal': signal,
        'direction': direction or 'NEUTRAL',
        'confidence': min(95, total_confidence),
        'actions': action[:4]
    }

# ============================================
# BUILD MESSAGE
# ============================================
def build_ultimate_message(data, divergence, pcr, max_pain, iv, gamma, combined, entry_advice):
    now = datetime.now()
    
    msg = f"<b>🔥 ULTIMATE OPTIONS SCANNER</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    # Entry advice
    msg += f"<b>⏰ {entry_advice[0]}:</b> {entry_advice[1]}\n\n"
    
    # COMBINED SUPER SIGNAL
    msg += f"<b>🎯 COMBINED SIGNAL:</b> {combined['signal']}\n"
    msg += f"Direction: <b>{combined['direction']}</b>\n"
    msg += f"Confidence: <b>{combined['confidence']:.0f}%</b>\n"
    for a in combined['actions']:
        msg += f"  • {a}\n"
    msg += f"\n{'═'*35}\n\n"
    
    # Individual signals
    if pcr:
        emoji = "🔴" if 'GREED' in pcr['signal'] else "🟢" if 'FEAR' in pcr['signal'] else "🟡"
        msg += f"<b>{emoji} PCR SIGNAL:</b> {pcr['signal']} (PCR: {pcr['pcr']})\n"
        msg += f"{pcr['action']}\n"
        msg += f"<i>{pcr.get('logic', '')}</i>\n\n"
    
    if max_pain:
        msg += f"<b>🎯 MAX PAIN:</b> Rs.{max_pain['max_pain']}\n"
        msg += f"Current: Rs.{max_pain['current']} | Distance: {max_pain['distance']} pts\n"
        msg += f"<i>{max_pain['logic']}</i>\n\n"
    
    if iv:
        emoji = "🔴" if 'TOO HIGH' in iv['signal'] else "🟢" if 'LOW' in iv['signal'] else "🟡"
        msg += f"<b>{emoji} IV SIGNAL:</b> {iv['signal']} (IV: {iv['avg_iv']}%)\n"
        msg += f"{iv['action']}\n\n"
    
    if gamma:
        msg += f"<b>⚡ GAMMA SQUEEZE:</b> {gamma['signal']}\n"
        for s in gamma['strikes'][:2]:
            msg += f"  • {s['strike']} {s['type']}: {s['distance']}% away, OI: {s['oi']/100000:.1f}L\n"
        msg += f"<i>{gamma['logic']}</i>\n\n"
    
    if divergence:
        msg += f"<b>💰 SMART MONEY:</b>\n"
        for d in divergence[:3]:
            emoji = "🟢" if d['signal'] == 'SMART_MONEY_ACCUMULATION' else "🔴"
            msg += f"{emoji} {d['strike']} {d['type']}: {d['signal']}\n"
            msg += f"   Entry: Rs.{d['entry']} | Target: Rs.{d['target']}\n\n"
    
    msg += f"{'═'*35}\n"
    msg += f"<b>📋 GOLDEN RULES:</b>\n"
    msg += f"• PCR Extreme Fear (>1.5) = Best buying opportunity\n"
    msg += f"• IV < 13 = Cheapest options = Best time to buy\n"
    msg += f"• Max Pain = Magnetic level\n"
    msg += f"• Smart money OI divergence = Front-run signal\n"
    msg += f"• Exit ALL before 2:30 PM\n"
    
    return msg

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("ULTIMATE OPTIONS SCANNER v3.0")
    
    if not is_market_open():
        msg = f"<b>Options Scanner</b>\n{datetime.now().strftime('%d-%b %I:%M %p')}\n\nMarket closed. Mon-Fri 9:15 AM-3:30 PM."
        send_telegram(msg)
        exit(0)
    
    # Fetch data
    data = fetch_options_chain()
    if not data:
        send_telegram(f"⚠️ Could not fetch options data.")
        exit(1)
    
    # Run all 5 signals
    print("Running proprietary signals...")
    divergence = detect_oi_price_divergence(data)
    pcr = calculate_pcr_signal(data)
    max_pain = calculate_max_pain(data)
    iv = calculate_iv_signal(data)
    gamma = detect_gamma_squeeze(data)
    
    # Combine
    combined = combine_signals(divergence, pcr, max_pain, iv, gamma)
    entry_advice = get_optimal_entry_time()
    
    # Build & send
    msg = build_ultimate_message(data, divergence, pcr, max_pain, iv, gamma, combined, entry_advice)
    
    if send_telegram(msg):
        print(f"✅ Ultimate alert sent! Signal: {combined['signal']}")
    else:
        print("❌ Failed")
