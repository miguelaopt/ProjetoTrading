# app.py
import os
import json
import feedparser
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
import yfinance as yf
import requests
import time

# --- IMPORTAÇÕES LOCAIS (A nova organização) ---
from extensions import db, login_manager, mail, cache
from models import User, Watchlist, Portfolio, Transaction
from utils import (
    get_stock_price, get_user_badges, get_market_sentiment, 
    get_market_movers, get_top_cryptos, get_quick_ticker_data, 
    smart_format, client # Cliente AI importado do utils
)

# Configuração Inicial
load_dotenv(encoding="utf-8")
app = Flask(__name__)

# Configurações do Servidor
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "chave-secreta-padrao-123")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Base de Dados
database_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- INICIALIZAR EXTENSÕES ---
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login_page'
mail.init_app(app)
cache.init_app(app)

token_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROTAS PRINCIPAIS ---

@app.route('/')
@cache.memoize(timeout=60)
def home():
    sentiment = get_market_sentiment()
    top_5_crypto = get_top_cryptos(limit=5)
    ticker_data = get_quick_ticker_data()
    return render_template('home.html', active_page='home', sentiment=sentiment, top_crypto=top_5_crypto, ticker_data=ticker_data)

@app.route('/crypto')
@login_required
@cache.cached(timeout=60)
def crypto_page():
    gainers, losers = get_market_movers()
    return render_template('crypto.html', market_data=get_top_cryptos(limit=20), gainers=gainers, losers=losers, active_page='crypto')

@app.context_processor
def inject_user_plan():
    if current_user.is_authenticated:
        # Formatação bonita: "Pro" -> "PRO Plan"
        plan_display = f"{current_user.plan_type} Plan"
        
        # Cor do badge baseada no plano
        plan_color = "gray"
        if current_user.plan_type == 'Pro': plan_color = "#3498db" # Azul
        if current_user.plan_type == 'Ultra': plan_color = "#f1c40f" # Dourado
            
        return dict(user_plan_display=plan_display, user_plan_color=plan_color)
    return dict(user_plan_display="", user_plan_color="")

# --- ROTAS DE PLANOS E PAGAMENTOS ---

@app.route('/pricing')
@login_required
def pricing_page():
    return render_template('pricing.html', active_page='pricing')

@app.route('/checkout/<plan_name>')
@login_required
def checkout_page(plan_name):
    # Definir preços para simulação
    prices = {
        'Starter': 'Grátis',
        'Pro': '€5.00',
        'Ultra': '€10.00'
    }
    
    # Se for Starter, não precisa de pagar, ativa direto
    if plan_name == 'Starter':
        current_user.plan_type = 'Starter'
        current_user.special_role = None
        db.session.commit()
        flash("Plano Starter ativado.", "success")
        return redirect(url_for('profile_page'))

    if plan_name not in prices:
        return redirect(url_for('pricing_page'))

    return render_template('checkout.html', plan_name=plan_name, price=prices[plan_name])

@app.route('/process_payment', methods=['POST'])
@login_required
def process_payment():
    plan_name = request.form.get('plan')
    
    # SIMULAÇÃO DE PROCESSAMENTO BANCÁRIO
    # O servidor "dorme" 2 segundos para fingir que está a contactar o banco
    time.sleep(2.5) 
    
    # Aqui validarias o cartão de crédito com Stripe/PayPal na vida real
    
    # Atribuir Plano
    current_user.plan_type = plan_name
    
    if plan_name == 'Ultra':
        current_user.special_role = 'VIP'
    elif plan_name == 'Pro':
        current_user.special_role = None 

    db.session.commit()
    
    # Redirecionar para página de sucesso
    return render_template('payment_success.html', plan=plan_name)

