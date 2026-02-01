import os
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from google import genai
from google.genai import types
import yfinance as yf
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests
from flask_caching import Cache


# --- CONFIGURAÇÃO INICIAL ---

# Carregar variáveis de ambiente (Força UTF-8 para evitar erro no Windows)
load_dotenv(encoding="utf-8")

app = Flask(__name__)

# CONFIGURAÇÃO DE CACHE (Memória Simples)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 60})

# Configuração da Chave Secreta e API
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "chave-secreta-padrao")
API_KEY = os.getenv("GENAI_API_KEY")

if not API_KEY:
    print("⚠️ AVISO: GENAI_API_KEY não encontrada no .env")

# Cliente Google Gemini
if API_KEY:
    client = genai.Client(api_key=API_KEY)

# Configuração da Base de Dados
# Tenta usar a do .env, senão usa SQLite local por defeito
database_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite")

# Correção para PostgreSQL no Render (se usares no futuro)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login_page'
login_manager.init_app(app)

# --- MODELOS DA BASE DE DADOS (ATUALIZADOS) ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(100))
    avatar = db.Column(db.String(50), default='fa-user')
    special_role = db.Column(db.String(50), nullable=True)

    
    # Paper Trading: Saldo Virtual (Começa com 10k)
    virtual_balance = db.Column(db.Float, default=10000.0)
    
    # Relações
    portfolio = db.relationship('Portfolio', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False) # Ex: BTC
    amount = db.Column(db.Float, nullable=False)      # Quantidade
    avg_price = db.Column(db.Float, nullable=False)   # Preço médio de compra

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)   # 'BUY' ou 'SELL'
    price = db.Column(db.Float, nullable=False)       # Preço na hora
    amount = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False) # Custo total
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Criar tabelas se não existirem
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    # A função .get() antiga foi substituída por db.session.get()
    return db.session.get(User, int(user_id))

# --- FUNÇÕES AUXILIARES ---

def get_user_badges(user):
    badges = []
    
    # --- BADGE 1: INICIADO (Fez 1 trade) ---
    # Verifica se transactions existe e tem itens
    if user.transactions and len(user.transactions) > 0:
        badges.append({'icon': 'fa-rocket', 'color': '#3498db', 'title': 'Iniciado', 'desc': 'Fez o primeiro trade'})
        
    # --- BADGE 2: VETERANO (10+ trades) ---
    if user.transactions and len(user.transactions) >= 10:
        badges.append({'icon': 'fa-medal', 'color': '#9b59b6', 'title': 'Veterano', 'desc': 'Mais de 10 operações'})

    # --- BADGE 3: BALEIA (Lucro > 50%) ---
    # Se o saldo for > 15k (começa com 10k)
    if user.virtual_balance >= 15000:
         badges.append({'icon': 'fa-crown', 'color': '#f1c40f', 'title': 'Baleia', 'desc': 'Lucro superior a 50%'})
    
    # --- BADGE 4: ADMIN/VIP (Manual) ---
    # Verifica se a coluna existe para evitar erros se não atualizaste a BD
    if hasattr(user, 'special_role'):
        if user.special_role == 'ADMIN':
            badges.append({'icon': 'fa-shield-halved', 'color': '#e74c3c', 'title': 'Admin', 'desc': 'Staff'})
        elif user.special_role == 'VIP':
            badges.append({'icon': 'fa-star', 'color': '#d35400', 'title': 'VIP', 'desc': 'Membro VIP'})

    return badges

# --- ADICIONAR NO APP.PY ---

def calculate_user_net_worth(user):
    """Calcula o património total (Saldo + Valor das Moedas em carteira)"""
    total_value = user.virtual_balance
    
    # Se o user tiver portfolio, somar o valor atual das moedas
    if user.portfolio:
        # Para ser rápido no leaderboard, vamos tentar usar cache ou valores aproximados
        # Mas aqui vamos buscar live para ser preciso
        for item in user.portfolio:
            try:
                # Tenta buscar preço rápido
                ticker_name = f"{item.symbol}-USD"
                ticker = yf.Ticker(ticker_name)
                # fast_info é mais rápido que history
                current_price = ticker.fast_info.last_price 
                if current_price:
                    total_value += (item.amount * current_price)
                else:
                    total_value += (item.amount * item.avg_price) # Fallback
            except:
                total_value += (item.amount * item.avg_price) # Fallback seguro
                
    return total_value

