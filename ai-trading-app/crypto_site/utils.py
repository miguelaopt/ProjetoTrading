# utils.py
import os
import requests
import feedparser
import yfinance as yf
from google import genai
from google.genai import types
from extensions import cache

# Configuração da AI
API_KEY = os.getenv("GENAI_API_KEY")
client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
    except:
        print("Erro ao iniciar AI")

def smart_format(value):
    if value is None: return "$0.00"
    if value < 1.0: return f"${value:.8f}"
    else: return f"${value:,.2f}"

def get_user_badges(user):
    badges = []
    if user.transactions and len(user.transactions) > 0:
        badges.append({'icon': 'fa-rocket', 'color': '#3498db', 'title': 'Iniciado', 'desc': 'Fez o primeiro trade'})
    if user.transactions and len(user.transactions) >= 10:
        badges.append({'icon': 'fa-medal', 'color': '#9b59b6', 'title': 'Veterano', 'desc': 'Mais de 10 operações'})
    if user.virtual_balance >= 15000:
         badges.append({'icon': 'fa-crown', 'color': '#f1c40f', 'title': 'Baleia', 'desc': 'Lucro superior a 50%'})
    if hasattr(user, 'special_role'):
        if user.special_role == 'ADMIN':
            badges.append({'icon': 'fa-shield-halved', 'color': '#e74c3c', 'title': 'Admin', 'desc': 'Staff'})
        elif user.special_role == 'VIP':
            badges.append({'icon': 'fa-star', 'color': '#d35400', 'title': 'VIP', 'desc': 'Membro VIP'})
    return badges

def get_stock_price(symbol):
    try:
        # Tenta pegar preço rápido
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.last_price
        return price
    except:
        return None

def get_market_sentiment():
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = response.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return {"value": value, "text": classification}
    except:
        return {"value": 50, "text": "Neutral (Offline)"}

def get_market_movers():
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'AVAX-USD', 'LINK-USD', 'SHIB-USD', 'DOT-USD']
    movers_data = []
    try:
        tickers_str = " ".join(tickers)
        data = yf.download(tickers_str, period="2d", progress=False)['Close']
        for t in tickers:
            try:
                # Tratar caso de indexação do yfinance
                if len(tickers) == 1:
                     current = data.iloc[-1]
                     prev = data.iloc[-2]
                else:
                    current = data[t].iloc[-1]
                    prev = data[t].iloc[-2]
                
                change = ((current - prev) / prev) * 100
                symbol = t.replace('-USD', '')
                movers_data.append({'symbol': symbol, 'change': change, 'price': current})
            except: continue
            
        movers_data.sort(key=lambda x: x['change'], reverse=True)
        # Gainers (Top 3), Losers (Bottom 3 ordenados do pior para o melhor visualmente)
        return movers_data[:3], sorted(movers_data[-3:], key=lambda x: x['change'])
    except:
        return [], []

@cache.memoize(timeout=120)
def get_top_cryptos(limit=5):
    # Lista segura e estável
    top_tickers = [
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 
        'DOGE-USD', 'ADA-USD', 'AVAX-USD', 'TRX-USD', 'LINK-USD', 
        'DOT-USD', 'LTC-USD', 'BCH-USD', 'SHIB-USD', 'ADA-USD'
    ]
    limit = min(limit, len(top_tickers))
    selected = top_tickers[:limit]
    data = []
    try:
        tickers = yf.Tickers(" ".join(selected))
        for symbol in selected:
            try:
                ticker_obj = tickers.tickers.get(symbol)
                if not ticker_obj: continue
                info = ticker_obj.fast_info
                
                price = info.last_price
                prev_close = info.previous_close
                if price is None or prev_close is None: continue
                
                change_pct = ((price - prev_close) / prev_close) * 100
                clean_symbol = symbol.replace("-USD", "")
                
                supported_icons = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LTC', 'BCH', 'DOT', 'LINK']
                if clean_symbol in supported_icons:
                    icon_class = f"fa-brands fa-{clean_symbol.lower()}"
                else:
                    icon_class = "fa-solid fa-coins"

                data.append({
                    "symbol": clean_symbol,
                    "price": smart_format(price),
                    "change": f"{change_pct:+.2f}%",
                    "change_raw": change_pct,
                    "icon": icon_class,
                    "color": "text-green" if change_pct >= 0 else "text-red"
                })
            except: continue
    except: pass
    return data

def get_quick_ticker_data():
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD']
    data = []
    try:
        for t in tickers:
            stock = yf.Ticker(t)
            price = stock.fast_info.last_price
            prev = stock.fast_info.previous_close
            change = ((price - prev) / prev) * 100
            data.append({
                "symbol": t.replace("-USD", ""),
                "price": smart_format(price),
                "change": f"{abs(change):.2f}",
                "color": "green" if change >= 0 else "red",
                "sign": "+" if change >= 0 else "-"
            })
    except: pass
    return data