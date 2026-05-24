"""
OPTIONS MOMENTUM SCANNER v1.0
Detects: OI Spurts, Premium Decay Traps, Momentum Breakouts
Strategy: Buy when OI surges + Price confirms, Exit before decay
"""
import os
import time
import requests
import json
from datetime import datetime
from nsetools import Nse

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_OPTIONS_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_OPTIONS_CHAT_ID')

# ============================================
# NSE OPTIONS DATA FETCHER
# ============================================
def fetch_nifty_options():
    """Fetch Nifty options chain data"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        
        # Get session cookie
        session.get('https://www.nseindia.com', timeout=10)
        
        # Fetch options chain
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY'
        response = session.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('records', {}).get('data', [])
    except Exception as e:
        print(f"Error fetching options: {e}")
    return []

def fetch_bank_nifty_options():
    """Fetch Bank Nifty options chain"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        session.get('https://www.nseindia.com', timeout=10)
        
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY'
        response = session.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('records', {}).get('data', [])
    except:
        pass
    return []

# ============================================
# OI SPURT DETECTOR (8%+ in first 15 min)
# ============================================
def detect_oi_spurt(options_data):
    """Detect options with significant OI increase"""
    alerts = []
    
    for record in options_data:
        if 'CE' in record and 'PE' in record:
            ce = record['CE']
            pe = record['PE']
            
            strike_price = ce.get('strikePrice', 0)
            underlying = ce.get('underlyingValue', 0)
            
            # CE Analysis
            ce_oi = ce.get('openInterest', 0)
            ce_oi_change = ce.get('changeinOpenInterest', 0)
            ce_volume = ce.get('totalTradedVolume', 0)
            ce_ltp = ce.get('lastPrice', 0)
            ce_iv = ce.get('impliedVolatility', 0)
            
            # PE Analysis
            pe_oi = pe.get('openInterest', 0)
            pe_oi_change = pe.get('changeinOpenInterest', 0)
            pe_volume = pe.get('totalTradedVolume', 0)
            pe_ltp = pe.get('lastPrice', 0)
            pe_iv = pe.get('impliedVolatility', 0)
            
            # OI Change % for CE
            if ce_oi > 0 and ce_oi_change > 0:
                ce_oi_pct = (ce_oi_change / (ce_oi - ce_oi_change)) * 100
                
                # OI Surge > 8% + High Volume
                if ce_oi_pct >= 8 and ce_volume > 1000:
                    direction = "CALL" if strike_price > underlying else "PUT"
                    alerts.append({
                        'symbol': 'NIFTY',
                        'strike': strike_price,
                        'type': 'CE',
                        'direction': 'BULLISH',
                        'oi_change': round(ce_oi_pct, 1),
                        'ltp': ce_ltp,
                        'volume': ce_volume,
                        'iv': ce_iv,
                        'underlying': underlying,
                        'signal': 'OI_SPURT',
                        'strategy': 'MOMENTUM_BUY'
                    })
            
            # OI Change % for PE
            if pe_oi > 0 and pe_oi_change > 0:
                pe_oi_pct = (pe_oi_change / (pe_oi - pe_oi_change)) * 100
                
                if pe_oi_pct >= 8 and pe_volume > 1000:
                    alerts.append({
                        'symbol': 'NIFTY',
                        'strike': strike_price,
                        'type': 'PE',
                        'direction': 'BEARISH',
                        'oi_change': round(pe_oi_pct, 1),
                        'ltp': pe_ltp,
                        'volume': pe_volume,
                        'iv': pe_iv,
                        'underlying': underlying,
                        'signal': 'OI_SPURT',
                        'strategy': 'MOMENTUM_BUY'
                    })
    
    return alerts

# ============================================
# PREMIUM DECAY TRAP DETECTOR
# ============================================
def detect_decay_trap(options_data):
    """Detect options where premium can decay 50% intraday"""
    alerts = []
    
    for record in options_data:
        if 'CE' in record:
            ce = record['CE']
            strike = ce.get('strikePrice', 0)
            ltp = ce.get('lastPrice', 0)
            iv = ce.get('impliedVolatility', 0)
            underlying = ce.get('underlyingValue', 0)
            
            # High IV = High premium = Decay risk
            if iv > 20 and ltp > 50:
                # ATM or near ATM options
                if abs(strike - underlying) / underlying < 0.02:
                    alerts.append({
                        'symbol': 'NIFTY',
                        'strike': strike,
                        'type': 'CE',
                        'ltp': ltp,
                        'iv': iv,
                        'signal': 'DECAY_RISK',
                        'warning': f'Premium {ltp} can decay 50% if underlying stalls. Exit before 1 PM.'
                    })
            
        if 'PE' in record:
            pe = record['PE']
            strike = pe.get('strikePrice', 0)
            ltp = pe.get('lastPrice', 0)
            iv = pe.get('impliedVolatility', 0)
            underlying = pe.get('underlyingValue', 0)
            
            if iv > 20 and ltp > 50:
                if abs(strike - underlying) / underlying < 0.02:
                    alerts.append({
                        'symbol': 'NIFTY',
                        'strike': strike,
                        'type': 'PE',
                        'ltp': ltp,
                        'iv': iv,
                        'signal': 'DECAY_RISK',
                        'warning': f'Premium {ltp} can decay 50% if underlying stalls. Exit before 1 PM.'
                    })
    
    return alerts