@app.route('/leaderboard')
def leaderboard_page():
    users = User.query.all()
    leaderboard_data = []
    
    for u in users:
        # Calcular Net Worth (Simplificado)
        net_worth = u.virtual_balance
        if u.portfolio:
            for item in u.portfolio:
                net_worth += (item.amount * item.avg_price) # Simplificado

        pnl_pct = ((net_worth - 10000) / 10000) * 100
        
        # AQUI ESTÁ A CORREÇÃO: Usar a mesma função para toda a gente
        user_badges = get_user_badges(u)
        
        leaderboard_data.append({
            'username': u.username,
            'avatar': u.avatar if u.avatar else 'fa-user',
            'net_worth': net_worth,
            'pnl_pct': pnl_pct,
            'badges': user_badges, # <--- IMPORTANTE: Enviar para o HTML
            'is_current': (current_user.is_authenticated and u.id == current_user.id)
        })
    
    # Ordenar
    leaderboard_data.sort(key=lambda x: x['net_worth'], reverse=True)
    
    return render_template('leaderboard.html', ranking=leaderboard_data, active_page='leaderboard')

@app.route('/trader/<username>')
@login_required
def public_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Calcular stats
    net_worth = user.virtual_balance
    portfolio_list = []
    
    if user.portfolio:
        for item in user.portfolio:
            # Lógica de preço (simplificada)
            current_price = item.avg_price # Em produção usarias API
            val = item.amount * current_price
            net_worth += val
            portfolio_list.append({'symbol': item.symbol, 'amount': item.amount, 'value': val})
        
    pnl = ((net_worth - 10000) / 10000) * 100
    
    # --- NOVO: BUSCAR BADGES DO UTILIZADOR VISITADO ---
    badges = get_user_badges(user) 
    
    return render_template('public_profile.html', 
                           trader=user, 
                           net_worth=net_worth, 
                           pnl=pnl, 
                           portfolio=portfolio_list,
                           badges=badges) # <--- Envia badges para o HTML

def smart_format(value):
    if value is None: return "$0.00"
    if value < 1.0: return f"${value:.8f}"
    else: return f"${value:,.2f}"

def get_quick_ticker_data():
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

def get_market_sentiment():
    """Busca o Fear & Greed Index real da API alternative.me"""
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = response.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return {"value": value, "text": classification}
    except:
        # Fallback se a API falhar
        return {"value": 50, "text": "Neutral (Offline)"}

@cache.memoize(timeout=120) # Guarda o resultado por 2 minutos
def get_top_cryptos(limit=5):
    """
    Busca dados reais. 
    Removido UNI e outras instáveis para evitar lentidão.
    """
    # Lista limpa de moedas que o Yahoo Finance aceita bem
    top_tickers = [
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 
        'DOGE-USD', 'ADA-USD', 'AVAX-USD', 'TRX-USD', 'LINK-USD', 
        'DOT-USD', 'LTC-USD', 'BCH-USD', 'SHIB-USD', 'ADA-USD',
        'ATOM-USD', 'XLM-USD', 'ETC-USD', 'FIL-USD', 'ICP-USD'
    ]
    
    # Garante que não pedimos mais do que existem na lista
    limit = min(limit, len(top_tickers))
    selected = top_tickers[:limit]
    data = []
    
    try:
        # Tenta descarregar tudo de uma vez (Mais rápido)
        tickers = yf.Tickers(" ".join(selected))
        
        for symbol in selected:
            try:
                # Aceder aos dados
                ticker_obj = tickers.tickers.get(symbol)
                if not ticker_obj: continue

                # Tenta obter o preço de forma segura
                # fast_info é muito mais rápido que history()
                info = ticker_obj.fast_info
                
                price = info.last_price
                prev_close = info.previous_close
                
                if price is None or prev_close is None:
                    continue # Se não houver dados, salta

                # Cálculos
                change_pct = ((price - prev_close) / prev_close) * 100
                
                # Limpar nome (BTC-USD -> BTC)
                clean_symbol = symbol.replace("-USD", "")
                
                # Ícones
                supported_icons = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LTC', 'BCH', 'DOT', 'LINK']
                if clean_symbol in supported_icons:
                    icon_class = f"fa-brands fa-{clean_symbol.lower()}"
                else:
                    icon_class = "fa-solid fa-coins"

                data.append({
                    "symbol": clean_symbol,
                    "price": smart_format(price),
                    "change": f"{change_pct:+.2f}%",
                    "change_raw": change_pct, # <--- CRUCIAL PARA A COR FUNCIONAR
                    "icon": icon_class,
                    "color": "text-green" if change_pct >= 0 else "text-red" # Envia a classe direto
                })
                
            except Exception as inner_e:
                # Se uma moeda falhar, ignora e segue para a próxima (Não trava o site)
                print(f"Erro ao ler {symbol}: {inner_e}")
                continue
                
    except Exception as e:
        print(f"Erro geral YFinance: {e}")
        
    return data