@app.route('/subscribe/<plan_name>')
@login_required
def subscribe_plan(plan_name):
    # Validar plano
    valid_plans = ['Starter', 'Pro', 'Ultra']
    if plan_name not in valid_plans:
        flash("Plano inválido.", "error")
        return redirect(url_for('pricing_page'))
    
    # Aqui entraria a integração com Stripe/PayPal.
    # Por enquanto, atualizamos diretamente na base de dados.
    
    current_user.plan_type = plan_name
    
    # Exemplo: Dar badge VIP se for Ultra
    if plan_name == 'Ultra':
        current_user.special_role = 'VIP'
    elif plan_name == 'Pro':
        current_user.special_role = None # Remove VIP antigo se descer de nivel
    
    db.session.commit()
    
    flash(f"Parabéns! Agora és membro {plan_name}.", "success")
    return redirect(url_for('profile_page'))

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
            return redirect(url_for('home'))
        else:
            flash('Email ou password incorretos.', 'error')
    return render_template('auth.html', mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Este email já está registado.', 'error')
        else:
            new_user = User(username=name, email=email, password=generate_password_hash(password, method='pbkdf2:sha256'))
            try:
                db.session.add(new_user)
                db.session.commit()
                flash('Conta criada! Por favor faz login.', 'success')
                return redirect(url_for('login_page'))
            except Exception as e:
                flash(f'Erro: {e}', 'error')
    return render_template('auth.html', mode='signup')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = token_serializer.dumps(user.email, salt='recover-key')
            link = url_for('reset_password', token=token, _external=True)
            msg = Message('Recuperar Password', recipients=[email])
            msg.body = f'Clica para mudar a password: {link}'
            try: mail.send(msg)
            except: pass
            flash('Email de recuperação enviado!', 'success')
        else: flash('Email não encontrado.', 'error')
        return redirect(url_for('login_page'))
    return render_template('auth.html', mode='forgot')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try: email = token_serializer.loads(token, salt='recover-key', max_age=1800)
    except:
        flash('Link inválido.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        user = User.query.filter_by(email=email).first_or_404()
        user.password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        db.session.commit()
        flash('Password alterada!', 'success')
        return redirect(url_for('login_page'))
    return render_template('reset_password.html', token=token)

# --- PAPER TRADING (SIMULADOR) ---

@app.route('/paper_trading')
@login_required
def paper_trading():
    portfolio_items = Portfolio.query.filter_by(user_id=current_user.id).all()
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.timestamp.desc()).limit(10).all()
    
    total_portfolio_value = 0
    enriched_portfolio = []
    allocation_labels = []
    allocation_data = []

    # Batch Download para performance
    tickers_to_fetch = [f"{item.symbol}-USD" if not item.symbol.endswith("-USD") else item.symbol for item in portfolio_items]
    symbols_map = {item.symbol: (f"{item.symbol}-USD" if not item.symbol.endswith("-USD") else item.symbol) for item in portfolio_items}
    
    live_prices = {}
    if tickers_to_fetch:
        try:
            data = yf.download(tickers_to_fetch, period="1d", interval="1d", progress=False, threads=True, group_by='ticker')
            for symbol in tickers_to_fetch:
                try:
                    price = data['Close'].iloc[-1] if len(tickers_to_fetch) == 1 else data[symbol]['Close'].iloc[-1]
                    if float(price) > 0: live_prices[symbol] = float(price)
                except: pass
        except: pass

    for item in portfolio_items:
        yf_symbol = symbols_map.get(item.symbol)
        current_price = live_prices.get(yf_symbol, item.avg_price)
        value = item.amount * current_price
        total_portfolio_value += value
        
        profit_pct = 0
        profit_abs = 0
        if item.avg_price > 0:
            profit_pct = ((current_price - item.avg_price) / item.avg_price) * 100
            profit_abs = value - (item.amount * item.avg_price)
        
        enriched_portfolio.append({
            "symbol": item.symbol, "amount": item.amount, "avg_price": item.avg_price,
            "current_price": current_price, "total_value": value, "profit_pct": profit_pct, "profit_abs": profit_abs
        })
        if value > 1:
            allocation_labels.append(item.symbol)
            allocation_data.append(round(value, 2))

    net_worth = current_user.virtual_balance + total_portfolio_value
    if current_user.virtual_balance > 1:
        allocation_labels.append("Cash")
        allocation_data.append(round(current_user.virtual_balance, 2))

    return render_template('paper_trading.html', portfolio=enriched_portfolio, transactions=transactions,
                           net_worth=net_worth, alloc_labels=json.dumps(allocation_labels),
                           alloc_data=json.dumps(allocation_data), active_page='paper_trading')

@app.route('/paper_trading/trade', methods=['POST'])
@login_required
def execute_trade():
    symbol = request.form.get('symbol', '').upper().strip()
    action = request.form.get('action')
    trade_mode = request.form.get('trade_mode')
    
    try: input_value = float(request.form.get('amount'))
    except: return redirect(url_for('paper_trading'))
    if input_value <= 0: return redirect(url_for('paper_trading'))

    price = get_stock_price(f"{symbol}-USD")
    if not price: 
        price = get_stock_price(symbol)
        if not price:
            flash('Moeda não encontrada.', 'error')
            return redirect(url_for('paper_trading'))

    amount = input_value / price if trade_mode == 'fiat' else input_value
    cost = amount * price

    if action == 'BUY':
        if current_user.virtual_balance >= cost:
            current_user.virtual_balance -= cost
            pos = Portfolio.query.filter_by(user_id=current_user.id, symbol=symbol).first()
            if pos:
                total_old = pos.amount * pos.avg_price
                new_amt = pos.amount + amount
                pos.avg_price = (total_old + cost) / new_amt
                pos.amount = new_amt
            else:
                db.session.add(Portfolio(user_id=current_user.id, symbol=symbol, amount=amount, avg_price=price))
            db.session.add(Transaction(user_id=current_user.id, symbol=symbol, type=action, price=price, amount=amount, total_value=cost))
            db.session.commit()
            flash(f'Comprado!', 'success')
        else:
            flash('Saldo insuficiente.', 'error')

    elif action == 'SELL':
        pos = Portfolio.query.filter_by(user_id=current_user.id, symbol=symbol).first()
        if pos and pos.amount >= (amount * 0.99999):
            current_user.virtual_balance += cost
            pos.amount -= amount
            if pos.amount <= 0.000001: db.session.delete(pos)
            db.session.add(Transaction(user_id=current_user.id, symbol=symbol, type=action, price=price, amount=amount, total_value=cost))
            db.session.commit()
            flash(f'Vendido!', 'success')
        else:
            flash('Moedas insuficientes.', 'error')
    return redirect(url_for('paper_trading'))

@app.route('/paper_trading/reset')
@login_required
def reset_account():
    current_user.virtual_balance = 10000.0
    Portfolio.query.filter_by(user_id=current_user.id).delete()
    Transaction.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Conta reiniciada!', 'success')
    return redirect(url_for('paper_trading'))

# --- COPY TRADING ---

@app.route('/copy_trade/preview/<target_username>')
@login_required
def copy_trade_preview(target_username):
    target_user = User.query.filter_by(username=target_username).first_or_404()
    if target_user.id == current_user.id: return redirect(url_for('profile_page'))
    if not target_user.portfolio: return redirect(url_for('public_profile', username=target_username))

    total_cost_to_copy = 0.0
    target_assets = []
    
    tickers_to_fetch = [f"{item.symbol}-USD" for item in target_user.portfolio]
    live_prices = {}
    if tickers_to_fetch:
        try:
            data = yf.download(tickers_to_fetch, period="1d", interval="1d", progress=False, threads=True, group_by='ticker')
            for item in target_user.portfolio:
                sym = f"{item.symbol}-USD"
                try:
                    price = data['Close'].iloc[-1] if len(tickers_to_fetch) == 1 else data[sym]['Close'].iloc[-1]
                    live_prices[sym] = float(price)
                except: live_prices[sym] = item.avg_price
        except: pass

    for item in target_user.portfolio:
        price = live_prices.get(f"{item.symbol}-USD", item.avg_price)
        cost = item.amount * price
        total_cost_to_copy += cost
        target_assets.append({'symbol': item.symbol, 'amount': item.amount, 'current_price': price, 'cost': cost})

    my_equity = current_user.virtual_balance + sum([i.amount * i.avg_price for i in current_user.portfolio])
    badges = get_user_badges(target_user)

    return render_template('copy_confirm.html', target=target_user, target_assets=target_assets,
                           total_cost=total_cost_to_copy, my_cash=current_user.virtual_balance,
                           my_equity=my_equity, badges=badges)

@app.route('/copy_trade/execute/<target_username>', methods=['POST'])
@login_required
def copy_trade_execute(target_username):
    target_user = User.query.filter_by(username=target_username).first_or_404()
    action_type = request.form.get('action_type')
    
    tickers_to_fetch = [f"{item.symbol}-USD" for item in target_user.portfolio]
    live_prices = {}
    if tickers_to_fetch:
        try:
            data = yf.download(tickers_to_fetch, period="1d", interval="1d", progress=False, threads=True, group_by='ticker')
            for item in target_user.portfolio:
                sym = f"{item.symbol}-USD"
                try:
                    price = data['Close'].iloc[-1] if len(tickers_to_fetch) == 1 else data[sym]['Close'].iloc[-1]
                    live_prices[sym] = float(price)
                except: live_prices[sym] = item.avg_price
        except: pass

    cost_needed = 0.0
    orders = []
    for item in target_user.portfolio:
        price = live_prices.get(f"{item.symbol}-USD", item.avg_price)
        cost = item.amount * price
        cost_needed += cost
        orders.append({'symbol': item.symbol, 'amount': item.amount, 'price': price, 'cost': cost})

    try:
        if action_type == 'sell_and_buy':
            liq_val = 0
            for item in current_user.portfolio:
                liq_val += (item.amount * item.avg_price)
                db.session.add(Transaction(user_id=current_user.id, symbol=item.symbol, type="SELL", price=item.avg_price, amount=item.amount, total_value=item.amount*item.avg_price))
                db.session.delete(item)
            current_user.virtual_balance += liq_val
            db.session.commit()

        if current_user.virtual_balance < cost_needed:
            flash("Saldo insuficiente.", "error")
            return redirect(url_for('copy_trade_preview', target_username=target_username))

        for order in orders:
            current_user.virtual_balance -= order['cost']
            existing = Portfolio.query.filter_by(user_id=current_user.id, symbol=order['symbol']).first()
            if existing:
                total_old = existing.amount * existing.avg_price
                new_amt = existing.amount + order['amount']
                existing.avg_price = (total_old + order['cost']) / new_amt
                existing.amount = new_amt
            else:
                db.session.add(Portfolio(user_id=current_user.id, symbol=order['symbol'], amount=order['amount'], avg_price=order['price']))
            
            db.session.add(Transaction(user_id=current_user.id, symbol=order['symbol'], type="BUY", price=order['price'], amount=order['amount'], total_value=order['cost']))

        db.session.commit()
        flash("Cópia realizada com sucesso!", "success")
        return redirect(url_for('paper_trading'))
    except:
        db.session.rollback()
        flash("Erro ao executar.", "error")
        return redirect(url_for('home'))

# --- HISTÓRICO, PERFIL E SOCIAL ---

@app.route('/history')
@login_required
def history_page():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.timestamp.desc()).all()
    return render_template('history.html', transactions=transactions, active_page='history')