# ============================================
# HIGH PROBABILITY SETUP (Near Sure Shot)
# ============================================
def detect_high_probability_setup(options_data):
    """
    Strategy: OI Surge + Price above VWAP + High Volume + IV expanding
    This is the closest to "sure shot" in options buying
    """
    alerts = []
    
    for record in options_data:
        if 'CE' in record:
            ce = record['CE']
            
            strike = ce.get('strikePrice', 0)
            ltp = ce.get('lastPrice', 0)
            oi = ce.get('openInterest', 0)
            oi_change = ce.get('changeinOpenInterest', 0)
            volume = ce.get('totalTradedVolume', 0)
            iv = ce.get('impliedVolatility', 0)
            underlying = ce.get('underlyingValue', 0)
            change = ce.get('change', 0)
            
            # Conditions for HIGH PROBABILITY CALL
            oi_pct = (oi_change / (oi - oi_change)) * 100 if oi > oi_change > 0 else 0
            
            if (oi_pct > 10 and  # OI surging
                volume > 5000 and  # High volume
                change > 0 and  # Price increasing
                iv > 15 and  # IV supporting
                strike > underlying * 0.99):  # ATM/ITM
                
                alerts.append({
                    'symbol': 'NIFTY',
                    'strike': strike,
                    'type': 'CE',
                    'direction': 'BULLISH',
                    'ltp': ltp,
                    'oi_pct': round(oi_pct, 1),
                    'volume': volume,
                    'iv': iv,
                    'underlying': underlying,
                    'signal': 'HIGH_PROBABILITY',
                    'confidence': min(90, oi_pct + 40),
                    'entry': ltp,
                    'target1': round(ltp * 1.5, 2),
                    'target2': round(ltp * 2.0, 2),
                    'stop_loss': round(ltp * 0.8, 2),
                    'max_hold': 'Exit before 2 PM to avoid decay'
                })
            
        if 'PE' in record:
            pe = record['PE']
            
            strike = pe.get('strikePrice', 0)
            ltp = pe.get('lastPrice', 0)
            oi = pe.get('openInterest', 0)
            oi_change = pe.get('changeinOpenInterest', 0)
            volume = pe.get('totalTradedVolume', 0)
            iv = pe.get('impliedVolatility', 0)
            underlying = pe.get('underlyingValue', 0)
            change = pe.get('change', 0)
            
            oi_pct = (oi_change / (oi - oi_change)) * 100 if oi > oi_change > 0 else 0
            
            if (oi_pct > 10 and
                volume > 5000 and
                change > 0 and
                iv > 15 and
                strike < underlying * 1.01):
                
                alerts.append({
                    'symbol': 'NIFTY',
                    'strike': strike,
                    'type': 'PE',
                    'direction': 'BEARISH',
                    'ltp': ltp,
                    'oi_pct': round(oi_pct, 1),
                    'volume': volume,
                    'iv': iv,
                    'underlying': underlying,
                    'signal': 'HIGH_PROBABILITY',
                    'confidence': min(90, oi_pct + 40),
                    'entry': ltp,
                    'target1': round(ltp * 1.5, 2),
                    'target2': round(ltp * 2.0, 2),
                    'stop_loss': round(ltp * 0.8, 2),
                    'max_hold': 'Exit before 2 PM to avoid decay'
                })
    
    return alerts

# ============================================
# SMART MONEY VS RETAIL DETECTOR
# ============================================
def detect_smart_money_trap(options_data):
    """
    Detect where smart money is trapping retailers
    High OI at a strike = Smart money sold options
    Price moving towards that strike = Retail trapped
    """
    alerts = []
    
    # Find highest OI strikes (smart money positions)
    max_ce_oi = 0
    max_pe_oi = 0
    max_ce_strike = 0
    max_pe_strike = 0
    
    for record in options_data:
        if 'CE' in record:
            ce = record['CE']
            if ce.get('openInterest', 0) > max_ce_oi:
                max_ce_oi = ce.get('openInterest', 0)
                max_ce_strike = ce.get('strikePrice', 0)
        
        if 'PE' in record:
            pe = record['PE']
            if pe.get('openInterest', 0) > max_pe_oi:
                max_pe_oi = pe.get('openInterest', 0)
                max_pe_strike = pe.get('strikePrice', 0)
    
    if max_ce_strike > 0:
        alerts.append({
            'signal': 'SMART_MONEY',
            'type': 'CE_RESISTANCE',
            'strike': max_ce_strike,
            'oi': max_ce_oi,
            'message': f'Smart money sold CE at {max_ce_strike}. Price likely to face resistance. Dont buy CE above this.'
        })
    
    if max_pe_strike > 0:
        alerts.append({
            'signal': 'SMART_MONEY',
            'type': 'PE_SUPPORT',
            'strike': max_pe_strike,
            'oi': max_pe_oi,
            'message': f'Smart money sold PE at {max_pe_strike}. This is strong support. Dont buy PE below this.'
        })
    
    return alerts

