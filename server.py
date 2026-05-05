from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime
import time

app = Flask(__name__)

# ════════════════════════════════════════════════════════════════
# ⚙️ الإعدادات
# ════════════════════════════════════════════════════════════════
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "abuwasem123")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3"))

# ════════════════════════════════════════════════════════════════
# 📦 Cache بسيط
# ════════════════════════════════════════════════════════════════
cache = {}

def get_cache(key):
    if key in cache:
        data, timestamp = cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None

def set_cache(key, data):
    cache[key] = (data, time.time())

# ════════════════════════════════════════════════════════════════
# 🔐 التحقق
# ════════════════════════════════════════════════════════════════
def check_secret(data):
    return data.get('secret') == WEBHOOK_SECRET

# ════════════════════════════════════════════════════════════════
# 🐋 جلب بيانات Polygon.io
# ════════════════════════════════════════════════════════════════
def fetch_whale_data(symbol, min_value=100000):
    if not POLYGON_API_KEY:
        return {"error": "API key missing", "data": []}
    
    base_url = "https://api.polygon.io"
    
    result = {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "whales": [],
        "darkpool": [],
        "stats": {}
    }
    
    try:
        # 1. جلب Options (الخيارات)
        options_url = f"{base_url}/v3/reference/options/contracts"
        params = {
            "underlying_ticker": symbol,
            "apiKey": POLYGON_API_KEY,
            "limit": 20
        }
        
        resp = requests.get(options_url, params=params, timeout=10)
        if resp.status_code == 200:
            options_data = resp.json()
            for item in options_data.get('results', [])[:10]:
                result["whales"].append({
                    "type": "CALL" if item.get("contract_type") == "call" else "PUT",
                    "strike": float(item.get("strike_price", 0)),
                    "premium": float(item.get("strike_price", 0)) * 100,  # تقدير
                    "volume": int(item.get("volume", 0)),
                    "expiry": item.get("expiration_date", ""),
                    "sentiment": "bullish" if item.get("contract_type") == "call" else "bearish",
                    "time": datetime.now().isoformat()
                })
        
        # 2. إحصائيات
        puts = sum(1 for w in result["whales"] if w["type"] == "PUT")
        calls = sum(1 for w in result["whales"] if w["type"] == "CALL")
        total = puts + calls
        
        result["stats"] = {
            "put_call_ratio": round(puts / total, 2) if total > 0 else 0.5,
            "total_premium": sum(w["premium"] for w in result["whales"]),
            "net_premium": sum(w["premium"] if w["type"] == "CALL" else -w["premium"] for w in result["whales"]),
            "whale_count": len(result["whales"]),
            "put_count": puts,
            "call_count": calls
        }
        
    except Exception as e:
        result["error"] = str(e)
    
    return result

# ════════════════════════════════════════════════════════════════
# 🎯 Routes
# ════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    return jsonify({
        "🐋": "Whale Detector Server",
        "status": "running",
        "time": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"ok": True})

@app.route('/whales', methods=['POST'])
def whales():
    data = request.json or {}
    if not check_secret(data):
        return jsonify({"error": "bad secret"}), 401
    
    symbol = data.get('symbol', 'SPY').upper()
    min_val = data.get('threshold', 100000)
    
    cache_key = f"{symbol}_{min_val}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)
    
    result = fetch_whale_data(symbol, min_val)
    set_cache(cache_key, result)
    return jsonify(result)

@app.route('/indicator', methods=['POST'])
def indicator():
    data = request.json or {}
    if not check_secret(data):
        return jsonify({"error": "bad secret"}), 401
    
    symbol = data.get('symbol', 'SPY').upper()
    min_val = data.get('threshold', 100000)
    
    cache_key = f"ind_{symbol}_{min_val}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)
    
    full = fetch_whale_data(symbol, min_val)
    
    simple = {
        "timestamp": full.get("timestamp"),
        "symbol": symbol,
        "whale_detected": len(full.get("whales", [])) > 0,
        "latest_whales": full.get("whales", [])[:5],
        "put_call_ratio": full.get("stats", {}).get("put_call_ratio", 0.5),
        "net_premium": full.get("stats", {}).get("net_premium", 0),
        "total_premium": full.get("stats", {}).get("total_premium", 0),
        "darkpool": full.get("darkpool", [])[:3],
        "stats": full.get("stats", {})
    }
    
    set_cache(cache_key, simple)
    return jsonify(simple)

# ════════════════════════════════════════════════════════════════
# ▶️ Run
# ════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ════════════════════════════════════════════════════════════════
# 🎯 للـ Render (مهم!)
# ════════════════════════════════════════════════════════════════
application = app