@app.route('/leaderboard')
def leaderboard_page():
    users = User.query.all()
    
    # 1. Recolher todas as moedas usadas no site inteiro para baixar preço de uma vez
    all_tickers = set()
    for u in users:
        for item in u.portfolio:
            all_tickers.add(f"{item.symbol}-USD")
            
    # 2. Batch Download dos preços atuais (Rápido)
    live_prices = {}
    if all_tickers:
        try:
            data = yf.download(list(all_tickers), period="1d", interval="1d", progress=False, group_by='ticker')
            for sym in all_tickers:
                try:
                    # Se for só uma moeda a estrutura é diferente
                    if len(all_tickers) == 1:
                        price = data['Close'].iloc[-1]
                    else:
                        price = data[sym]['Close'].iloc[-1]
                    live_prices[sym] = float(price)
                except: pass
        except: pass

    # 3. Calcular Net Worth Real usando os preços live
    leaderboard_data = []
    for u in users:
        portfolio_value = 0.0
        for item in u.portfolio:
            # Usa o preço live. Se falhar, usa o avg_price como fallback
            price = live_prices.get(f"{item.symbol}-USD", item.avg_price)
            portfolio_value += (item.amount * price)
            
        nw = u.virtual_balance + portfolio_value
        
        leaderboard_data.append({
            'username': u.username,
            'avatar': u.avatar,
            'net_worth': nw,
            'pnl_pct': ((nw - 10000) / 10000) * 100,
            'badges': get_user_badges(u),
            'is_current': (current_user.is_authenticated and u.id == current_user.id)
        })
    
    leaderboard_data.sort(key=lambda x: x['net_worth'], reverse=True)
    return render_template('leaderboard.html', ranking=leaderboard_data, active_page='leaderboard')

