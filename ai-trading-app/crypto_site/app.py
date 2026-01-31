from flask import Flask, render_template, jsonify, request
from google import genai  # <--- THE NEW LIBRARY
import yfinance as yf

app = Flask(__name__)

# --- CONFIGURATION ---
# Replace with your actual key
API_KEY = "AIzaSyBmMHvghgV13qHOzv-OcyCT887MZacnnzo"

# Initialize the new Client
client = genai.Client(api_key=API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_crypto')
def get_crypto():
    """Scans the market using yfinance"""
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 'BNB-USD', 'DOGE-USD']
    data = []
    
    try:
        for ticker in tickers:
            stock = yf.Ticker(ticker)
            # Fast fetch
            hist = stock.history(period="2d")
            
            if len(hist) >= 2:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((current - prev) / prev) * 100
                
                data.append({
                    "symbol": ticker.replace("-USD", ""),
                    "price": round(current, 2),
                    "change": round(change, 2)
                })
        
        # Sort by price high to low
        data.sort(key=lambda x: x['price'], reverse=True)
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    """Uses the new google.genai SDK to get advice"""
    try:
        # 1. Get the current market context from the request
        market_context = request.json.get('context', 'No data provided')
        
        prompt = f"""
        You are a crypto expert. Here is the current market status:
        {market_context}
        
        Based on this, give me:
        1. The "Coin of the Moment".
        2. A 1-sentence explanation why.
        """

        # 2. Call Gemini (New Syntax)
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        
        return jsonify({"advice": response.text})
        
    except Exception as e:
        print(e)
        return jsonify({"advice": "⚠️ AI Error: Check your API Key or Model Name."})

if __name__ == '__main__':
    app.run(debug=True)