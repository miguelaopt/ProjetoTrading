// ==========================================
// 1. INTERFACE GLOBAL (Menus e Dropdowns)
// ==========================================


// ==========================================
// 1. INTERFACE GLOBAL (Menus e Dropdowns)
// ==========================================

// Adicionar na secção "INTERFACE GLOBAL"
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu-overlay');
    menu.classList.toggle('active');
    
    // Bloquear scroll do site quando o menu está aberto
    if (menu.classList.contains('active')) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = 'auto';
    }
}

// Fechar ao clicar na parte escura
document.getElementById('mobile-menu-overlay').addEventListener('click', function(e) {
    if (e.target === this) toggleMobileMenu();
});

// ... resto do teu código ...

function toggleUserMenu() {
    const menu = document.getElementById('user-menu');
    menu.classList.toggle('hidden');
}

// Fechar menu se clicar fora
window.onclick = function(event) {
    if (!event.target.matches('.user-icon') && !event.target.matches('.fa-user')) {
        const dropdowns = document.getElementsByClassName("dropdown-content");
        for (let i = 0; i < dropdowns.length; i++) {
            if (!dropdowns[i].classList.contains('hidden')) {
                dropdowns[i].classList.add('hidden');
            }
        }
    }
}

// ==========================================
// 2. LÓGICA DA HOME PAGE
// ==========================================

// Renderizar Listas Simples (Crypto/ETF) na Home
async function loadHomeDataTablesOnly() {
    if (!document.getElementById('home-crypto-list')) return;

    try {
        // Vai buscar a lista completa à API
        const response = await fetch('/get_market_data');
        const data = await response.json();

        // Renderiza apenas os Top 5 de cada
        renderSimpleList('home-crypto-list', data.crypto.slice(0, 5));
        renderSimpleList('home-etf-list', data.etf.slice(0, 5));

    } catch (error) {
        console.error("Erro ao carregar tabelas:", error);
    }
}

function renderSimpleList(elementId, data) {
    const list = document.getElementById(elementId);
    list.innerHTML = '';
    
    data.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div class="asset-info">
                <span class="asset-icon"><i class="fa-solid fa-coins"></i></span>
                <span><b>${item.symbol}</b></span>
            </div>
            <div class="price-box">
                <span class="price">$${item.price}</span>
                <span class="change ${item.change >= 0 ? 'green' : 'red'}">
                    ${item.change >= 0 ? '▲' : '▼'} ${item.change}%
                </span>
            </div>
        `;
        list.appendChild(li);
    });
}

// Renderizar Gráfico ApexCharts
function renderHomeChart() {
    if (!document.querySelector("#mainChart")) return;

    // Dados fictícios para demonstração visual
    // Numa versão futura, podemos ligar isto à API também
    var options = {
        series: [{
            name: 'BTC Momentum',
            data: [91000, 92500, 91800, 93200, 94500, 93800, 95400, 96100, 95200]
        }, {
            name: 'S&P 500 Trend',
            data: [49000, 49500, 49800, 50200, 50500, 50100, 50800, 51000, 51200] // Normalizado para escala visual
        }],
        chart: {
            height: 350,
            type: 'area',
            toolbar: { show: false },
            background: 'transparent'
        },
        colors: ['#bc13fe', '#00f3ff'], // Roxo e Azul Neon
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 2 },
        xaxis: {
            categories: ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
            labels: { style: { colors: '#a0a0a0' } },
            axisBorder: { show: false },
            axisTicks: { show: false }
        },
        yaxis: { 
            labels: { show: false }, // Esconder eixo Y para look mais limpo
        },
        grid: {
            borderColor: 'rgba(255,255,255,0.05)',
            strokeDashArray: 4,
        },
        theme: { mode: 'dark' },
        legend: { labels: { colors: '#fff' } },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.4,
                opacityTo: 0.05,
                stops: [0, 90, 100]
            }
        }
    };

    var chart = new ApexCharts(document.querySelector("#mainChart"), options);
    chart.render();
}

// ==========================================
// 3. LÓGICA DAS PÁGINAS DEDICADAS (Crypto/ETF)
// ==========================================

async function loadMarketData(type) {
    try {
        const response = await fetch('/get_market_data');
        const data = await response.json();
        
        if (type === 'crypto') {
            renderFullList('crypto-list', data.crypto, 'crypto-best', 'crypto-worst');
        } else if (type === 'etf') {
            renderFullList('etf-list', data.etf, 'etf-best', 'etf-worst');
        }
    } catch (error) {
        console.error("Erro:", error);
    }
}

function renderFullList(listId, data, bestId, worstId) {
    const list = document.getElementById(listId);
    if (!list) return;
    
    list.innerHTML = ''; 

    data.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
            <span><b>${item.symbol}</b></span>
            <div class="price-box">
                <span>$${item.price}</span>
                <span class="${item.change >= 0 ? 'green' : 'red'}">${item.change}%</span>
            </div>
        `;
        list.appendChild(li);
    });

    // Calcular Best/Worst
    const sorted = [...data].sort((a, b) => b.change - a.change);
    const best = sorted[0];
    const worst = sorted[sorted.length - 1];

    if(document.getElementById(bestId)) {
        document.getElementById(bestId).innerHTML = `${best.symbol} <br><span class="green">${best.change}%</span>`;
        document.getElementById(worstId).innerHTML = `${worst.symbol} <br><span class="red">${worst.change}%</span>`;
    }
}

