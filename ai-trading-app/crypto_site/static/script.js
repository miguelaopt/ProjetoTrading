// --- FUNÇÃO GLOBAL: Carregar Dados Home (Ticker + Tabelas) ---
async function loadHomeData() {
    try {
        // Chamada à API
        const response = await fetch('/get_market_data');
        const data = await response.json();

        // 1. PREENCHER TICKER TAPE
        const tickerTrack = document.getElementById('home-ticker');
        if (tickerTrack) {
            tickerTrack.innerHTML = ''; // Limpar
            
            // Combinar listas para o ticker
            const allAssets = [...data.crypto, ...data.etf];
            
            // Criar elementos do ticker (Duplicar para loop infinito visual)
            // Fazemos 2 voltas aos dados para preencher a largura do ecrã
            for(let i=0; i<2; i++) { 
                allAssets.forEach(asset => {
                    const item = document.createElement('div');
                    item.className = 'ticker-item';
                    const colorClass = asset.change >= 0 ? 'green' : 'red';
                    const signal = asset.change >= 0 ? '+' : '';
                    
                    item.innerHTML = `
                        <span class="ticker-symbol">${asset.symbol}</span>
                        <span class="ticker-price">$${asset.price}</span>
                        <span class="ticker-change ${colorClass}">${signal}${asset.change}%</span>
                    `;
                    tickerTrack.appendChild(item);
                });
            }
        }

        // 2. PREENCHER TABELAS DA HOME (Se existirem)
        if (document.getElementById('home-crypto-list')) {
            renderSimpleList('home-crypto-list', data.crypto.slice(0, 5)); // Só top 5
            renderSimpleList('home-etf-list', data.etf.slice(0, 5));       // Só top 5
        }

    } catch (error) {
        console.error("Erro ao carregar dados home:", error);
    }
}

// Função auxiliar para renderizar listas simples na Home
function renderSimpleList(elementId, data) {
    const list = document.getElementById(elementId);
    list.innerHTML = '';
    
    data.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div class="asset-info">
                <span class="asset-icon"><i class="fa-solid fa-coins"></i></span>
                <span>${item.symbol}</span>
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

// --- GRÁFICO APEXCHARTS ---
function renderHomeChart() {
    if (!document.querySelector("#mainChart")) return;

    var options = {
        series: [{
            name: 'BTC Trend',
            data: [91000, 92500, 91800, 93200, 94500, 93800, 95400, 96100, 95200]
        }, {
            name: 'SPY Trend',
            data: [490, 495, 498, 502, 505, 501, 508, 510, 512]
        }],
        chart: {
            height: 350,
            type: 'area',
            toolbar: { show: false },
            background: 'transparent'
        },
        colors: ['#bc13fe', '#00f3ff'], // Cores Neon do tema
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 2 },
        xaxis: {
            type: 'category',
            categories: ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
            labels: { style: { colors: '#a0a0a0' } }
        },
        yaxis: { labels: { style: { colors: '#a0a0a0' } } },
        grid: {
            borderColor: 'rgba(255,255,255,0.05)',
        },
        theme: { mode: 'dark' },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.3,
                opacityTo: 0.05,
                stops: [0, 90, 100]
            }
        }
    };

    var chart = new ApexCharts(document.querySelector("#mainChart"), options);
    chart.render();
}

// --- MANTER AS OUTRAS FUNÇÕES DO SCRIPT ANTERIOR ---
// (Copia aqui as funções toggleUserMenu, loadMarketData das páginas específicas, etc.)