"""
OPTIONS SCANNER - DEBUG VERSION
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

# ===== DEBUG: Print config =====
print("=" * 50)
print("DEBUG INFO:")
print(f"Bot Token exists: {TELEGRAM_BOT_TOKEN is not None}")
print(f"Bot Token length: {len(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else 0}")
print(f"Chat ID: {TELEGRAM_CHAT_ID}")
print("=" * 50)

def send_test_message():
    """Simple test to verify Telegram connection"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing token or chat ID!")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    test_text = f"🧪 Options Scanner Test\n{datetime.now().strftime('%d-%b %I:%M %p')}\n\nConnection successful!"
    
    try:
        print(f"Sending to chat ID: {TELEGRAM_CHAT_ID}")
        resp = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': test_text,
            'parse_mode': 'HTML'
        }, timeout=10)
        
        result = resp.json()
        print(f"Telegram Response: {json.dumps(result, indent=2)}")
        
        if result.get('ok'):
            print("✅ Test message sent!")
            return True
        else:
            print(f"❌ Failed: {result.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def fetch_nifty_options():
    """Fetch Nifty options with debug"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        
        print("Fetching NSE session...")
        session.get('https://www.nseindia.com', timeout=10)
        
        url = 'https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY'
        print("Fetching options chain...")
        response = session.get(url, timeout=15)
        
        print(f"NSE Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', {}).get('data', [])
            print(f"Records found: {len(records)}")
            return records
        else:
            print(f"NSE Error: {response.text[:200]}")
    except Exception as e:
        print(f"NSE Fetch Error: {e}")
    return []

def analyze_options(data):
    """Simple analysis"""
    alerts = []
    
    for record in data[:30]:  # First 30 records
        if 'CE' in record:
            ce = record['CE']
            strike = ce.get('strikePrice', 0)
            oi = ce.get('openInterest', 0)
            oi_change = ce.get('changeinOpenInterest', 0)
            ltp = ce.get('lastPrice', 0)
            volume = ce.get('totalTradedVolume', 0)
            
            if oi > 0 and oi_change > 0:
                oi_pct = (oi_change / (oi - oi_change)) * 100
                if oi_pct > 5 and volume > 1000:
                    alerts.append(f"CE {strike}: OI +{oi_pct:.1f}% | LTP: {ltp} | Vol: {volume}")
    
    return alerts

def build_message(alerts):
    now = datetime.now()
    msg = f"<b>OPTIONS SCANNER</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*30}\n\n"
    
    if alerts:
        msg += f"<b>OI Spurt Alerts ({len(alerts)} found):</b>\n\n"
        for alert in alerts[:10]:
            msg += f"• {alert}\n"
    else:
        msg += f"No significant OI changes detected.\n"
        msg += f"Market may be in consolidation.\n"
    
    msg += f"\n{'═'*30}\n"
    msg += f"Options Scanner Test"
    return msg

# ===== MAIN =====
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("OPTIONS SCANNER STARTING")
    print("=" * 50)
    
    # STEP 1: Test Telegram
    print("\n📱 Testing Telegram connection...")
    if not send_test_message():
        print("❌ Telegram failed - stopping")
        exit(1)
    
    # STEP 2: Fetch NSE data
    print("\n📊 Fetching NSE options data...")
    data = fetch_nifty_options()
    
    if not data:
        print("❌ No NSE data - sending error to Telegram")
        send_test_message()
        exit(1)
    
    # STEP 3: Analyze
    print("\n🔍 Analyzing options...")
    alerts = analyze_options(data)
    print(f"Alerts found: {len(alerts)}")
    
    # STEP 4: Send results
    print("\n📱 Sending analysis...")
    msg = build_message(alerts)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': msg,
        'parse_mode': 'HTML'
    }, timeout=10)
    
    result = resp.json()
    print(f"Send result: {json.dumps(result, indent=2)}")
    
    if result.get('ok'):
        print("✅ Analysis sent to Telegram!")
    else:
        print(f"❌ Send failed: {result.get('description')}")
