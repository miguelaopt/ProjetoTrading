import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from google import genai
# Importar tipos para configurar a API corretamente
from google.genai import types 
import yfinance as yf
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
API_KEY = os.getenv("GENAI_API_KEY")
if not API_KEY:
    print("ERRO CRÍTICO: GENAI_API_KEY não encontrada!")

# Configurar cliente
if API_KEY:
    client = genai.Client(api_key=API_KEY)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "chave-secreta-dev")

# DB Híbrida
database_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login_page'
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    name = db.Column(db.String(100))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- FUNÇÕES AUXILIARES DE LIMPEZA (A CURA PARA O ERRO) ---
def clean_ai_response(text):
    """
    Procura o primeiro '{' e o último '}' para extrair apenas o JSON,
    ignorando texto introdutório ou erros de markdown.
    """
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end == 0:
            return None
        json_str = text[start:end]
        return json_str
    except:
        return None

def smart_format(value):
    if value < 1.0: return f"${value:.8f}"
    else: return f"${value:,.2f}"

def get_quick_ticker_data():
    # ... (Mantém a tua função igual) ...
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD']
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
                    "price": smart_format(curr),
                    "change": f"{abs(change):.2f}",
                    "color": "green" if change >= 0 else "red",
                    "sign": "+" if change >= 0 else "-"
                })
    except: pass
    return data

# --- ROTAS NORMAIS (Home, Crypto, Auth...) ---
# (Mantém o código igual ao anterior para estas rotas: /, /crypto, /login, /signup, /logout)
@app.route('/')
def home():
    ticker_data = get_quick_ticker_data()
    return render_template('home.html', active_page='home', ticker_data=ticker_data)

@app.route('/crypto')
def crypto_page(): return render_template('crypto.html', active_page='crypto')

@app.route('/etf')
def etf_page(): return render_template('etf.html', active_page='etf')

@app.route('/screener')
@login_required 
def screener_page():
    # Cria o ficheiro screener.html se não existir, senão dá erro de template
    return render_template('screener.html', active_page='screener')

@app.route('/ai')
@login_required
def ai_page():
    return render_template('ai.html', active_page='ai')

@app.route('/risk')
@login_required
def risk_page():
    return render_template('risk.html', active_page='risk')

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
        return redirect(request.args.get('next') or url_for('crypto_page'))
    return render_template('auth.html', mode='login')

@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
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

# --- ROTAS DE PÁGINAS PROTEGIDAS ---
# (Mantém os renders das páginas HTML: /crypto/analyze, etc...)
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


# --- APIS CORRIGIDAS (AQUI ESTÁ O FIX) ---
@app.route('/analyze_user_coin', methods=['POST'])
@login_required
def analyze_user_coin():
    try:
        data = request.json
        raw_ticker = data.get('ticker', '').strip().upper()
        investment = float(data.get('investment', 0))
        
        # 1. Obter Preço (YFinance)
        # Tentativa 1: Com -USD
        yf_ticker = f"{raw_ticker}-USD" if not raw_ticker.endswith(("USD", "-USD")) else raw_ticker
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="1mo")
        
        # Tentativa 2: Sem -USD (Se falhar a primeira)
        if hist.empty:
            stock = yf.Ticker(raw_ticker)
            hist = stock.history(period="1mo")
            if hist.empty:
                return jsonify({"error": f"Não consegui ler o preço de '{raw_ticker}'. Verifica o nome."})

        current_price = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        perf_30d = ((current_price - start_price) / start_price) * 100

        # 2. Prompt
        prompt = f"""
        És um especialista financeiro. Analisa o ativo {raw_ticker}.
        Dados Atuais: Preço ${current_price:.8f}, Performance 30d {perf_30d:.2f}%.
        O utilizador quer investir ${investment}.
        
        Gera um JSON com esta estrutura exata:
        {{
            "verdict": "Compra, Venda ou Espera",
            "explanation": "Uma frase curta em PT-PT.",
            "entry": (valor float sugerido para entrada),
            "stop_loss": (valor float para stop loss),
            "take_profit": (valor float para alvo),
            "risk_level": "Baixo, Médio ou Alto"
        }}
        """
        
        # 3. Chamar AI com MODO JSON FORÇADO (O Segredo!)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json' 
            )
        )
        
        # Debug: Ver nos logs do Render o que chegou
        print(f"AI Resposta para {raw_ticker}: {response.text}")

        # 4. Ler JSON (Agora é seguro porque forçámos o formato)
        import json
        ai_data = json.loads(response.text)
        
        # 5. Cálculos Matemáticos (Protegidos contra divisão por zero)
        if current_price > 0:
            shares = investment / current_price
            pot_profit = (ai_data['take_profit'] - current_price) * shares
            pot_loss = (current_price - ai_data['stop_loss']) * shares
            roi = ((ai_data['take_profit'] - current_price) / current_price) * 100
        else:
            shares, pot_profit, pot_loss, roi = 0, 0, 0, 0
        
        # Função auxiliar local para formatar
        def fmt(val): 
            return f"${val:.8f}" if val < 1 else f"${val:,.2f}"

        return jsonify({
            "ticker": raw_ticker,
            "current_price": fmt(current_price),
            "verdict": ai_data['verdict'],
            "explanation": ai_data['explanation'],
            "risk_level": ai_data['risk_level'],
            "plan": { 
                "entry": fmt(ai_data['entry']), 
                "stop": fmt(ai_data['stop_loss']), 
                "target": fmt(ai_data['take_profit']) 
            },
            "math": { 
                "shares": f"{shares:,.2f}", 
                "potential_profit": f"€{pot_profit:.2f}", 
                "potential_loss": f"€{pot_loss:.2f}", 
                "roi": f"{roi:.1f}%" 
            }
        })

    except Exception as e:
        print(f"ERRO CRÍTICO ANALISAR: {e}")
        # Retorna o erro real para o ecrã para saberes o que se passa
        return jsonify({"error": f"Erro interno: {str(e)}"})

