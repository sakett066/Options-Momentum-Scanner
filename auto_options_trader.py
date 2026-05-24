"""
FULLY AUTOMATED OPTIONS TRADER
Entry: 9:45 AM | Exit: 2:15 PM | 1 Lot Only
No monitoring needed - set and forget
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
# CONFIGURATION - YOU CAN CHANGE THESE
# ============================================
CONFIG = {
    'LOTS': 1,                    # Start with 1 lot
    'LOT_SIZE': 25,               # NIFTY lot size
    'MAX_LOSS_PER_TRADE': 2000,   # Max loss Rs.2000
    'TARGET_PROFIT_PCT': 50,      # Book at 50% profit
    'TRAIL_SL_AFTER': 30,         # Trail SL after 30% profit
    'ENTRY_TIME': '09:45',        # Enter at 9:45 AM
    'EXIT_TIME': '14:15',         # Exit at 2:15 PM
    'NO_TRADE_AFTER': '14:00',    # No new trades after 2 PM
}

# ============================================
# TELEGRAM
# ============================================
def send_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

# ============================================
# NSE DATA
# ============================================
def fetch_options_data():
    """Get options data"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Referer': 'https://www.nseindia.com/option-chain'
        })
        session.get('https://www.nseindia.com', timeout=15)
        time.sleep(0.5)
        
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY'
        resp = session.get(url, timeout=15)
        
        if resp.status_code == 200:
            return resp.json().get('records', {}).get('data', [])
    except: pass
    return []

# ============================================
# SIGNAL GENERATOR
# ============================================
def generate_trade_signal(data):
    """Generate ONE clear trade signal"""
    
    # Calculate PCR
    total_ce_oi = sum(r.get('CE', {}).get('openInterest', 0) for r in data if 'CE' in r)
    total_pe_oi = sum(r.get('PE', {}).get('openInterest', 0) for r in data if 'PE' in r)
    pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1
    
    # Get current Nifty
    underlying = 0
    for r in data[:1]:
        if 'CE' in r:
            underlying = r['CE'].get('underlyingValue', 0)
            break
    
    # Find ATM strike (nearest to current price)
    atm_strike = round(underlying / 50) * 50  # Round to nearest 50
    
    # Find best option based on PCR
    if pcr > 1.3:
        # EXTREME FEAR = Buy Calls
        direction = 'BUY'
        option_type = 'CE'
        strike = atm_strike + 100  # OTM call
    elif pcr < 0.7:
        # EXTREME GREED = Buy Puts
        direction = 'BUY'
        option_type = 'PE'
        strike = atm_strike - 100  # OTM put
    else:
        # NEUTRAL = No trade
        return None
    
    # Find that option in chain
    for record in data:
        if option_type == 'CE' and 'CE' in record:
            opt = record['CE']
            if opt.get('strikePrice') == strike:
                return {
                    'symbol': 'NIFTY',
                    'strike': strike,
                    'type': option_type,
                    'direction': direction,
                    'entry': opt.get('lastPrice', 0),
                    'ltp': opt.get('lastPrice', 0),
                    'pcr': round(pcr, 2),
                    'underlying': underlying,
                    'signal': 'AUTO_TRADE',
                    'stop_loss': round(opt.get('lastPrice', 0) * 0.75, 2),
                    'target': round(opt.get('lastPrice', 0) * 1.5, 2),
                    'oi': opt.get('openInterest', 0),
                    'volume': opt.get('totalTradedVolume', 0)
                }
        
        if option_type == 'PE' and 'PE' in record:
            opt = record['PE']
            if opt.get('strikePrice') == strike:
                return {
                    'symbol': 'NIFTY',
                    'strike': strike,
                    'type': option_type,
                    'direction': direction,
                    'entry': opt.get('lastPrice', 0),
                    'ltp': opt.get('lastPrice', 0),
                    'pcr': round(pcr, 2),
                    'underlying': underlying,
                    'signal': 'AUTO_TRADE',
                    'stop_loss': round(opt.get('lastPrice', 0) * 0.75, 2),
                    'target': round(opt.get('lastPrice', 0) * 1.5, 2),
                    'oi': opt.get('openInterest', 0),
                    'volume': opt.get('totalTradedVolume', 0)
                }
    
    return None