@app.route('/trader/<username>')
@login_required
def public_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # 1. Preparar lista de Símbolos
    tickers = []
    symbols_map = {}
    for item in user.portfolio:
        yf_symbol = f"{item.symbol}-USD" if not item.symbol.endswith("-USD") else item.symbol
        tickers.append(yf_symbol)
        symbols_map[item.symbol] = yf_symbol

    # 2. Batch Download Robusto
    live_prices = {}
    if tickers:
        try:
            # group_by='ticker' é usado para tentar manter estrutura
            data = yf.download(tickers, period="1d", interval="1d", progress=False, group_by='ticker')
            
            for sym in tickers:
                val_price = None
                try:
                    # TENTATIVA 1: Aceder pelo Símbolo (Estrutura MultiIndex: Ticker -> Close)
                    # É o mais comum com group_by='ticker', mesmo para 1 moeda
                    val_price = data[sym]['Close'].iloc[-1]
                except:
                    try:
                        # TENTATIVA 2: Aceder direto (Estrutura Plana: Close)
                        # Acontece às vezes se o yfinance simplificar a resposta
                        val_price = data['Close'].iloc[-1]
                    except: 
                        pass # Falhou tudo
                
                # Se encontrámos um preço válido, guardamos
                if val_price is not None and float(val_price) > 0:
                    live_prices[sym] = float(val_price)
                    
        except Exception as e:
            print(f"Erro ao baixar preços no perfil: {e}")

    # 3. Calcular Património
    portfolio_value = 0.0
    portfolio_display = []
    
    for item in user.portfolio:
        yf_symbol = symbols_map.get(item.symbol)
        # Usa o preço live. Se falhar (não estava no dict), usa o avg_price
        current_price = live_prices.get(yf_symbol, item.avg_price)
        
        val = item.amount * current_price
        portfolio_value += val
        
        portfolio_display.append({
            'symbol': item.symbol, 
            'amount': item.amount, 
            'value': val,
            'price': current_price,
            'avg_price': item.avg_price 
        })
        
    net_worth = user.virtual_balance + portfolio_value
    pnl_pct = ((net_worth - 10000) / 10000) * 100
    
    return render_template('public_profile.html', 
                           trader=user, 
                           net_worth=net_worth, 
                           pnl=pnl_pct, 
                           portfolio=portfolio_display, 
                           badges=get_user_badges(user))

