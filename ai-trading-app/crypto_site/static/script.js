// ==========================================
// 1. INTERFACE GLOBAL (Menus e Dropdowns)
// ==========================================

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