// ==========================================
// 4. LÓGICA AI ARCHITECT (Trade Analyzer)
// ==========================================
async function askArchitect() {
    const ticker = document.getElementById('ticker-input').value;
    if (!ticker) return;

    document.getElementById('ai-loading').classList.remove('hidden');
    document.getElementById('ai-plan').classList.add('hidden');

    try {
        const response = await fetch('/analyze_trade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ticker: ticker })
        });
        const data = await response.json();

        // Populate Data
        document.getElementById('plan-ticker').innerText = ticker.toUpperCase();
        document.getElementById('plan-sentiment').innerText = data['SENTIMENTO'] || 'Neutro';
        document.getElementById('plan-entry').innerText = data['ENTRADA'] || '--';
        document.getElementById('plan-stop').innerText = data['STOP LOSS'] || '--';
        document.getElementById('plan-target').innerText = data['TAKE PROFIT'] || '--';
        document.getElementById('plan-reason').innerText = data['RAZÃO'] || 'Sem análise.';

        document.getElementById('ai-loading').classList.add('hidden');
        document.getElementById('ai-plan').classList.remove('hidden');
        
    } catch (error) {
        alert("Erro na análise.");
        document.getElementById('ai-loading').classList.add('hidden');
    }
}

// --- LÓGICA DO FAQ (ACCORDION) ---
const acc = document.getElementsByClassName("faq-question");

for (let i = 0; i < acc.length; i++) {
    acc[i].addEventListener("click", function() {
        // Alternar a classe ativa
        this.classList.toggle("active");
        
        // Rodar o ícone
        const icon = this.querySelector("i");
        if(this.classList.contains("active")) {
            icon.classList.remove("fa-plus");
            icon.classList.add("fa-minus");
        } else {
            icon.classList.remove("fa-minus");
            icon.classList.add("fa-plus");
        }

        // Abrir/Fechar painel
        const panel = this.nextElementSibling;
        if (panel.style.maxHeight) {
            panel.style.maxHeight = null;
        } else {
            panel.style.maxHeight = panel.scrollHeight + "px";
        } 
    });
}

// ==========================================
// 5. NOVA LÓGICA DA PÁGINA CRYPTO
// ==========================================