# --- ROTAS PRINCIPAIS ---

@app.route('/')
@cache.memoize(timeout=60) # A pagina Home guardada por 1 minuto
def home():
    # 1. Buscar Sentimento Real
    sentiment = get_market_sentiment()
    
    # 2. Buscar Top 5 para a Home
    top_5_crypto = get_top_cryptos(limit=5)
    
    # 3. Ticker Tape (Dados rápidos)
    ticker_data = get_quick_ticker_data() # Mantém a tua função antiga ou usa a nova
    
    return render_template('home.html', 
                           active_page='home', 
                           sentiment=sentiment, 
                           top_crypto=top_5_crypto,
                           ticker_data=ticker_data)

@app.route('/crypto')
def crypto_page():
    # Agora a página crypto carrega as Top 20 reais
    top_20 = get_top_cryptos(limit=20)
    return render_template('crypto.html', active_page='crypto', market_data=top_20)

@app.route('/crypto/analyze')
@login_required
def crypto_analyze_page():
    return render_template('crypto_analyze.html', active_page='crypto')

@app.route('/crypto/recommend')
@login_required
def crypto_recommend_page():
    return render_template('crypto_recommend.html', active_page='crypto')

@app.route('/crypto/strategy')
@login_required
def crypto_strategy_page():
    return render_template('crypto_strategy.html', active_page='crypto')

@app.route('/crypto/decoder')
@login_required
def crypto_decoder_page():
    return render_template('crypto_decoder.html', active_page='crypto')

@app.route('/etf')
def etf_page(): return render_template('etf.html', active_page='etf')

# Rotas que faltavam antes
@app.route('/screener')
@login_required 
def screener_page(): return render_template('screener.html', active_page='screener')

@app.route('/ai')
@login_required
def ai_page(): return render_template('ai.html', active_page='ai')

@app.route('/risk')
@login_required
def risk_page(): return render_template('risk.html', active_page='risk')

# --- ROTAS LEGAIS (Novas) ---
@app.route('/legal/terms')
def terms_page(): return render_template('legal_terms.html')

@app.route('/legal/privacy')
def privacy_page(): return render_template('legal_privacy.html')

# --- AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login efetuado com sucesso!', 'success')
            return redirect(url_for('home')) # Ou para onde quiseres ir
        else:
            flash('Email ou password incorretos.', 'error')

    # AQUI ESTÁ A CORREÇÃO: Usa auth.html com modo login
    return render_template('auth.html', mode='login')


# --- ROTA DE PERFIL (CORRIGIDA) ---
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_page():
    my_badges = get_user_badges(current_user)
    
    return render_template('profile.html', active_page='profile', badges=my_badges)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    email = request.form.get('email')
    
    # Validação simples
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != current_user.id:
        flash('Nome de utilizador já está em uso.', 'error')
    else:
        current_user.username = username
        current_user.email = email
        try:
            db.session.commit()
            flash('Dados atualizados!', 'success')
        except:
            flash('Erro ao guardar.', 'error')
            
    return redirect(url_for('profile_page'))