@app.route('/generate_portfolio', methods=['POST'])
@login_required
def generate_portfolio():
    try:
        data = request.json
        prompt = f"""
        Cria portfolio crypto €{data.get('capital')}, Risco {data.get('risk')}.
        JSON EXATO: {{'explanation': '...', 'allocation': [{{'asset': 'Nome', 'pct': 50}}]}}
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        # Limpar JSON
        import json
        json_str = clean_ai_response(response.text)
        if not json_str: return jsonify({"error": "Erro na resposta da AI"})
        
        ai_data = json.loads(json_str)
        
        allocation = [{"asset": i['asset'], "pct": i['pct'], "value": f"€{float(data.get('capital'))*(i['pct']/100):,.2f}"} for i in ai_data['allocation']]
        return jsonify({"explanation": ai_data['explanation'], "allocation": allocation})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/decode_market', methods=['POST'])
@login_required
def decode_market():
    try:
        prompt = f"Explica simples iniciante (max 3 frases): {request.json.get('question')}"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return jsonify({"answer": response.text})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/get_market_data')
def get_market_data():
    # (Mantém a tua função do Top 20 igual)
    cryptos = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'DOGE-USD', 'ADA-USD', 'AVAX-USD', 'SHIB-USD', 'DOT-USD']
    etfs = ['SPY', 'QQQ', 'VOO']
    def fetch(tickers):
        data = []
        try:
            for t in tickers:
                stock = yf.Ticker(t)
                hist = stock.history(period="2d")
                if len(hist) >= 1:
                    curr = hist['Close'].iloc[-1]
                    change = ((curr - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100 if len(hist) >= 2 else 0
                    data.append({"symbol": t.replace("-USD", ""), "price": smart_format(curr), "raw_price": curr, "change": round(change, 2)})
        except: pass
        return data
    cd = fetch(cryptos)
    cd.sort(key=lambda x: x['raw_price'], reverse=True)
    return jsonify({"crypto": cd, "etf": fetch(etfs)})

@app.route('/get_recommendations', methods=['GET'])
def get_recommendations():
    try:
        # Lista de candidatos
        candidates = ['SOL-USD', 'DOGE-USD', 'AVAX-USD', 'LINK-USD', 'FET-USD', 'PEPE-USD', 'XRP-USD']
        recommendations = []
        
        for t in candidates:
            try:
                # Proteção Individual: Se esta moeda falhar, passa à próxima
                stock = yf.Ticker(t)
                hist = stock.history(period="5d")
                
                if len(hist) > 1:
                    curr = hist['Close'].iloc[-1]
                    start = hist['Close'].iloc[0]
                    change = ((curr - start) / start) * 100
                    
                    # Só recomenda se tiver subido (Momentum)
                    if change > 0:
                        recommendations.append({
                            "ticker": t.replace("-USD", ""),
                            "price": f"${curr:.4f}" if curr < 1 else f"${curr:.2f}",
                            "change_5d": f"+{change:.1f}%",
                            "target": f"${curr*1.15:.4f}" if curr < 1 else f"${curr*1.15:.2f}", # Alvo +15%
                            "stop": f"${curr*0.90:.4f}" if curr < 1 else f"${curr*0.90:.2f}",   # Stop -10%
                            "roi": "Potencial Alto",
                            "tag": "Momentum"
                        })
            except Exception as inner_e:
                print(f"Erro ao ler {t}: {inner_e}")
                continue # Continua para a próxima moeda

        return jsonify(recommendations)

    except Exception as e:
        print(f"Erro Geral Recommendations: {e}")
        return jsonify([]) # Retorna lista vazia em vez de crashar

if __name__ == '__main__':
    app.run(debug=True)