async function analyzeUserCoin() {
    const ticker = document.getElementById('user-ticker').value;
    const investment = document.getElementById('user-investment').value;
    
    if(!ticker || !investment) {
        alert("Preenche a moeda e o valor a investir!");
        return;
    }

    // UI Loading
    document.getElementById('analysis-loading').classList.remove('hidden');
    document.getElementById('analysis-result').classList.add('hidden');

    try {
        const response = await fetch('/analyze_user_coin', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ticker: ticker, investment: investment })
        });
        const data = await response.json();

        if(data.error) {
            alert(data.error);
            document.getElementById('analysis-loading').classList.add('hidden');
            return;
        }

        // Renderizar o Resultado com Estilo
        const resultDiv = document.getElementById('analysis-result');
        const colorClass = data.math.potential_profit.includes('-') ? 'red' : 'green';
        
        resultDiv.innerHTML = `
            <div class="glass" style="padding: 20px; border: 1px solid var(--neon-purple);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h2 class="neon-text">${data.ticker}</h2>
                    <span class="sentiment-badge">${data.verdict}</span>
                </div>
                
                <p style="font-size: 1.1rem; margin: 15px 0;">"${data.explanation}"</p>
                
                <div class="stats-row" style="margin: 20px 0; gap: 15px;">
                    <div class="stat-item" style="flex:1">
                        <small>Entrada Ideal</small>
                        <h3>${data.plan.entry}</h3>
                    </div>
                    <div class="stat-item" style="flex:1">
                        <small style="color:var(--danger)">Stop Loss</small>
                        <h3>${data.plan.stop}</h3>
                    </div>
                    <div class="stat-item" style="flex:1">
                        <small style="color:var(--success)">Take Profit</small>
                        <h3>${data.plan.target}</h3>
                    </div>
                </div>

                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-top: 20px;">
                    <h4>💰 Se investires €${investment}:</h4>
                    <ul style="list-style:none; padding:0; margin-top:10px;">
                        <li style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span>Lucro Potencial:</span>
                            <span class="green">${data.math.potential_profit} (ROI: ${data.math.roi})</span>
                        </li>
                        <li style="display:flex; justify-content:space-between;">
                            <span>Perda Máxima (Stop):</span>
                            <span class="red">${data.math.potential_loss}</span>
                        </li>
                    </ul>
                </div>
            </div>
        `;
        
        document.getElementById('analysis-loading').classList.add('hidden');
        resultDiv.classList.remove('hidden');
        resultDiv.classList.add('fade-in');

    } catch (e) {
        console.error(e);
        alert("Erro na ligação.");
        document.getElementById('analysis-loading').classList.add('hidden');
    }
}

async function fetchRecommendations() {
    const grid = document.getElementById('recs-grid');
    const loading = document.getElementById('recs-loading');
    
    loading.classList.remove('hidden');
    grid.innerHTML = '';

    try {
        const response = await fetch('/get_recommendations');
        const data = await response.json();

        loading.classList.add('hidden');

        if(data.length === 0) {
            grid.innerHTML = '<p class="text-center">O mercado está difícil... sem recomendações seguras agora.</p>';
            return;
        }

        data.forEach(coin => {
            const card = document.createElement('div');
            card.className = 'pricing-card glass-panel';
            card.innerHTML = `
                <div class="badge-popular" style="background: var(--neon-blue);">${coin.tag}</div>
                <h3>${coin.ticker}</h3>
                <div class="price" style="font-size: 2rem;">${coin.price}</div>
                <p style="color: var(--success); margin-bottom: 20px;">${coin.change_5d} (5d)</p>
                
                <ul class="features-list" style="text-align:left;">
                    <li>🎯 Alvo: <span class="green" style="float:right">${coin.target}</span></li>
                    <li>🛑 Stop: <span class="red" style="float:right">${coin.stop}</span></li>
                    <li>🚀 ROI Est.: <span class="green" style="float:right">${coin.roi}</span></li>
                </ul>
                <button class="btn-outline full-width">Ver Gráfico</button>
            `;
            grid.appendChild(card);
        });

    } catch (e) {
        loading.classList.add('hidden');
        grid.innerHTML = '<p>Erro ao buscar recomendações.</p>';
    }
}

// ==========================================
// LÓGICA DE TOP MOVERS & TOP 20 (CRYPTO PAGE)
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    if(document.getElementById('gainers-list')) {
        loadCryptoPageData();
    }
});

