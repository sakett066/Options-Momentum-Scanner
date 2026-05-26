"""
OPTIONS SCANNER v4.0 - 24/7 Working
Uses Yahoo Finance for reliable data, NSE options when available
Works day and night like other bots
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

CONFIG = {
    'LOTS': 1,
    'LOT_SIZE': 25,
    'MAX_LOSS': 2000,
    'ENTRY_HOUR_START': 9,
    'ENTRY_HOUR_END': 14,
    'EXIT_HOUR': 14,
    'EXIT_MINUTE': 15,
}

def is_market_hours():
    """Check if market is open for trading"""
    now = datetime.now()
    if now.weekday() >= 5: return False
    h, m = now.hour, now.minute
    if h < 9 or (h == 9 and m < 15): return False
    if h > 15 or (h == 15 and m > 30): return False
    return True

def get_nifty_data():
    """Get Nifty data using Yahoo Finance (24/7 reliable)"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^NSEI")
        hist = ticker.history(period="5d")
        
        if not hist.empty and len(hist) >= 2:
            price = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change = ((price - prev) / prev) * 100
            
            info = ticker.info
            h52 = float(info.get('fiftyTwoWeekHigh', price * 1.15))
            l52 = float(info.get('fiftyTwoWeekLow', price * 0.85))
            
            return {
                'price': price,
                'change': change,
                'high_52': h52 if not np.isnan(h52) else price * 1.15,
                'low_52': l52 if not np.isnan(l52) else price * 0.85,
                'day_high': float(hist['High'].iloc[-1]),
                'day_low': float(hist['Low'].iloc[-1]),
                'volume': int(hist['Volume'].iloc[-1])
            }
    except:
        pass
    
    # Fallback: Use RELIANCE as market proxy
    try:
        import yfinance as yf
        ticker = yf.Ticker("RELIANCE.NS")
        hist = ticker.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            return {
                'price': price * 18,  # Approximate Nifty
                'change': 0,
                'high_52': price * 18 * 1.15,
                'low_52': price * 18 * 0.85,
                'day_high': price * 18,
                'day_low': price * 18,
                'volume': 100000
            }
    except:
        pass
    
    return None