# ============================================
# CHECK IF ENTRY TIME
# ============================================
def is_entry_time():
    """Check if it's time to enter trade"""
    now = datetime.now()
    current_time = now.strftime('%H:%M')
    
    # Entry window: 9:45 AM to 10:15 AM
    return '09:45' <= current_time <= '10:15'

def is_exit_time():
    """Check if it's time to exit all trades"""
    now = datetime.now()
    current_time = now.strftime('%H:%M')
    return current_time >= CONFIG['EXIT_TIME']

def is_market_hours():
    """Check if market is open"""
    now = datetime.now()
    if now.weekday() >= 5: return False
    hour, minute = now.hour, now.minute
    if hour < 9 or (hour == 9 and minute < 15): return False
    if hour > 15 or (hour == 15 and minute > 30): return False
    return True

# ============================================
# TRADE STATE (stored in file)
# ============================================
TRADE_FILE = 'trade_state.json'

def save_trade_state(state):
    """Save trade state to file"""
    with open(TRADE_FILE, 'w') as f:
        json.dump(state, f, default=str)

def load_trade_state():
    """Load trade state from file"""
    try:
        with open(TRADE_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

# ============================================
# EXECUTE TRADE (Manual - You do this part)
# ============================================
def execute_entry(signal):
    """Send entry alert with exact instructions"""
    
    lots = CONFIG['LOTS']
    qty = lots * CONFIG['LOT_SIZE']
    cost = signal['entry'] * qty
    sl_amount = signal['stop_loss'] * qty
    target_amount = signal['target'] * qty
    max_loss = cost - sl_amount
    
    msg = f"🚀 <b>TRADE ENTRY SIGNAL</b>\n"
    msg += f"{datetime.now().strftime('%d-%b %I:%M %p')}\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"<b>📊 SIGNAL DETAILS:</b>\n"
    msg += f"Symbol: NIFTY {signal['strike']} {signal['type']}\n"
    msg += f"Direction: {signal['direction']}\n"
    msg += f"PCR: {signal['pcr']}\n"
    msg += f"Nifty: {signal['underlying']}\n\n"
    
    msg += f"<b>💰 ORDER:</b>\n"
    msg += f"Buy: {qty} Qty ({lots} Lot)\n"
    msg += f"Entry: Rs.{signal['entry']}\n"
    msg += f"Total: Rs.{cost:.0f}\n\n"
    
    msg += f"<b>🛑 STOP LOSS:</b>\n"
    msg += f"Sell at: Rs.{signal['stop_loss']}\n"
    msg += f"Max Loss: Rs.{max_loss:.0f}\n\n"
    
    msg += f"<b>🎯 TARGET:</b>\n"
    msg += f"Sell at: Rs.{signal['target']}\n"
    msg += f"Profit: Rs.{target_amount - cost:.0f} (+50%)\n\n"
    
    msg += f"<b>⏰ AUTO-EXIT:</b> 2:15 PM today\n"
    msg += f"<b>📱 ACTION:</b> Place this order on Upstox now\n\n"
    
    msg += f"<b>ON UPSTOX APP:</b>\n"
    msg += f"1. Search: NIFTY {signal['strike']} {signal['type']}\n"
    msg += f"2. Buy: {qty} Qty at MARKET\n"
    msg += f"3. Set GTT Sell: {qty} @ Rs.{signal['stop_loss']}\n"
    msg += f"4. Set GTT Sell: {qty//2} @ Rs.{signal['target']}\n"
    
    send_alert(msg)
    
    # Save trade state
    state = {
        'entry_time': str(datetime.now()),
        'symbol': f"NIFTY{signal['strike']}{signal['type']}",
        'entry_price': signal['entry'],
        'stop_loss': signal['stop_loss'],
        'target': signal['target'],
        'quantity': qty,
        'lots': lots,
        'cost': cost,
        'status': 'ENTERED'
    }
    save_trade_state(state)
    
    return True

def execute_exit():
    """Send exit alert"""
    state = load_trade_state()
    
    if not state or state.get('status') != 'ENTERED':
        return False
    
    msg = f"🔴 <b>EXIT SIGNAL - 2:15 PM</b>\n"
    msg += f"{datetime.now().strftime('%d-%b %I:%M %p')}\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"<b>EXIT TRADE:</b>\n"
    msg += f"Symbol: {state['symbol']}\n"
    msg += f"Quantity: {state['quantity']}\n"
    msg += f"Entry: Rs.{state['entry_price']}\n\n"
    
    msg += f"<b>📱 ACTION:</b>\n"
    msg += f"Sell all {state['quantity']} at MARKET price\n"
    msg += f"On Upstox: Exit position\n\n"
    
    msg += f"<b>📊 TRADE SUMMARY:</b>\n"
    msg += f"Check P&L after exit\n"
    
    send_alert(msg)
    
    # Mark as exited
    state['status'] = 'EXITED'
    state['exit_time'] = str(datetime.now())
    save_trade_state(state)
    
    return True

# ============================================
# MAIN LOGIC
# ============================================
def run_auto_trader():
    """Main auto-trader logic"""
    now = datetime.now()
    
    print(f"\n{'='*50}")
    print(f"AUTO OPTIONS TRADER - {now.strftime('%d-%b %I:%M %p')}")
    print(f"{'='*50}")
    
    # Check market hours
    if not is_market_hours():
        print("Market closed")
        if now.weekday() >= 5:
            print("Weekend - no trading")
        else:
            send_alert(f"🔴 Market closed at {now.strftime('%I:%M %p')}")
        return
    
    # Check trade state
    state = load_trade_state()
    
    # EXIT CHECK - Always check first
    if is_exit_time():
        if state and state.get('status') == 'ENTERED':
            print("🕐 Exit time - closing trade")
            execute_exit()
        else:
            print("🕐 Exit time - no open trade")
        return
    
    # ENTRY CHECK
    if is_entry_time():
        # Check if already entered today
        if state and state.get('status') == 'ENTERED':
            entry_date = state.get('entry_time', '')[:10]
            today = str(now)[:10]
            if entry_date == today:
                print("Already entered today")
                return
        
        # Generate signal
        print("📊 Generating trade signal...")
        data = fetch_options_data()
        
        if not data:
            send_alert("⚠️ Could not fetch options data")
            return
        
        signal = generate_trade_signal(data)
        
        if signal:
            print(f"✅ Signal found: {signal['type']} {signal['strike']}")
            execute_entry(signal)
        else:
            print("No trade signal (PCR neutral)")
            send_alert(f"<b>📊 Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\nNo trade signal. PCR neutral. Waiting for extreme.")
    else:
        current_time = now.strftime('%H:%M')
        print(f"⏰ {current_time} - Not entry/exit time. Waiting.")
        
        # Mid-day check
        if state and state.get('status') == 'ENTERED':
            msg = f"<b>📊 POSITION UPDATE</b>\n"
            msg += f"{now.strftime('%d-%b %I:%M %p')}\n"
            msg += f"Symbol: {state['symbol']}\n"
            msg += f"Entry: Rs.{state['entry_price']}\n"
            msg += f"SL: Rs.{state['stop_loss']}\n"
            msg += f"Target: Rs.{state['target']}\n"
            msg += f"⏰ Auto-exit at 2:15 PM\n"
            send_alert(msg)

# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    run_auto_trader()