@app.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html', active_page='profile', badges=get_user_badges(current_user))

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    email = request.form.get('email')
    if User.query.filter_by(username=username).first() and username != current_user.username:
        flash('Username em uso.', 'error')
    else:
        current_user.username = username
        current_user.email = email
        db.session.commit()
        flash('Perfil atualizado!', 'success')
    return redirect(url_for('profile_page'))

@app.route('/update_avatar', methods=['POST'])
@login_required
def update_avatar():
    current_user.avatar = request.form.get('avatar')
    db.session.commit()
    return redirect(url_for('profile_page'))

@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    old = request.form.get('old_password')
    new = request.form.get('new_password')
    confirm = request.form.get('confirm_password')
    
    if not check_password_hash(current_user.password, old):
        flash('Password antiga errada.', 'error')
    elif new != confirm:
        flash('Passwords não coincidem.', 'error')
    else:
        current_user.password = generate_password_hash(new, method='pbkdf2:sha256')
        db.session.commit()
        flash('Password alterada!', 'success')
    return redirect(url_for('profile_page'))

@app.route('/toggle_watchlist/<ticker>')
@login_required
def toggle_watchlist(ticker):
    ticker = ticker.upper()
    exists = Watchlist.query.filter_by(user_id=current_user.id, symbol=ticker).first()
    if exists:
        db.session.delete(exists)
        msg, action = "removido", "removed"
    else:
        db.session.add(Watchlist(user_id=current_user.id, symbol=ticker))
        msg, action = "adicionado", "added"
    db.session.commit()
    return {"status": "success", "message": msg, "action": action}