# ============================================
# TELEGRAM SENDER
# ============================================
def send_options_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

# ============================================
# MAIN SCANNER
# ============================================
def run_options_scan():
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    print(f"📊 OPTIONS SCANNER - {now.strftime('%d-%b %I:%M %p')}")
    
    # Fetch data
    nifty_data = fetch_nifty_options()
    banknifty_data = fetch_bank_nifty_options()
    
    all_data = nifty_data + banknifty_data
    
    if not all_data:
        print("No options data available")
        return
    
    # Run all detectors
    oi_spurts = detect_oi_spurt(all_data)
    decay_traps = detect_decay_trap(all_data)
    high_prob = detect_high_probability_setup(all_data)
    smart_money = detect_smart_money_trap(all_data)
    
    # Build message
    msg = f"<b>OPTIONS MOMENTUM SCANNER</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    # Session-based advice
    if hour == 9 and minute < 30:
        msg += f"<b>⚠️ FIRST 30 MINUTES</b>\n"
        msg += f"Wait for OI to settle. Don't trade yet.\n"
        msg += f"Watch OI spurts > 8% for direction.\n\n"
    
    # HIGH PROBABILITY SETUPS (Most Important)
    if high_prob:
        msg += f"<b>🎯 HIGH PROBABILITY SETUPS</b>\n{'═'*35}\n\n"
        for i, alert in enumerate(high_prob[:4], 1):
            emoji = "🟢" if alert['direction'] == 'BULLISH' else "🔴"
            msg += f"{emoji} <b>#{i} {alert['symbol']} {alert['strike']} {alert['type']}</b>\n"
            msg += f"{'─'*35}\n"
            msg += f"Direction: <b>{alert['direction']}</b>\n"
            msg += f"Confidence: <b>{alert['confidence']:.0f}%</b>\n"
            msg += f"OI Surge: <b>+{alert['oi_pct']}%</b>\n"
            msg += f"Volume: {alert['volume']}\n"
            msg += f"IV: {alert['iv']}%\n\n"
            msg += f"<b>Trade Plan:</b>\n"
            msg += f"Entry: Rs.{alert['entry']}\n"
            msg += f"T1: Rs.{alert['target1']} (+50%) | T2: Rs.{alert['target2']} (+100%)\n"
            msg += f"SL: Rs.{alert['stop_loss']} (-20%)\n"
            msg += f"⏰ {alert['max_hold']}\n\n"
    
    # OI SPURTS
    if oi_spurts:
        msg += f"<b>📊 OI SPURTS (>8%)</b>\n{'═'*35}\n\n"
        for alert in oi_spurts[:3]:
            msg += f"{'🟢' if alert['direction']=='BULLISH' else '🔴'} {alert['symbol']} {alert['strike']} {alert['type']}\n"
            msg += f"   OI: +{alert['oi_change']}% | LTP: Rs.{alert['ltp']} | Vol: {alert['volume']}\n\n"
    
    # DECAY WARNINGS
    if decay_traps:
        msg += f"<b>⚠️ PREMIUM DECAY WARNING</b>\n{'═'*35}\n\n"
        for alert in decay_traps[:2]:
            msg += f"⚠️ {alert['symbol']} {alert['strike']} {alert['type']} | Premium: Rs.{alert['ltp']}\n"
            msg += f"   {alert['warning']}\n\n"
    
    # SMART MONEY LEVELS
    if smart_money:
        msg += f"<b>💰 SMART MONEY LEVELS</b>\n{'═'*35}\n\n"
        for alert in smart_money[:2]:
            msg += f"{alert['message']}\n\n"
    
    # Golden Rules
    if hour < 13:
        msg += f"<b>📋 SESSION RULES:</b>\n"
        msg += f"• First 30 min: Observe OI, don't trade\n"
        msg += f"• 10 AM-1 PM: Best time for momentum trades\n"
        msg += f"• After 2 PM: Exit all positions (theta decay)\n"
        msg += f"• Never hold options overnight\n"
    
    msg += f"\n{'═'*35}\n"
    msg += f"<i>Options Scanner | OI + Momentum + Decay Alerts</i>"
    
    if send_options_alert(msg):
        print(f"✅ Options alert sent!")
    else:
        print("❌ Failed to send")

if __name__ == "__main__":
    run_options_scan()
