from flask import Flask, render_template, jsonify, request
from google import genai
import yfinance as yf

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
# ⚠️ COLOCA A TUA API KEY AQUI
API_KEY = "AIzaSyBmMHvghgV13qHOzv-OcyCT887MZacnnzo" 

if API_KEY:
    client = genai.Client(api_key=API_KEY)

# --- FUNÇÃO AUXILIAR: BUSCAR DADOS RÁPIDOS PARA O TICKER (SSR) ---
def get_quick_ticker_data():
    """
    Busca apenas alguns ativos principais para preencher o Ticker Tape
    antes da página carregar.
    """
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL']
    data = []
    try:
        for t in tickers:
            stock = yf.Ticker(t)
            # '1d' é o mais rápido
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((curr - prev) / prev) * 100
                
                # Preparar dados formatados para o HTML
                data.append({
                    "symbol": t.replace("-USD", ""),
                    "price": f"{curr:,.2f}", 
                    "change": f"{abs(change):.2f}", # Removemos o sinal negativo aqui para tratar no HTML
                    "color": "green" if change >= 0 else "red",
                    "sign": "+" if change >= 0 else "-"
                })
    except Exception as e:
        print(f"Erro no Ticker: {e}")
    return data

# --- ROTAS DE PÁGINAS ---

@app.route('/')
def home():
    # Executa a função ANTES de enviar a página para o utilizador
    # Isto elimina o "loading" do ticker
    ticker_data = get_quick_ticker_data()
    return render_template('home.html', active_page='home', ticker_data=ticker_data)

@app.route('/crypto')
def crypto_page():
    return render_template('crypto.html', active_page='crypto')

@app.route('/etf')
def etf_page():
    return render_template('etf.html', active_page='etf')

# --- ROTAS DE FERRAMENTAS & AUTH ---
@app.route('/login')
def login_page():
    return render_template('auth.html', mode='login')

@app.route('/signup')
def signup_page():
    return render_template('auth.html', mode='signup')

@app.route('/screener')
def screener_page():
    return render_template('screener.html', active_page='screener')

@app.route('/ai')
def ai_page():
    return render_template('ai.html', active_page='ai')

@app.route('/risk')
def risk_page():
    return render_template('risk.html', active_page='risk')

# --- APIS DE DADOS (JSON) ---

@app.route('/get_market_data')
def get_market_data():
    """API completa para preencher as tabelas (Crypto & ETF)"""
    cryptos = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'BNB-USD', 'ADA-USD', 'DOGE-USD', 'AVAX-USD']
    etfs = ['SPY', 'QQQ', 'VOO', 'IWM', 'GLD', 'EEM', 'NVDA', 'TSLA', 'AMD', 'MSFT']
    
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
                        "price": f"{curr:,.2f}",
                        "change": round(change, 2)
                    })
        except: pass
        return data

    return jsonify({
        "crypto": fetch(cryptos),
        "etf": fetch(etfs)
    })

@app.route('/analyze_trade', methods=['POST'])
def analyze_trade():
    """Lógica da AI para o Architect"""
    try:
        req_data = request.json
        ticker = req_data.get('ticker')
        
        # 1. Dados Reais
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if hist.empty: return jsonify({"error": "Ticker não encontrado"})

        current = hist['Close'].iloc[-1]
        perf = ((current - hist['Close'].iloc[0])/hist['Close'].iloc[0])*100
        
        # 2. AI Prompt
        prompt = f"""
        Age como um Mentor de Trading Profissional.
        Ativo: {ticker}. Preço: ${current:.2f}. Perf 30d: {perf:.1f}%.
        Responde neste formato EXATO (sem markdown):
        SENTIMENTO: [Alta/Baixa/Neutro]
        ENTRADA: [Valor]
        STOP LOSS: [Valor]
        TAKE PROFIT: [Valor]
        RAZÃO: [Frase curta]
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        
        # Parser simples
        lines = response.text.split('\n')
        result = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
                
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)