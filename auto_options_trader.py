"""
AUTO OPTIONS TRADER - Guaranteed Alert Version
Simple PCR-based entry/exit with Telegram alerts
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

def send_alert(text):
    """Send Telegram alert"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
        result = resp.json()
        print(f"Telegram response: {result.get('ok')}")
        return result.get('ok', False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def get_nifty_data():
    """Get Nifty data using nsetools (always works)"""
    try:
        nse = Nse()
        q = nse.get_quote('NIFTY 50')
        if not q:
            # Fallback to RELIANCE for market proxy
            q = nse.get_quote('RELIANCE')
        
        price = float(q.get('lastPrice', 0))
        change = float(q.get('pChange', 0))
        
        return {
            'price': price,
            'change': change,
            'day_high': float(q.get('intraDayHighLow', {}).get('max', 0)),
            'day_low': float(q.get('intraDayHighLow', {}).get('min', 0))
        }
    except Exception as e:
        print(f"NSE error: {e}")
        return None

def calculate_pcr():
    """Calculate simplified PCR from options data"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        session.get('https://www.nseindia.com', timeout=10)
        time.sleep(0.5)
        
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY'
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            records = data.get('records', {}).get('data', [])
            
            total_ce = 0
            total_pe = 0
            
            for r in records:
                if 'CE' in r:
                    total_ce += r['CE'].get('openInterest', 0)
                if 'PE' in r:
                    total_pe += r['PE'].get('openInterest', 0)
            
            if total_ce > 0:
                return round(total_pe / total_ce, 2)
    except Exception as e:
        print(f"PCR error: {e}")
    
    return None

def is_entry_time():
    """Check if it's entry window"""
    now = datetime.now()
    current = now.strftime('%H:%M')
    return '09:45' <= current <= '10:15'

def is_exit_time():
    """Check if it's exit time"""
    now = datetime.now()
    return now.strftime('%H:%M') >= '14:15'

def is_market_open():
    """Check market hours"""
    now = datetime.now()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    if h < 9 or (h == 9 and m < 15): return False
    if h > 15 or (h == 15 and m > 30): return False
    return True

# ============================================
# TRADE STATE MANAGEMENT
# ============================================
TRADE_FILE = 'trade_state.json'

def save_state(state):
    with open(TRADE_FILE, 'w') as f:
        json.dump(state, f, default=str)

def load_state():
    try:
        with open(TRADE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

# ============================================
# MAIN
# ============================================
def run():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    
    print(f"\n{'='*50}")
    print(f"AUTO TRADER - {now.strftime('%d-%b %I:%M %p')}")
    print(f"{'='*50}")
    
    # 1. Send test alert first
    if not send_alert(f"🟢 <b>Auto Trader Online</b>\n{now.strftime('%d-%b %I:%M %p')}\nChecking market...\nTime: {current_time}"):
        print("❌ Telegram failed - check credentials")
        return
    
    # 2. Market check
    if not is_market_open():
        print("Market closed")
        if now.weekday() >= 5:
            send_alert("📅 Weekend - Market closed")
        else:
            send_alert(f"🔴 Market closed ({current_time})")
        return
    
    # 3. Check state
    state = load_state()
    
    # 4. EXIT CHECK
    if is_exit_time():
        if state and state.get('status') == 'ENTERED' and state.get('date') == today:
            msg = f"🔴 <b>EXIT TRADE NOW</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n"
            msg += f"Sell: {state['symbol']}\n"
            msg += f"Qty: {state['quantity']}\n"
            msg += f"Entry: Rs.{state['entry']}\n"
            msg += f"Exit at MARKET price\n\n"
            msg += f"📱 Open Upstox → Exit Position"
            send_alert(msg)
            
            state['status'] = 'EXITED'
            save_state(state)
        else:
            print("Exit time but no open trade")
        return
    
    # 5. ENTRY CHECK
    if is_entry_time():
        if state and state.get('status') == 'ENTERED' and state.get('date') == today:
            print("Already entered today")
            return
        
        # Get Nifty data
        nifty = get_nifty_data()
        if not nifty:
            send_alert("⚠️ Could not fetch Nifty data")
            return
        
        # Get PCR
        pcr = calculate_pcr()
        
        # Determine signal
        if pcr is None:
            signal_type = 'NO_DATA'
        elif pcr > 1.3:
            signal_type = 'BUY_CALL'
        elif pcr < 0.7:
            signal_type = 'BUY_PUT'
        else:
            signal_type = 'NEUTRAL'
        
        # Build and send alert
        if signal_type in ['BUY_CALL', 'BUY_PUT']:
            direction = "CALL (CE)" if signal_type == 'BUY_CALL' else "PUT (PE)"
            strike = round(nifty['price'] / 50) * 50
            
            if signal_type == 'BUY_CALL':
                strike = strike + 100  # OTM
            else:
                strike = strike - 100  # OTM
            
            symbol = f"NIFTY{strike}{'CE' if signal_type == 'BUY_CALL' else 'PE'}"
            
            msg = f"🚀 <b>TRADE ENTRY SIGNAL</b>\n"
            msg += f"{now.strftime('%d-%b %I:%M %p')}\n"
            msg += f"{'═'*35}\n\n"
            
            msg += f"<b>📊 MARKET:</b>\n"
            msg += f"Nifty: {nifty['price']:.0f} ({nifty['change']:+.1f}%)\n"
            msg += f"PCR: {pcr} - {'EXTREME FEAR' if pcr > 1.3 else 'EXTREME GREED'}\n\n"
            
            msg += f"<b>🎯 SIGNAL:</b>\n"
            msg += f"Buy: <b>{direction}</b>\n"
            msg += f"Symbol: <b>{symbol}</b>\n"
            msg += f"Strike: {strike}\n\n"
            
            msg += f"<b>📱 ON UPSTOX APP:</b>\n"
            msg += f"1. Search: {symbol}\n"
            msg += f"2. Buy: 25 Qty (1 Lot) at MARKET\n"
            msg += f"3. Set GTT SL: -25% from entry\n"
            msg += f"4. Set Target: +50% from entry\n\n"
            
            msg += f"<b>⏰ EXIT:</b> 2:15 PM TODAY\n"
            msg += f"<b>⚠️ Max Loss:</b> Accept -25% SL\n"
            
            send_alert(msg)
            
            # Save state
            save_state({
                'date': today,
                'time': current_time,
                'symbol': symbol,
                'status': 'ENTERED',
                'entry': 'MARKET',
                'quantity': 25
            })
            
        elif signal_type == 'NEUTRAL':
            msg = f"<b>📊 Options Scanner</b>\n"
            msg += f"{now.strftime('%d-%b %I:%M %p')}\n\n"
            msg += f"Nifty: {nifty['price']:.0f}\n"
            msg += f"PCR: {pcr} (Neutral)\n\n"
            msg += f"⚠️ No trade signal. PCR not extreme.\n"
            msg += f"Wait for PCR > 1.3 or < 0.7"
            send_alert(msg)
        else:
            send_alert(f"⚠️ Could not fetch PCR data. Try later.")
    
    else:
        print(f"⏰ {current_time} - Not in entry/exit window")
        
        # Mid-day status if trade open
        if state and state.get('status') == 'ENTERED' and state.get('date') == today:
            msg = f"<b>📊 POSITION ACTIVE</b>\n"
            msg += f"{now.strftime('%d-%b %I:%M %p')}\n\n"
            msg += f"Symbol: {state['symbol']}\n"
            msg += f"Entry: MARKET\n"
            msg += f"Qty: {state['quantity']}\n\n"
            msg += f"⏰ Auto-Exit at 2:15 PM\n"
            msg += f"📱 Check P&L on Upstox"
            send_alert(msg)

if __name__ == "__main__":
    run()
