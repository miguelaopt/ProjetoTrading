import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from google import genai
import yfinance as yf
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv # <--- NOVA IMPORTAÇÃO

# Carrega as variáveis do ficheiro .env (apenas no teu PC)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO SEGURA ---
# O código vai buscar a chave ao sistema. Se não encontrar, dá erro ou None.
API_KEY = os.getenv("GENAI_API_KEY") 

if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    print("⚠️ AVISO: API Key não encontrada! Configura o .env ou as variáveis no Render.")

# Configurações de Base de Dados e Segurança
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "chave-secreta-padrao-dev") # Usa a do .env ou uma default

# Lógica Híbrida de Base de Dados (Postgres no Render / SQLite no PC)
database_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login_page'
login_manager.init_app(app)

# --- MODELO DA BASE DE DADOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200)) # Aumentei para 200 por causa do hash longo
    name = db.Column(db.String(100))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- FUNÇÕES AUXILIARES ---
def get_quick_ticker_data():
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD']
    data = []
    try:
        for t in tickers:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if len(hist) >= 1:
                curr = hist['Close'].iloc[-1]
                change = 0
                if len(hist) >= 2:
                    prev = hist['Close'].iloc[-2]
                    change = ((curr - prev) / prev) * 100
                data.append({
                    "symbol": t.replace("-USD", ""),
                    "price": f"${curr:,.2f}" if curr > 1 else f"${curr:.4f}", 
                    "change": f"{abs(change):.2f}", 
                    "color": "green" if change >= 0 else "red",
                    "sign": "+" if change >= 0 else "-"
                })
    except: pass
    return data

def smart_format(value):
    if value < 1.0: return f"${value:.8f}"
    else: return f"${value:,.2f}"

# --- ROTAS PÚBLICAS ---
@app.route('/')
def home():
    ticker_data = get_quick_ticker_data()
    return render_template('home.html', active_page='home', ticker_data=ticker_data)

@app.route('/crypto')
def crypto_page():
    return render_template('crypto.html', active_page='crypto')

@app.route('/etf')
def etf_page():
    return render_template('etf.html', active_page='etf')

# --- AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Email ou password incorretos.')
            return redirect(url_for('login_page'))
        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('crypto_page'))
    return render_template('auth.html', mode='login')

@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email já existe.')
            return redirect(url_for('login_page'))
        new_user = User(email=email, name=name, password=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('crypto_page'))
    return render_template('auth.html', mode='signup')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# --- ROTAS PROTEGIDAS (PÁGINAS) ---
@app.route('/screener')
@login_required 
def screener_page(): return render_template('screener.html', active_page='screener')

@app.route('/ai')
@login_required
def ai_page(): return render_template('ai.html', active_page='ai')

@app.route('/risk')
@login_required
def risk_page(): return render_template('risk.html', active_page='risk')

@app.route('/crypto/analyze')
@login_required
def crypto_analyze_page(): return render_template('crypto_analyze.html', active_page='crypto')

@app.route('/crypto/recommend')
@login_required
def crypto_recommend_page(): return render_template('crypto_recommend.html', active_page='crypto')

@app.route('/crypto/strategy')
@login_required
def crypto_strategy_page(): return render_template('crypto_strategy.html', active_page='crypto')

@app.route('/crypto/decoder')
@login_required
def crypto_decoder_page(): return render_template('crypto_decoder.html', active_page='crypto')