@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    old_pass = request.form.get('old_password')
    new_pass = request.form.get('new_password')
    confirm_pass = request.form.get('confirm_password')
    
    if not check_password_hash(current_user.password, old_pass):
        flash('A password atual está incorreta.', 'error')
        return redirect(url_for('profile_page'))
    
    if new_pass != confirm_pass:
        flash('As novas passwords não coincidem.', 'error')
        return redirect(url_for('profile_page'))
        
    # Guardar nova password hash
    current_user.password = generate_password_hash(new_pass, method='pbkdf2:sha256')
    db.session.commit()
    flash('Password alterada com sucesso!', 'success')
    return redirect(url_for('profile_page'))

@app.route('/update_avatar', methods=['POST'])
@login_required
def update_avatar():
    avatar = request.form.get('avatar')
    if avatar:
        current_user.avatar = avatar
        db.session.commit()
        flash('Avatar atualizado!', 'success')
    return redirect(url_for('profile_page'))


@app.route('/history')
@login_required
def history_page():
    # Vai buscar todas as transações, ordenadas da mais recente para a mais antiga
    transactions = Transaction.query.filter_by(user_id=current_user.id)\
                    .order_by(Transaction.timestamp.desc())\
                    .all()
    
    return render_template('history.html', transactions=transactions, active_page='history')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# --- ROTAS DE AI E ANÁLISE ---
# --- SUBSTIUI ESTA FUNÇÃO NO TEU APP.PY ---

@app.route('/analyze_user_coin', methods=['POST'])
@login_required
def analyze_user_coin():
    try:
        data = request.json
        raw_ticker = data.get('ticker', '').strip().upper()
        investment = float(data.get('investment', 0) or 0)
        
        # 1. Obter Preço Real (YFinance)
        # Tenta adicionar -USD se não tiver (ex: BTC -> BTC-USD)
        yf_ticker = f"{raw_ticker}-USD" if not raw_ticker.endswith(("-USD", "USD")) else raw_ticker
        
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="1mo")
        
        # Se falhar, tenta o ticker original (ex: AAPL)
        if hist.empty:
            stock = yf.Ticker(raw_ticker)
            hist = stock.history(period="1mo")
            if hist.empty: 
                return jsonify({"error": f"Não consegui encontrar dados para '{raw_ticker}'."})

        current_price = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        perf_30d = ((current_price - start_price) / start_price) * 100

        # 2. Prompt "Educacional" (Para contornar bloqueios da AI)
        # Forçamos a AI a agir como um simulador
        prompt = f"""
        Atua como um mentor de trading para fins ESTRITAMENTE EDUCACIONAIS.
        Analisa o ativo: {raw_ticker}
        Preço Atual: ${current_price:.6f}
        Performance 30d: {perf_30d:.2f}%
        
        Gera um PLANO DE TRADE SIMULADO. Tens de fornecer valores numéricos teóricos, não devolvas zeros.
        
        Responde APENAS neste JSON exato (sem formatação extra):
        {{
            "verdict": "Compra Forte / Compra / Neutro / Venda / Venda Forte",
            "explanation": "Uma frase curta e técnica sobre a tendência.",
            "entry": {current_price:.6f}, 
            "stop_loss": {current_price * 0.95:.6f},
            "take_profit": {current_price * 1.10:.6f},
            "risk_level": "Baixo/Médio/Alto"
        }}
        (Nota: Ajusta os valores de entry/stop/target baseados na tua análise técnica, mas mantém o formato float).
        """
        
        # 3. Chamar AI
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Tenta usar o modelo mais rápido/recente
            contents=prompt
        )
        
        # 4. Limpeza de JSON (O Segredo para não dar erro)
        # Removemos ```json e ``` que a AI às vezes adiciona
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        ai_data = json.loads(clean_json)
        
        # 5. Cálculos Finais
        # Garante que os valores vêm como números (float) para não dar erro
        entry_price = float(ai_data.get('entry', current_price))
        stop_price = float(ai_data.get('stop_loss', current_price * 0.95))
        target_price = float(ai_data.get('take_profit', current_price * 1.05))
        
        shares = investment / current_price if current_price > 0 else 0
        pot_profit = (target_price - current_price) * shares
        pot_loss = (current_price - stop_price) * shares
        roi = ((target_price - current_price) / current_price) * 100 if current_price > 0 else 0
        
        return jsonify({
            "ticker": raw_ticker,
            "current_price": smart_format(current_price),
            "verdict": ai_data.get('verdict', 'Neutro'),
            "explanation": ai_data.get('explanation', 'Análise indisponível.'),
            "risk_level": ai_data.get('risk_level', 'Médio'),
            "plan": { 
                "entry": smart_format(entry_price), 
                "stop": smart_format(stop_price), 
                "target": smart_format(target_price) 
            },
            "math": { 
                "shares": f"{shares:,.4f}", 
                "potential_profit": f"${pot_profit:.2f}", 
                "potential_loss": f"${pot_loss:.2f}", 
                "roi": f"{roi:.1f}%" 
            }
        })

    except Exception as e:
        print(f"ERRO BACKEND: {e}")
        return jsonify({"error": f"Erro interno: {str(e)}"})