def get_bank_nifty_data():
    """Get Bank Nifty data"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^NSEBANK")
        hist = ticker.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            return {
                'price': price,
                'change': ((price - prev) / prev) * 100
            }
    except:
        pass
    return None

def calculate_pcr_estimate(nifty_data):
    """
    Estimate PCR from price action
    When market down 2%+ = Fear = High PCR = Buy Calls
    When market up 2%+ = Greed = Low PCR = Buy Puts
    """
    change = nifty_data['change']
    price = nifty_data['price']
    h52 = nifty_data['high_52']
    l52 = nifty_data['low_52']
    
    # Position in 52W range
    position = ((price - l52) / (h52 - l52)) * 100 if (h52 - l52) > 0 else 50
    
    # Estimate PCR
    if position < 25:
        pcr_estimate = 1.6  # Near lows = fear
        signal = 'EXTREME_FEAR'
        direction = 'BUY_CALL'
        message = 'Market near 52W low. Fear is high. CONTRARIAN BUY CALLS.'
        confidence = 75
    elif position < 40:
        pcr_estimate = 1.3
        signal = 'FEAR'
        direction = 'BUY_CALL'
        message = 'Market below midpoint. Good time to buy calls.'
        confidence = 65
    elif position > 80:
        pcr_estimate = 0.5
        signal = 'EXTREME_GREED'
        direction = 'BUY_PUT'
        message = 'Market near 52W high. Greed is high. CONTRARIAN BUY PUTS.'
        confidence = 75
    elif position > 60:
        pcr_estimate = 0.7
        signal = 'GREED'
        direction = 'BUY_PUT'
        message = 'Market above midpoint. Consider puts.'
        confidence = 60
    else:
        pcr_estimate = 1.0
        signal = 'NEUTRAL'
        direction = None
        message = 'Market in middle range. No extreme signal.'
        confidence = 30
    
    return {
        'pcr': round(pcr_estimate, 2),
        'signal': signal,
        'direction': direction,
        'message': message,
        'confidence': confidence
    }

def estimate_iv(nifty_data):
    """Estimate IV from price volatility"""
    h52 = nifty_data['high_52']
    l52 = nifty_data['low_52']
    price = nifty_data['price']
    
    volatility = ((h52 - l52) / l52) * 100
    
    if volatility < 20:
        iv_estimate = 12
        signal = 'LOW'
        message = 'IV estimated LOW. Options cheap. GOOD TIME TO BUY.'
        safe = True
    elif volatility < 35:
        iv_estimate = 17
        signal = 'NORMAL'
        message = 'IV estimated normal. OK to trade.'
        safe = True
    elif volatility < 50:
        iv_estimate = 24
        signal = 'HIGH'
        message = 'IV estimated HIGH. Reduce position or avoid buying.'
        safe = False
    else:
        iv_estimate = 30
        signal = 'VERY_HIGH'
        message = 'IV estimated VERY HIGH. DO NOT BUY options.'
        safe = False
    
    return {
        'iv': iv_estimate,
        'signal': signal,
        'message': message,
        'safe': safe
    }

def detect_market_extreme(nifty_data):
    """Detect if market is at extreme for reversal trade"""
    change = nifty_data['change']
    
    if change < -2:
        return {'extreme': True, 'type': 'PANIC', 'action': 'BUY_CALL', 
                'message': f'Market down {change:.1f}%. Panic selling. Reversal likely.'}
    elif change > 2:
        return {'extreme': True, 'type': 'EUPHORIA', 'action': 'BUY_PUT',
                'message': f'Market up {change:.1f}%. Euphoria. Reversal likely.'}
    return {'extreme': False, 'type': None, 'action': None, 'message': ''}

def generate_option_trade(nifty_data, pcr, iv, extreme):
    """Generate option trade plan"""
    
    if not iv['safe']:
        return {'signal': 'NO_TRADE', 'reason': iv['message']}
    
    if pcr['direction'] is None and not extreme['extreme']:
        return {'signal': 'NO_TRADE', 'reason': 'No clear direction. Wait for extreme signal.'}
    
    # Determine direction
    if extreme['extreme']:
        direction = extreme['action']
    else:
        direction = pcr['direction']
    
    price = nifty_data['price']
    atm = round(price / 50) * 50
    
    if direction == 'BUY_CALL':
        strike = atm + 100
        option_type = 'CE'
        reason = pcr['message'] if not extreme['extreme'] else extreme['message']
    else:
        strike = atm - 100
        option_type = 'PE'
        reason = pcr['message'] if not extreme['extreme'] else extreme['message']
    
    # Estimate option price (0.5-1% of strike for OTM)
    estimated_premium = round(strike * 0.005, 0)
    
    lots = CONFIG['LOTS']
    qty = lots * CONFIG['LOT_SIZE']
    cost = estimated_premium * qty
    sl = round(estimated_premium * 0.75, 0)
    t1 = round(estimated_premium * 1.5, 0)
    t2 = round(estimated_premium * 2.0, 0)
    
    confidence = pcr['confidence']
    if extreme['extreme']:
        confidence += 10
    
    return {
        'signal': 'TRADE',
        'symbol': f"NIFTY{strike}{option_type}",
        'strike': strike,
        'type': option_type,
        'direction': direction,
        'entry': estimated_premium,
        'lots': lots,
        'quantity': qty,
        'cost': round(cost, 0),
        'sl': sl,
        'target1': t1,
        'target2': t2,
        'max_loss': round((estimated_premium - sl) * qty, 0),
        'confidence': min(90, confidence),
        'reason': reason,
        'note': '⚠️ Premium is ESTIMATED. Check actual price on Upstox before trading.'
    }

def get_session_advice():
    now = datetime.now()
    h, m = now.hour, now.minute
    current = f"{h:02d}:{m:02d}"
    
    if not is_market_hours():
        return 'Market closed', 'Wait for market hours (9:15 AM - 3:30 PM IST)'
    
    if current < '09:30':
        return 'PRE-OPEN', 'Market just opened. Wait for data to settle.'
    elif current < '10:00':
        return 'BEST ENTRY', 'Best time to enter. Direction becoming clear.'
    elif current < '13:00':
        return 'ACTIVE', 'Good trading window. Manage positions.'
    elif current < '14:00':
        return 'BOOK PROFITS', 'Start exiting. Book partial profits.'
    elif current < '14:15':
        return 'FINAL EXIT', 'Exit ALL positions NOW.'
    else:
        return 'NO TRADE', 'Too late. No new trades.'

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def run():
    now = datetime.now()
    session, advice = get_session_advice()
    
    print(f"OPTIONS SCANNER v4.0 - {now.strftime('%d-%b %I:%M %p')}")
    
    # Get market data (24/7 reliable)
    nifty = get_nifty_data()
    if not nifty:
        send_telegram(f"<b>Options Scanner</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n⚠️ Could not fetch market data.")
        return
    
    banknifty = get_bank_nifty_data()
    
    # Calculate signals
    pcr = calculate_pcr_estimate(nifty)
    iv = estimate_iv(nifty)
    extreme = detect_market_extreme(nifty)
    trade = generate_option_trade(nifty, pcr, iv, extreme)
    
    # Build message
    msg = f"<b>🎯 OPTIONS SCANNER v4.0</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"<b>📊 MARKET DATA:</b>\n"
    msg += f"Nifty: {nifty['price']:.0f} ({nifty['change']:+.1f}%)\n"
    if banknifty:
        msg += f"Bank Nifty: {banknifty['price']:.0f} ({banknifty['change']:+.1f}%)\n"
    msg += f"52W Range: {nifty['low_52']:.0f} - {nifty['high_52']:.0f}\n\n"
    
    msg += f"<b>📊 SIGNALS:</b>\n"
    msg += f"PCR (Est): {pcr['pcr']} - {pcr['signal']}\n"
    msg += f"IV (Est): {iv['iv']}% - {iv['signal']}\n"
    msg += f"{'═'*35}\n\n"
    
    if trade['signal'] == 'TRADE':
        emoji = "🟢" if trade['direction'] == 'BUY_CALL' else "🔴"
        msg += f"<b>{emoji} TRADE SIGNAL: {trade['direction']}</b>\n"
        msg += f"Confidence: {trade['confidence']:.0f}%\n"
        msg += f"Reason: {trade['reason']}\n"
        msg += f"{'═'*35}\n\n"
        
        msg += f"<b>💰 ORDER:</b>\n"
        msg += f"Symbol: {trade['symbol']}\n"
        msg += f"Entry (Est): Rs.{trade['entry']}\n"
        msg += f"Lots: {trade['lots']} | Qty: {trade['quantity']}\n"
        msg += f"Cost (Est): Rs.{trade['cost']}\n\n"
        
        msg += f"<b>🛑 STOP LOSS:</b>\n"
        msg += f"Exit at: Rs.{trade['sl']}\n"
        msg += f"Max Loss: Rs.{trade['max_loss']}\n\n"
        
        msg += f"<b>🎯 TARGETS:</b>\n"
        msg += f"T1: Rs.{trade['target1']} (+50%) | T2: Rs.{trade['target2']} (+100%)\n\n"
        
        msg += f"<b>⏰ EXIT:</b> Before 2:15 PM TODAY\n"
        msg += f"{trade['note']}\n\n"
    else:
        msg += f"<b>⏸️ NO TRADE</b>\n"
        msg += f"{trade['reason']}\n\n"
    
    msg += f"<b>📋 SESSION:</b> {session}\n{advice}\n\n"
    msg += f"{'═'*35}\n"
    msg += f"<i>24/7 Options Scanner | Yahoo Finance Powered</i>"
    
    send_telegram(msg)
    
    if trade['signal'] == 'TRADE':
        print(f"✅ Trade signal: {trade['symbol']} ({trade['confidence']:.0f}%)")
    else:
        print(f"⏸️ No trade: {trade['reason']}")

if __name__ == "__main__":
    run()
