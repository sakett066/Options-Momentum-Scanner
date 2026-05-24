"""
OPTIONS MOMENTUM SCANNER v2.0 - Production Ready
Detects: OI Spurts, Momentum, Smart Money Levels
With market hours check and fallback APIs
"""
import os
import time
import requests
import json
from datetime import datetime

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_OPTIONS_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_OPTIONS_CHAT_ID')

# ============================================
# MARKET HOURS CHECK
# ============================================
def is_market_open():
    """Check if market is open right now"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    
    # Weekend check (Mon=0, Sun=6)
    if weekday >= 5:
        return False
    
    # Before 9:15 AM
    if hour < 9 or (hour == 9 and minute < 15):
        return False
    
    # After 3:30 PM
    if hour > 15 or (hour == 15 and minute > 30):
        return False
    
    return True

def get_session_advice():
    """Get advice based on current time"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    if hour == 9 and minute < 30:
        return "⚠️ First 30 min: Observe OI, don't trade yet. Wait for direction."
    elif hour < 11:
        return "✅ Best trading window: 10 AM-1 PM. Enter momentum trades."
    elif hour < 13:
        return "✅ Good window. Trail SL. Book partial profits."
    elif hour < 14:
        return "⚠️ Start booking profits. Exit 50% positions."
    elif hour < 15:
        return "🔴 Exit ALL positions. Theta decay accelerates. No new trades."
    else:
        return "🔴 Final 30 min: Close all. Don't carry options overnight."