@app.route('/generate_portfolio', methods=['POST'])
@login_required
def generate_portfolio():
    try:
        data = request.json
        prompt = f"""
        Cria portfolio crypto de €{data.get('capital')}, perfil de Risco {data.get('risk')}.
        Retorna JSON: {{ "explanation": "texto", "allocation": [{{ "asset": "BTC", "pct": 50 }}] }}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json')
        )
        ai_data = json.loads(response.text)
        
        capital = float(data.get('capital'))
        allocation = []
        for i in ai_data.get('allocation', []):
            allocation.append({
                "asset": i['asset'],
                "pct": i['pct'],
                "value": f"€{capital * (i['pct']/100):,.2f}"
            })
            
        return jsonify({"explanation": ai_data.get('explanation'), "allocation": allocation})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/decode_market', methods=['POST'])
@login_required
def decode_market():
    try:
        prompt = f"Explica simples para iniciante (max 3 linhas): {request.json.get('question')}"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return jsonify({"answer": response.text})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/get_recommendations', methods=['GET'])
def get_recommendations():
    try:
        # LISTA EXPANDIDA (Top 50 + Populares)
        # Isto simula "toda a internet" relevante sem matar o servidor
        candidates = [
            # Giants
            'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
            # Layer 1 & 2
            'AVAX-USD', 'DOT-USD', 'MATIC-USD', 'LINK-USD', 'TRX-USD', 'ATOM-USD',
            'NEAR-USD', 'APT-USD', 'SUI-USD', 'ARB-USD', 'OP-USD', 'INJ-USD',
            # AI & Gaming
            'RNDR-USD', 'FET-USD', 'GRT-USD', 'IMX-USD', 'SAND-USD', 'MANA-USD',
            # Memes (Alta Volatilidade = Boas Recomendações)
            'DOGE-USD', 'SHIB-USD', 'PEPE-USD', 'WIF-USD', 'FLOKI-USD', 'BONK-USD'
        ]
        
        recommendations = []
        
        # Download em massa (Muito mais rápido que um a um)
        tickers = yf.Tickers(" ".join(candidates))
        
        for symbol in candidates:
            try:
                # Usar fast_info ou history curto
                ticker_obj = tickers.tickers.get(symbol)
                if not ticker_obj: continue
                
                # Precisamos de 7 dias para ver a tendência
                hist = ticker_obj.history(period="7d")
                if len(hist) < 5: continue
                
                curr = hist['Close'].iloc[-1]
                start_week = hist['Close'].iloc[0]
                change_pct = ((curr - start_week) / start_week) * 100
                
                clean_ticker = symbol.replace("-USD", "")
                
                # --- A LÓGICA DE FILTRO (O "Scanner") ---
                # Só mostra se tiver movimento interessante (>3% ou <-2%)
                # Assim não enchemos a lista de moedas paradas
                
                tag = ""
                roi = ""
                stop = 0.0
                target = 0.0
                include = False

                if change_pct > 15:
                    tag = "🔥 Super Momentum"
                    roi = "Alto Risco / Alto Retorno"
                    stop = curr * 0.88
                    target = curr * 1.25
                    include = True
                elif change_pct > 5:
                    tag = "🚀 Tendência Alta"
                    roi = "Médio"
                    stop = curr * 0.94
                    target = curr * 1.12
                    include = True
                elif change_pct < -10:
                    tag = "💎 Oversold (Dip)"
                    roi = "Oportunidade Compra"
                    stop = curr * 0.85
                    target = curr * 1.30
                    include = True
                elif change_pct < -4:
                    tag = "📉 Correção Curta"
                    roi = "Médio"
                    stop = curr * 0.92
                    target = curr * 1.10
                    include = True

                if include:
                    recommendations.append({
                        "ticker": clean_ticker,
                        "price": smart_format(curr),
                        "change_5d": f"{change_pct:+.1f}%",
                        "change_raw": change_pct,
                        "target": smart_format(target),
                        "stop": smart_format(stop),
                        "roi": roi,
                        "tag": tag
                    })
                
            except: continue

        # Ordenar por "Excitação" (Maior movimento absoluto primeiro)
        recommendations.sort(key=lambda x: abs(x['change_raw']), reverse=True)
        
        # Retorna Top 9 para encher a grelha
        return jsonify(recommendations[:9])

    except Exception as e:
        print(f"Erro Recs: {e}")
        return jsonify([])

# --- PAPER TRADING (SIMULADOR) ---

@app.route('/paper_trading')
@login_required
def paper_trading():
    portfolio_items = Portfolio.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.timestamp.desc()).limit(10).all()
    
    total_portfolio_value = 0
    enriched_portfolio = []
    
    # Dados para o Gráfico de Pizza (Chart.js)
    allocation_labels = []
    allocation_data = []

    for item in portfolio_items:
        try:
            # Tenta preço live (com cache de 1 minuto seria ideal, mas aqui direto)
            ticker = yf.Ticker(f"{item.symbol}-USD")
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                ticker = yf.Ticker(item.symbol) # Tenta sem -USD
                hist = ticker.history(period="1d")
                current_price = hist['Close'].iloc[-1] if not hist.empty else item.avg_price
        except:
            current_price = item.avg_price # Fallback
        
        value = item.amount * current_price
        total_portfolio_value += value
        
        profit_pct = 0
        profit_abs = 0
        if item.avg_price > 0:
            profit_pct = ((current_price - item.avg_price) / item.avg_price) * 100
            profit_abs = value - (item.amount * item.avg_price)
        
        enriched_portfolio.append({
            "symbol": item.symbol,
            "amount": item.amount,
            "avg_price": item.avg_price,
            "current_price": current_price,
            "total_value": value,
            "profit_pct": profit_pct,
            "profit_abs": profit_abs
        })

        # Adicionar dados para o gráfico
        if value > 1: # Só mostra no gráfico se valer mais de $1
            allocation_labels.append(item.symbol)
            allocation_data.append(round(value, 2))

    net_worth = current_user.virtual_balance + total_portfolio_value
    
    # Adicionar o saldo livre ao gráfico também
    if current_user.virtual_balance > 1:
        allocation_labels.append("Cash (USD)")
        allocation_data.append(round(current_user.virtual_balance, 2))

    return render_template('paper_trading.html', 
                           portfolio=enriched_portfolio, 
                           transactions=transactions,
                           net_worth=net_worth,
                           alloc_labels=json.dumps(allocation_labels),
                           alloc_data=json.dumps(allocation_data),
                           active_page='paper_trading')

@app.route('/paper_trading/trade', methods=['POST'])
@login_required
def execute_trade():
    symbol = request.form.get('symbol', '').upper().strip()
    action = request.form.get('action') # BUY ou SELL
    trade_mode = request.form.get('trade_mode') # 'units' (Qtd Moedas) ou 'fiat' (Valor em $)
    
    try:
        input_value = float(request.form.get('amount')) # O valor que o user escreveu
    except:
        flash('Valor inválido.', 'error')
        return redirect(url_for('paper_trading'))

    if input_value <= 0:
        flash('O valor deve ser maior que zero.', 'error')
        return redirect(url_for('paper_trading'))

    # 1. Obter Preço Real
    try:
        ticker_name = f"{symbol}-USD" if not symbol.endswith("-USD") else symbol
        ticker = yf.Ticker(ticker_name)
        hist = ticker.history(period="1d")
        
        if hist.empty:
            ticker = yf.Ticker(symbol) # Tenta sem -USD
            hist = ticker.history(period="1d")
            if hist.empty:
                flash(f'Moeda "{symbol}" não encontrada.', 'error')
                return redirect(url_for('paper_trading'))
                
        price = hist['Close'].iloc[-1]
    except:
        flash('Erro de conexão ao obter preço. Tenta novamente.', 'error')
        return redirect(url_for('paper_trading'))

    # 2. Calcular Quantidade e Custo baseado no Modo
    amount = 0.0
    cost = 0.0

    if trade_mode == 'fiat':
        # User quer gastar X dólares (ex: $500 de BTC)
        cost = input_value
        amount = cost / price # Calcula quantas moedas dá
    else:
        # User quer comprar X moedas (ex: 0.5 BTC)
        amount = input_value
        cost = amount * price

    # 3. Lógica de Compra / Venda
    if action == 'BUY':
        if current_user.virtual_balance >= cost:
            # Tirar dinheiro
            current_user.virtual_balance -= cost
            
            # Adicionar ao Portfolio
            position = Portfolio.query.filter_by(user_id=current_user.id, symbol=symbol).first()
            if position:
                # Preço Médio Ponderado
                total_cost_old = position.amount * position.avg_price
                new_total_amount = position.amount + amount
                position.avg_price = (total_cost_old + cost) / new_total_amount
                position.amount = new_total_amount
            else:
                new_pos = Portfolio(user_id=current_user.id, symbol=symbol, amount=amount, avg_price=price)
                db.session.add(new_pos)
            
            flash(f'Compraste {amount:.6f} {symbol} (Total: ${cost:.2f})', 'success')
        else:
            flash(f'Saldo insuficiente! Precisas de ${cost:.2f}', 'error')
            return redirect(url_for('paper_trading'))

    elif action == 'SELL':
        position = Portfolio.query.filter_by(user_id=current_user.id, symbol=symbol).first()
        
        # Verificar se tem moedas suficientes
        if position and position.amount >= (amount * 0.99999): # Margem de erro pequena para floats
            # Adicionar dinheiro
            current_user.virtual_balance += cost
            
            # Remover do Portfolio
            position.amount -= amount
            if position.amount <= 0.000001: # Limpeza de "pó"
                db.session.delete(position)
            
            flash(f'Vendeste {amount:.6f} {symbol} (Recebeste: ${cost:.2f})', 'success')
        else:
            flash(f'Não tens {amount:.6f} {symbol} para vender.', 'error')
            return redirect(url_for('paper_trading'))

    # 4. Registar Transação
    tx = Transaction(user_id=current_user.id, symbol=symbol, type=action, price=price, amount=amount, total_value=cost)
    db.session.add(tx)
    db.session.commit()
    
    return redirect(url_for('paper_trading'))

@app.route('/paper_trading/reset')
@login_required
def reset_account():
    current_user.virtual_balance = 10000.0
    Portfolio.query.filter_by(user_id=current_user.id).delete()
    Transaction.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Conta reiniciada! Tens $10,000 virtuais novamente.', 'success')
    return redirect(url_for('paper_trading'))

# --- ADICIONA ESTA ROTA NO TEU APP.PY ---

@app.route('/crypto/details/<ticker>')
@login_required
def crypto_details(ticker):
    ticker = ticker.upper()
    yf_ticker = f"{ticker}-USD"
    
    # 1. Buscar Dados Reais
    try:
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="7d")
        
        if hist.empty:
            flash(f"Dados não encontrados para {ticker}", "error")
            return redirect(url_for('crypto_recommend_page'))
            
        current_price = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        change_pct = ((current_price - start_price) / start_price) * 100
        
        # 2. Gerar Plano Automático (Simulação de AI)
        # Se quiseres usar o Gemini aqui, podes chamar a função da AI, 
        # mas para ser rápido vamos usar a lógica matemática que já tinhas.
        
        comment = ""
        stop_loss = 0.0
        target = 0.0
        roi_label = ""
        
        if change_pct > 10:
            comment = f"O {ticker} está com um momentum explosivo. A tendência é forte, mas cuidado com correções de curto prazo."
            roi_label = "Alto Risco / Alto Retorno"
            stop_loss = current_price * 0.90
            target = current_price * 1.20
        elif change_pct > 0:
            comment = f"Tendência de alta saudável para {ticker}. Bons indicadores de volume a suportar a subida."
            roi_label = "Médio"
            stop_loss = current_price * 0.95
            target = current_price * 1.10
        elif change_pct < -10:
            comment = f"O {ticker} está em zona de sobrevenda (Oversold). O RSI indica uma possível reversão em breve."
            roi_label = "Oportunidade de Desconto"
            stop_loss = current_price * 0.85
            target = current_price * 1.30
        else:
            comment = f"O {ticker} está numa fase de acumulação lateral. Aguardar quebra de resistência."
            roi_label = "Baixo (Neutro)"
            stop_loss = current_price * 0.97
            target = current_price * 1.05

        return render_template('crypto_details.html',
                               ticker=ticker,
                               price=smart_format(current_price),
                               change_pct=f"{change_pct:+.2f}%",
                               change_raw=change_pct,
                               ai_comment=comment,
                               roi=roi_label,
                               plan={
                                   "entry": smart_format(current_price),
                                   "stop": smart_format(stop_loss),
                                   "target": smart_format(target)
                               },
                               active_page='crypto')

    except Exception as e:
        print(f"Erro Details: {e}")
        flash("Erro ao carregar detalhes.", "error")
        return redirect(url_for('crypto_recommend_page'))

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 1. Verificar se já existe
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Este email já está registado.', 'error')
        else:
            # 2. Criar novo utilizador
            new_user = User(
                username=name,
                email=email, 
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            
            try:
                db.session.add(new_user)
                db.session.commit()
                
                # 3. MENSAGEM DE SUCESSO
                flash('Conta criada com sucesso! Por favor faz login.', 'success')
                
                # 4. O SEGREDO ESTÁ AQUI: Redireciona para o LOGIN, não para a Home
                # E garantimos que NÃO chamamos login_user(new_user)
                return redirect(url_for('login_page'))
                
            except Exception as e:
                flash(f'Erro ao criar conta: {e}', 'error')
                    
    # Se for GET, mostra o formulário de registo
    return render_template('auth.html', mode='signup')

@app.route('/crypto/snapshot')
@login_required
def crypto_snapshot_page():
    ticker = request.args.get('ticker')
    if not ticker:
        return redirect(url_for('crypto_page'))
    
    ticker = ticker.upper().replace(" ", "")
    yf_ticker = f"{ticker}-USD"
    
    try:
        # Busca dados rápidos (1 mês para ter contexto)
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(period="1mo")
        
        if hist.empty:
            flash(f"Moeda {ticker} não encontrada.", "error")
            return redirect(url_for('crypto_page'))
            
        # Dados Atuais
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        # Dados de Volume
        volume = hist['Volume'].iloc[-1]
        avg_volume = hist['Volume'].mean()
        
        # --- Lógica de Estimativa Simples (Tendência) ---
        # Se estiver acima da média de 30 dias e com volume alto = SUBIR
        ma_30 = hist['Close'].mean()
        signal = "Neutro"
        signal_color = "yellow"
        signal_icon = "fa-minus"
        desc = "Mercado indeciso."

        if current_price > ma_30 and change_pct > 0:
            signal = "Tendência de Alta"
            signal_color = "green"
            signal_icon = "fa-arrow-trend-up"
            desc = "Preço acima da média mensal com momentum positivo."
        elif current_price < ma_30 and change_pct < 0:
            signal = "Tendência de Baixa"
            signal_color = "red"
            signal_icon = "fa-arrow-trend-down"
            desc = "Preço abaixo da média mensal. Cuidado."
        elif change_pct > 5:
             signal = "Possível Pump"
             signal_color = "green"
             signal_icon = "fa-rocket"
             desc = "Movimento explosivo detetado no curto prazo."

        return render_template('crypto_snapshot.html',
                               ticker=ticker,
                               price=smart_format(current_price),
                               change=f"{change_pct:+.2f}%",
                               change_raw=change_pct,
                               volume=smart_format(volume),
                               signal=signal,
                               signal_color=signal_color,
                               signal_icon=signal_icon,
                               signal_desc=desc,
                               active_page ='crypto')

    except Exception as e:
        print(f"Erro Snapshot: {e}")
        flash(f"Erro ao carregar {ticker}.", "error")
        return redirect(url_for('crypto_page'))

if __name__ == '__main__':
    # Porta 5000 forçada para evitar erros
    app.run(debug=True, port=5000)