@app.route('/api/news')
@cache.cached(timeout=300) 
def get_crypto_news():
    news = []
    # Lista de fontes (Se uma falhar, tenta a próxima)
    rss_feeds = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://decrypt.co/feed"
    ]
    
    # Cabeçalho para fingir que somos um browser (evita bloqueio 403)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for url in rss_feeds:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if feed.entries:
                    for entry in feed.entries[:6]: # Pegar as 6 últimas
                        news.append({
                            'title': entry.title,
                            'link': entry.link,
                            'published': entry.published if hasattr(entry, 'published') else 'Recente'
                        })
                    break # Se funcionou, paramos de procurar
        except Exception as e:
            print(f"Erro ao ler RSS {url}: {e}")
            continue

    return {"news": news}

# --- AI E SNAPSHOTS ---

@app.route('/analyze_user_coin', methods=['POST'])
@login_required
def analyze_user_coin():
    try:
        data = request.json
        ticker_in = data.get('ticker', '').strip().upper()
        investment = float(data.get('investment', 0) or 0)
        
        yf_ticker = f"{ticker_in}-USD"
        stock = yf.Ticker(yf_ticker)
        curr = stock.fast_info.last_price
        
        if not curr: return jsonify({"error": "Moeda não encontrada"})
        
        target = curr * 1.10
        stop = curr * 0.95
        
        # Cálculos para a interface
        shares = investment / curr if curr > 0 else 0
        pot_profit = (target - curr) * shares
        roi = 10.0 # ROI fixo estimado na estratégia (10%)
        
        return jsonify({
            "ticker": ticker_in,
            "current_price": smart_format(curr),
            "verdict": "Compra" if curr > stock.fast_info.previous_close else "Neutro",
            "explanation": "Análise técnica baseada em momentum e volume.",
            "risk_level": "Médio",
            "plan": {
                "entry": smart_format(curr), 
                "stop": smart_format(stop), 
                "target": smart_format(target)
            },
            "math": {
                "potential_profit": f"${pot_profit:,.2f}", # <--- Valor calculado
                "roi": f"{roi}%"                            # <--- ROI preenchido
            }
        })
    except: return jsonify({"error": "Erro na análise"})


@app.route('/crypto/snapshot')
@login_required
def crypto_snapshot_page():
    ticker = request.args.get('ticker', '').upper()
    try:
        stock = yf.Ticker(f"{ticker}-USD")
        
        # Usar fast_info é rápido, mas às vezes não tem volume histórico
        # Vamos buscar o histórico de 1 mês para garantir dados
        hist = stock.history(period="1mo")
        
        if hist.empty: return redirect(url_for('crypto_page'))

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = ((current_price - prev_close)/prev_close)*100
        
        # CORREÇÃO: Calcular Volume
        volume = hist['Volume'].iloc[-1]
        if volume == 0: volume = hist['Volume'].iloc[-2] # Fallback se o dia acabou de começar
        
        # Lógica simples de sinal
        ma_30 = hist['Close'].mean()
        signal = "Neutro"
        color = "yellow"
        if current_price > ma_30:
            signal = "Alta"
            color = "green"
        elif current_price < ma_30:
            signal = "Baixa"
            color = "red"

        return render_template('crypto_snapshot.html', 
                               ticker=ticker, 
                               price=smart_format(current_price), 
                               change=f"{change:+.2f}%", 
                               change_raw=change, 
                               volume=f"{volume:,.0f}", # <--- Enviamos o volume formatado
                               active_page='crypto',
                               signal=signal, 
                               signal_color=color, 
                               signal_icon="fa-chart-line", 
                               signal_desc="Baseado na média móvel de 30 dias.")
    except Exception as e: 
        print(f"Erro snapshot: {e}")
        return redirect(url_for('crypto_page'))