async function loadCryptoPageData() {
    try {
        const response = await fetch('/get_market_data');
        const data = await response.json();
        const cryptos = data.crypto;

        // 1. PREENCHER TOP MOVERS (Gainers/Losers)
        const sortedByChange = [...cryptos].sort((a, b) => b.change - a.change);
        const gainers = sortedByChange.slice(0, 3);
        const losers = sortedByChange.slice(sortedByChange.length - 3, sortedByChange.length).reverse();

        renderMoverList('gainers-list', gainers);
        renderMoverList('losers-list', losers);

        // 2. PREENCHER TABELA TOP 20
        // Assumimos que a lista já vem mais ou menos ordenada do backend ou ordenamos por preço
        // Para ser "Top 20" real precisariamos de MarketCap, mas vamos usar a lista do backend
        renderTop20Table(cryptos);

    } catch (error) {
        console.error("Erro ao carregar dados crypto:", error);
    }
}

// (Função renderMoverList mantém-se igual...)
function renderMoverList(elementId, data) {
    const list = document.getElementById(elementId);
    list.innerHTML = '';
    data.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div class="asset-info"><span><b>${item.symbol}</b></span></div>
            <div class="price-box">
                <span class="price">$${item.price}</span>
                <span class="change ${item.change >= 0 ? 'green' : 'red'}">${item.change >= 0 ? '+' : ''}${item.change}%</span>
            </div>`;
        list.appendChild(li);
    });
}

// NOVA FUNÇÃO: Renderizar Tabela
function renderTop20Table(data) {
    const tbody = document.getElementById('top-20-body');
    tbody.innerHTML = '';

    data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="rank-num">${index + 1}</td>
            <td style="font-weight:bold; color:var(--neon-blue);">${item.symbol}</td>
            <td class="text-right">$${item.price}</td>
            <td class="text-right ${item.change >= 0 ? 'green' : 'red'}">
                ${item.change >= 0 ? '▲' : '▼'} ${item.change}%
            </td>
        `;
        tbody.appendChild(row);
    });
}

// --- TOASTS SYSTEM ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span> <i class="fa-solid fa-check"></i>`;
    container.appendChild(toast);
    
    // Remover após 3 segundos
    setTimeout(() => { toast.remove(); }, 3000);
}

// Interceptar Flashed Messages do Flask e converter em Toasts (Opcional, se quiseres manter compatibilidade)
// Podes adicionar isto no base.html num script tag para ler as mensagens antigas

// --- NEWS FEED ---
function toggleNews() {
    const widget = document.getElementById('news-feed');
    widget.classList.toggle('active');
    
    if (widget.classList.contains('active')) {
        loadNews();
    }
}

async function loadNews() {
    const content = document.getElementById('news-content');
    // Mantém o skeleton se estiver vazio
    if(content.children.length > 3) return; // Já carregou

    try {
        const response = await fetch('/api/news');
        const data = await response.json();
        
        content.innerHTML = ''; // Limpar skeletons
        data.news.forEach(item => {
            content.innerHTML += `
                <div class="news-item">
                    <a href="${item.link}" target="_blank">${item.title}</a>
                    <div style="font-size:0.7rem; color:gray; margin-top:4px;">${new Date(item.published).toLocaleTimeString()}</div>
                </div>
            `;
        });
    } catch (e) {
        content.innerHTML = '<p class="text-red">Erro ao carregar notícias.</p>';
    }
}

// --- WATCHLIST TOGGLE ---
async function toggleWatchlist(ticker, btnElement) {
    try {
        const response = await fetch(`/toggle_watchlist/${ticker}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast(data.message, 'success');
            // Mudar ícone visualmente
            const icon = btnElement.querySelector('i');
            if (data.action === 'added') {
                icon.classList.remove('fa-regular');
                icon.classList.add('fa-solid');
                icon.style.color = '#f1c40f';
            } else {
                icon.classList.remove('fa-solid');
                icon.classList.add('fa-regular');
                icon.style.color = '';
            }
        }
    } catch (e) {
        showToast('Erro ao atualizar favoritos', 'error');
    }
}
