from flask import Flask, render_template, jsonify, request
from google import genai
import yfinance as yf

app = Flask(__name__)

API_KEY = "AIzaSyBmMHvghgV13qHOzv-OcyCT887MZacnnzo"
if API_KEY:
    client = genai.Client(api_key=API_KEY)

# --- ROTAS DAS PÁGINAS (LINKS DO MENU) ---
@app.route('/')
def home():
    return render_template('home.html', active_page='home')

@app.route('/crypto')
def crypto_page():
    return render_template('crypto.html', active_page='crypto')

@app.route('/etf')
def etf_page():
    return render_template('etf.html', active_page='etf')

@app.route('/login')
def login_page():
    return render_template('auth.html', mode='login')

@app.route('/signup')
def signup_page():
    return render_template('auth.html', mode='signup')

# --- ROTAS DAS FERRAMENTAS ---
@app.route('/screener')
def screener_page():
    return render_template('screener.html', active_page='screener')

@app.route('/ai')
def ai_page():
    return render_template('ai.html', active_page='ai')

@app.route('/risk')
def risk_page():
    return render_template('risk.html', active_page='risk')

# --- API DE DADOS (Mantém-se igual para alimentar as páginas) ---
@app.route('/get_market_data')
def get_market_data():
    # (O mesmo código de antes para buscar dados)
    cryptos = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'BNB-USD', 'ADA-USD']
    etfs = ['SPY', 'QQQ', 'VOO', 'IWM', 'GLD', 'EEM']
    
    def fetch(tickers):
        data = []
        try:
            for t in tickers:
                stock = yf.Ticker(t)
                hist = stock.history(period="2d")
                if len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change = ((curr - prev) / prev) * 100
                    data.append({
                        "symbol": t.replace("-USD", ""),
                        "price": round(curr, 2),
                        "change": round(change, 2)
                    })
        except: pass
        return data

    return jsonify({
        "crypto": fetch(cryptos),
        "etf": fetch(etfs)
    })

if __name__ == '__main__':
    app.run(debug=True)