# --- APIS PROTEGIDAS ---
@app.route('/analyze_user_coin', methods=['POST'])
@login_required
def analyze_user_coin():
    try:
        data = request.json
        raw_ticker = data.get('ticker', '').strip().upper()
        investment = float(data.get('investment', 0))
        
        if not raw_ticker: return jsonify({"error": "Escreve o nome da moeda!"})
        yf_ticker = f"{raw_ticker}-USD" if not raw_ticker.endswith(("USD", "-USD")) else raw_ticker
        
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="1mo")
        if hist.empty:
            stock = yf.Ticker(raw_ticker)
            hist = stock.history(period="1mo")
            if hist.empty: return jsonify({"error": f"Moeda '{raw_ticker}' não encontrada."})

        current_price = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        perf_30d = ((current_price - start_price) / start_price) * 100

        prompt = f"""
        Age como Mentor Trading. Investimento: ${investment} em {raw_ticker}.
        Preço: {current_price:.8f}. Perf 30d: {perf_30d:.2f}%.
        JSON EXATO: {{"verdict": "...", "explanation": "...", "entry": 0.0, "stop_loss": 0.0, "take_profit": 0.0, "risk_level": "..."}}
        """
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        import json
        ai_data = json.loads(response.text.replace('```json', '').replace('```', ''))
        
        shares = investment / current_price
        pot_profit = (ai_data['take_profit'] - current_price) * shares
        pot_loss = (current_price - ai_data['stop_loss']) * shares
        roi = ((ai_data['take_profit'] - current_price) / current_price) * 100
        
        return jsonify({
            "ticker": raw_ticker,
            "current_price": smart_format(current_price),
            "verdict": ai_data['verdict'],
            "explanation": ai_data['explanation'],
            "risk_level": ai_data['risk_level'],
            "plan": { "entry": smart_format(ai_data['entry']), "stop": smart_format(ai_data['stop_loss']), "target": smart_format(ai_data['take_profit']) },
            "math": { "shares": f"{shares:,.2f}", "potential_profit": f"€{pot_profit:.2f}", "potential_loss": f"€{pot_loss:.2f}", "roi": f"{roi:.1f}%" }
        })
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/get_recommendations', methods=['GET'])
def get_recommendations():
    try:
        candidates = ['SOL-USD', 'DOGE-USD', 'AVAX-USD', 'LINK-USD', 'FET-USD']
        recommendations = []
        for t in candidates:
            stock = yf.Ticker(t)
            hist = stock.history(period="5d")
            if len(hist) > 1:
                curr = hist['Close'].iloc[-1]
                change = ((curr - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                if change > 0:
                    recommendations.append({
                        "ticker": t.replace("-USD", ""),
                        "price": smart_format(curr),
                        "change_5d": f"+{change:.1f}%",
                        "target": smart_format(curr*1.10),
                        "stop": smart_format(curr*0.95),
                        "roi": "10.0%",
                        "tag": "Momentum"
                    })
        return jsonify(recommendations)
    except: return jsonify([])

@app.route('/generate_portfolio', methods=['POST'])
@login_required
def generate_portfolio():
    try:
        data = request.json
        prompt = f"Portfolio crypto €{data.get('capital')}, Risco {data.get('risk')}. JSON: {{'explanation': '...', 'allocation': [{{'asset': '...', 'pct': 50}}]}}"
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        import json
        ai_data = json.loads(response.text.replace('```json', '').replace('```', ''))
        allocation = [{"asset": i['asset'], "pct": i['pct'], "value": f"€{float(data.get('capital'))*(i['pct']/100):,.2f}"} for i in ai_data['allocation']]
        return jsonify({"explanation": ai_data['explanation'], "allocation": allocation})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/decode_market', methods=['POST'])
@login_required
def decode_market():
    try:
        prompt = f"Explica simples iniciante: {request.json.get('question')}"
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return jsonify({"answer": response.text})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/get_market_data')
def get_market_data():
    cryptos = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'AVAX-USD', 'SHIB-USD', 'DOT-USD', 'LINK-USD', 'TRX-USD', 'MATIC-USD', 'LTC-USD', 'BCH-USD', 'UNI7083-USD', 'XLM-USD', 'ATOM-USD', 'XMR-USD', 'ETC-USD']
    etfs = ['SPY', 'QQQ', 'VOO', 'IWM', 'GLD', 'EEM', 'NVDA', 'TSLA', 'AMD', 'MSFT']
    def fetch(tickers):
        data = []
        try:
            for t in tickers:
                stock = yf.Ticker(t)
                hist = stock.history(period="2d")
                if len(hist) >= 1:
                    curr = hist['Close'].iloc[-1]
                    change = ((curr - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100 if len(hist) >= 2 else 0
                    data.append({"symbol": t.replace("-USD", "").replace("7083",""), "price": smart_format(curr), "raw_price": curr, "change": round(change, 2)})
        except: pass
        return data
    cd = fetch(cryptos)
    cd.sort(key=lambda x: x['raw_price'], reverse=True)
    return jsonify({"crypto": cd, "etf": fetch(etfs)})

if __name__ == '__main__':
    app.run(debug=True)