@app.route('/crypto/details/<ticker>')
@login_required
def crypto_details(ticker):
    return redirect(url_for('crypto_snapshot_page', ticker=ticker))

@app.route('/get_recommendations', methods=['GET'])
@cache.cached(timeout=300)
def get_recommendations():
    candidates = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD', 'AVAX-USD', 'DOT-USD', 'MATIC-USD', 'LINK-USD', 'DOGE-USD', 'SHIB-USD', 'PEPE-USD']
    recommendations = []
    try:
        data = yf.download(candidates, period="7d", interval="1d", progress=False, group_by='ticker')
        for symbol in candidates:
            try:
                hist = data if len(candidates)==1 else data[symbol]
                if len(hist) < 5: continue
                
                curr = hist['Close'].iloc[-1]
                start = hist['Close'].iloc[0]
                pct = ((curr - start) / start) * 100
                
                # Definições automáticas de Target/Stop
                tag = ""
                roi_label = "Médio"
                target = curr * 1.10 # Target padrão +10%
                stop = curr * 0.95   # Stop padrão -5%
                
                if pct > 15: 
                    tag, roi_label = "🔥 Super Momentum", "Alto Risco"
                    target, stop = curr * 1.25, curr * 0.90
                elif pct > 5: 
                    tag, roi_label = "🚀 Tendência Alta", "Médio"
                    target, stop = curr * 1.15, curr * 0.94
                elif pct < -10: 
                    tag, roi_label = "💎 Oversold (Dip)", "Oportunidade"
                    target, stop = curr * 1.30, curr * 0.85
                elif pct < -5:
                    tag = "📉 Correção"
                
                if abs(pct) > 3:
                     recommendations.append({
                         "ticker": symbol.replace("-USD",""), 
                         "price": smart_format(curr), 
                         "change_5d": f"{pct:+.1f}%", 
                         "change_raw": pct,
                         "tag": tag,
                         "roi": roi_label,
                         "target": smart_format(target), # <--- Agora enviamos o Target
                         "stop": smart_format(stop)      # <--- E o Stop
                     })
            except: continue
            
        recommendations.sort(key=lambda x: abs(x['change_raw']), reverse=True)
        return jsonify(recommendations[:9])
    except: return jsonify([])


# --- ROTAS ESTÁTICAS ---
@app.route('/crypto/analyze')
def crypto_analyze_page(): return render_template('crypto_analyze.html', active_page='crypto')
@app.route('/crypto/recommend')
def crypto_recommend_page(): return render_template('crypto_recommend.html', active_page='crypto')
@app.route('/crypto/strategy')
def crypto_strategy_page(): return render_template('crypto_strategy.html', active_page='crypto')
@app.route('/crypto/decoder')
def crypto_decoder_page(): return render_template('crypto_decoder.html', active_page='crypto')
@app.route('/etf')
def etf_page(): return render_template('etf.html', active_page='etf')
@app.route('/screener')
def screener_page(): return render_template('screener.html', active_page='screener')
@app.route('/ai')
def ai_page(): return render_template('ai.html', active_page='ai')
@app.route('/risk')
def risk_page(): return render_template('risk.html', active_page='risk')
@app.route('/legal/terms')
def terms_page(): return render_template('legal_terms.html')
@app.route('/legal/privacy')
def privacy_page(): return render_template('legal_privacy.html')

if __name__ == '__main__':
    print("--- A INICIAR SERVIDOR ---")
    with app.app_context():
        db.create_all()
    # Usa porta 5001 para evitar conflitos de porta presa
    app.run(debug=True, port=5001, host='0.0.0.0', threaded=True)