# ============================================
# TELEGRAM SENDER
# ============================================
def send_telegram(text):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing credentials")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900:
            text = text[:3900]
        resp = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
        result = resp.json()
        return result.get('ok', False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# ============================================
# NSE OPTIONS DATA FETCHER
# ============================================
def fetch_options_data(symbol='NIFTY'):
    """Fetch options chain data from NSE"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/option-chain',
            'Connection': 'keep-alive'
        })
        
        # Get initial cookies
        print("Getting NSE session...")
        resp = session.get('https://www.nseindia.com', timeout=15)
        time.sleep(1)
        
        # Try multiple URLs
        urls = [
            f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}',
            f'https://www.nseindia.com/api/option-chain-equities?symbol={symbol}',
        ]
        
        for url in urls:
            try:
                print(f"Fetching: {url}")
                response = session.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    records = data.get('records', {}).get('data', [])
                    if records:
                        print(f"✅ Got {len(records)} records from {symbol}")
                        return records, symbol
                else:
                    print(f"Status {response.status_code} for {symbol}")
            except:
                continue
        
        # Fallback to Bank Nifty
        print("Trying Bank Nifty...")
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY'
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', {}).get('data', [])
            print(f"✅ Got {len(records)} records from BANKNIFTY")
            return records, 'BANKNIFTY'
            
    except Exception as e:
        print(f"Fetch error: {e}")
    
    return [], symbol

# ============================================
# OI SPURT DETECTOR
# ============================================
def detect_oi_spurts(data):
    """Find options with >8% OI increase"""
    alerts = []
    
    for record in data:
        try:
            underlying = 0
            
            if 'CE' in record:
                ce = record['CE']
                strike = ce.get('strikePrice', 0)
                oi = ce.get('openInterest', 0)
                oi_change = ce.get('changeinOpenInterest', 0)
                ltp = ce.get('lastPrice', 0)
                volume = ce.get('totalTradedVolume', 0)
                iv = ce.get('impliedVolatility', 0)
                underlying = ce.get('underlyingValue', underlying)
                
                if oi > oi_change > 0:
                    oi_pct = (oi_change / (oi - oi_change)) * 100
                    
                    if oi_pct >= 8 and volume > 500:
                        alerts.append({
                            'type': 'CE',
                            'strike': strike,
                            'direction': 'BULLISH 📈',
                            'oi_pct': round(oi_pct, 1),
                            'ltp': ltp,
                            'volume': volume,
                            'iv': iv,
                            'underlying': underlying
                        })
            
            if 'PE' in record:
                pe = record['PE']
                strike = pe.get('strikePrice', 0)
                oi = pe.get('openInterest', 0)
                oi_change = pe.get('changeinOpenInterest', 0)
                ltp = pe.get('lastPrice', 0)
                volume = pe.get('totalTradedVolume', 0)
                iv = pe.get('impliedVolatility', 0)
                underlying = pe.get('underlyingValue', underlying)
                
                if oi > oi_change > 0:
                    oi_pct = (oi_change / (oi - oi_change)) * 100
                    
                    if oi_pct >= 8 and volume > 500:
                        alerts.append({
                            'type': 'PE',
                            'strike': strike,
                            'direction': 'BEARISH 📉',
                            'oi_pct': round(oi_pct, 1),
                            'ltp': ltp,
                            'volume': volume,
                            'iv': iv,
                            'underlying': underlying
                        })
        except:
            continue
    
    # Sort by OI change
    alerts.sort(key=lambda x: x['oi_pct'], reverse=True)
    return alerts

# ============================================
# SMART MONEY LEVELS
# ============================================
def detect_smart_money(data):
    """Find highest OI strikes (smart money positions)"""
    max_ce_oi = 0
    max_ce_strike = 0
    max_pe_oi = 0
    max_pe_strike = 0
    
    for record in data:
        try:
            if 'CE' in record:
                ce = record['CE']
                oi = ce.get('openInterest', 0)
                if oi > max_ce_oi:
                    max_ce_oi = oi
                    max_ce_strike = ce.get('strikePrice', 0)
            
            if 'PE' in record:
                pe = record['PE']
                oi = pe.get('openInterest', 0)
                if oi > max_pe_oi:
                    max_pe_oi = oi
                    max_pe_strike = pe.get('strikePrice', 0)
        except:
            continue
    
    levels = []
    if max_ce_strike > 0:
        levels.append({
            'type': 'RESISTANCE',
            'strike': max_ce_strike,
            'message': f"Strong resistance at {max_ce_strike} (CE OI: {max_ce_oi/100000:.1f}L). Don't buy CE above this."
        })
    
    if max_pe_strike > 0:
        levels.append({
            'type': 'SUPPORT',
            'strike': max_pe_strike,
            'message': f"Strong support at {max_pe_strike} (PE OI: {max_pe_oi/100000:.1f}L). Don't buy PE below this."
        })
    
    return levels

# ============================================
# HIGH PROBABILITY SETUPS
# ============================================
def detect_high_probability(data):
    """OI Surge + Volume + IV confirmation"""
    setups = []
    
    for record in data:
        try:
            underlying = 0
            
            if 'CE' in record:
                ce = record['CE']
                strike = ce.get('strikePrice', 0)
                oi = ce.get('openInterest', 0)
                oi_change = ce.get('changeinOpenInterest', 0)
                ltp = ce.get('lastPrice', 0)
                volume = ce.get('totalTradedVolume', 0)
                iv = ce.get('impliedVolatility', 0)
                underlying = ce.get('underlyingValue', 0)
                change = ce.get('change', 0)
                
                if oi > oi_change > 0:
                    oi_pct = (oi_change / (oi - oi_change)) * 100
                    
                    # High probability conditions
                    if (oi_pct > 10 and volume > 2000 and change > 0 and iv > 12):
                        confidence = min(90, oi_pct + 35)
                        
                        setups.append({
                            'type': 'CE',
                            'strike': strike,
                            'direction': 'BULLISH',
                            'entry': ltp,
                            'target1': round(ltp * 1.5, 2),
                            'target2': round(ltp * 2.0, 2),
                            'stop_loss': round(ltp * 0.75, 2),
                            'confidence': round(confidence, 1),
                            'oi_pct': round(oi_pct, 1),
                            'volume': volume,
                            'iv': iv,
                            'underlying': underlying
                        })
            
            if 'PE' in record:
                pe = record['PE']
                strike = pe.get('strikePrice', 0)
                oi = pe.get('openInterest', 0)
                oi_change = pe.get('changeinOpenInterest', 0)
                ltp = pe.get('lastPrice', 0)
                volume = pe.get('totalTradedVolume', 0)
                iv = pe.get('impliedVolatility', 0)
                underlying = pe.get('underlyingValue', 0)
                change = pe.get('change', 0)
                
                if oi > oi_change > 0:
                    oi_pct = (oi_change / (oi - oi_change)) * 100
                    
                    if (oi_pct > 10 and volume > 2000 and change > 0 and iv > 12):
                        confidence = min(90, oi_pct + 35)
                        
                        setups.append({
                            'type': 'PE',
                            'strike': strike,
                            'direction': 'BEARISH',
                            'entry': ltp,
                            'target1': round(ltp * 1.5, 2),
                            'target2': round(ltp * 2.0, 2),
                            'stop_loss': round(ltp * 0.75, 2),
                            'confidence': round(confidence, 1),
                            'oi_pct': round(oi_pct, 1),
                            'volume': volume,
                            'iv': iv,
                            'underlying': underlying
                        })
        except:
            continue
    
    setups.sort(key=lambda x: x['confidence'], reverse=True)
    return setups

# ============================================
# BUILD MESSAGE
# ============================================
def build_message(symbol, oi_spurts, smart_money, high_prob, advice):
    """Build Telegram message"""
    now = datetime.now()
    
    msg = f"<b>🎯 OPTIONS MOMENTUM SCANNER</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"Index: {symbol}\n"
    msg += f"{'═'*35}\n\n"
    
    # Session advice
    msg += f"<b>⏰ SESSION:</b>\n{advice}\n\n"
    
    # High Probability Setups
    if high_prob:
        msg += f"<b>🔥 HIGH PROBABILITY SETUPS</b>\n{'═'*35}\n\n"
        for i, setup in enumerate(high_prob[:3], 1):
            emoji = "🟢" if setup['direction'] == 'BULLISH' else "🔴"
            msg += f"{emoji} <b>#{i} {symbol} {setup['strike']} {setup['type']}</b>\n"
            msg += f"{'─'*35}\n"
            msg += f"Direction: <b>{setup['direction']}</b>\n"
            msg += f"Confidence: <b>{setup['confidence']:.0f}%</b>\n"
            msg += f"OI Surge: +{setup['oi_pct']}%\n"
            msg += f"Volume: {setup['volume']} | IV: {setup['iv']}%\n\n"
            msg += f"<b>Trade:</b>\n"
            msg += f"Entry: Rs.{setup['entry']}\n"
            msg += f"T1: Rs.{setup['target1']} (+50%) | T2: Rs.{setup['target2']} (+100%)\n"
            msg += f"SL: Rs.{setup['stop_loss']} (-25%)\n"
            msg += f"⏰ Exit before 2 PM\n\n"
    
    # OI Spurts
    if oi_spurts:
        msg += f"<b>📊 TOP OI SPURTS</b>\n{'═'*35}\n\n"
        for alert in oi_spurts[:5]:
            emoji = "🟢" if 'BULLISH' in alert['direction'] else "🔴"
            msg += f"{emoji} {alert['strike']} {alert['type']} | OI: +{alert['oi_pct']}%\n"
            msg += f"   LTP: Rs.{alert['ltp']} | Vol: {alert['volume']} | IV: {alert['iv']}%\n\n"
    
    # Smart Money Levels
    if smart_money:
        msg += f"<b>💰 SMART MONEY LEVELS</b>\n{'═'*35}\n\n"
        for level in smart_money:
            msg += f"{level['message']}\n\n"
    
    # Rules
    msg += f"<b>📋 GOLDEN RULES:</b>\n"
    msg += f"• First 30 min: Observe, don't trade\n"
    msg += f"• 10 AM-1 PM: Best for momentum trades\n"
    msg += f"• After 1:30 PM: Start exiting\n"
    msg += f"• After 2:30 PM: No new trades\n"
    msg += f"• Never hold options overnight\n"
    msg += f"• SL mandatory -20% below entry\n"
    
    return msg

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("OPTIONS MOMENTUM SCANNER v2.0")
    print("=" * 50)
    
    # Check market hours
    if not is_market_open():
        msg = f"<b>Options Scanner</b>\n{datetime.now().strftime('%d-%b %I:%M %p')}\n\n🔴 Market is closed.\nTry between Mon-Fri 9:15 AM - 3:30 PM IST."
        send_telegram(msg)
        print("Market closed - exiting")
        exit(0)
    
    # Fetch data
    print("\n📊 Fetching options data...")
    data, symbol = fetch_options_data()
    
    if not data:
        msg = f"<b>Options Scanner</b>\n{datetime.now().strftime('%d-%b %I:%M %p')}\n\n⚠️ Could not fetch data. NSE API blocking.\nTry during market hours."
        send_telegram(msg)
        print("No data - exiting")
        exit(1)
    
    # Analyze
    print("\n🔍 Analyzing...")
    oi_spurts = detect_oi_spurts(data)
    smart_money = detect_smart_money(data)
    high_prob = detect_high_probability(data)
    advice = get_session_advice()
    
    print(f"OI Spurts: {len(oi_spurts)}")
    print(f"Smart Money Levels: {len(smart_money)}")
    print(f"High Prob Setups: {len(high_prob)}")
    
    # Build and send
    msg = build_message(symbol, oi_spurts, smart_money, high_prob, advice)
    
    if send_telegram(msg):
        print("✅ Alert sent to Telegram!")
    else:
        print("❌ Failed to send")
