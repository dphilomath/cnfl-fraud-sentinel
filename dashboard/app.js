/**
 * Fraud Sentinel — Dashboard JavaScript
 * WebSocket client, Chart.js visualizations, and live alert feed.
 */

// ════════════════════════════════════════════════════════
// State
// ════════════════════════════════════════════════════════
const state = {
    ws: null,
    connected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 50,
    reconnectDelay: 2000,

    // Stats
    totalTransactions: 0,
    totalAlerts: 0,
    fraudRate: 0,
    amountFlagged: 0,

    // Chart data
    volumeLabels: [],
    volumeData: [],
    alertVolumeData: [],
    maxChartPoints: 30,

    // Risk distribution
    riskCounts: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },

    // Recent data
    recentAlerts: [],
    recentTransactions: [],
    maxAlerts: 50,
    maxTransactions: 25,

    // Timing
    startTime: Date.now(),
};


// ════════════════════════════════════════════════════════
// DOM Elements
// ════════════════════════════════════════════════════════
const els = {
    connectionStatus: document.getElementById('connection-status'),
    statusText: document.querySelector('#connection-status .status-text'),
    modeBadge: document.getElementById('mode-badge'),

    statTotalTxns: document.getElementById('stat-total-txns'),
    statTotalAlerts: document.getElementById('stat-total-alerts'),
    statMlConfirmed: document.getElementById('stat-ml-confirmed'),
    statAiCount: document.getElementById('stat-ai-count'),
    statFraudPct: document.getElementById('stat-fraud-pct'),
    statAmountFlagged: document.getElementById('stat-amount-flagged'),

    alertList: document.getElementById('alert-list'),
    alertCounter: document.getElementById('alert-counter'),
    transactionsBody: document.getElementById('transactions-body'),

    footerUptime: document.getElementById('footer-uptime'),
};


// ════════════════════════════════════════════════════════
// Charts
// ════════════════════════════════════════════════════════
let volumeChart, riskChart;

function initCharts() {
    // Volume chart
    const volumeCtx = document.getElementById('volume-chart').getContext('2d');

    const volumeGradient = volumeCtx.createLinearGradient(0, 0, 0, 300);
    volumeGradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    volumeGradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

    const alertGradient = volumeCtx.createLinearGradient(0, 0, 0, 300);
    alertGradient.addColorStop(0, 'rgba(239, 68, 68, 0.3)');
    alertGradient.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

    volumeChart = new Chart(volumeCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Transactions',
                    data: [],
                    borderColor: '#6366f1',
                    backgroundColor: volumeGradient,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: '#6366f1',
                },
                {
                    label: 'Fraud Alerts',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: alertGradient,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: '#ef4444',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    align: 'end',
                    labels: {
                        color: '#94a3b8',
                        font: { family: "'Inter', sans-serif", size: 11, weight: '500' },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 16,
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 42, 0.95)',
                    borderColor: 'rgba(99, 102, 241, 0.3)',
                    borderWidth: 1,
                    titleFont: { family: "'Inter', sans-serif", weight: '600' },
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                },
            },
            scales: {
                x: {
                    grid: { color: 'rgba(99, 102, 241, 0.06)', drawBorder: false },
                    ticks: {
                        color: '#64748b',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        maxTicksLimit: 8,
                    },
                },
                y: {
                    grid: { color: 'rgba(99, 102, 241, 0.06)', drawBorder: false },
                    ticks: {
                        color: '#64748b',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                    },
                    beginAtZero: true,
                },
            },
            animation: {
                duration: 400,
                easing: 'easeOutQuart',
            },
        },
    });

    // Risk distribution doughnut chart
    const riskCtx = document.getElementById('risk-chart').getContext('2d');

    riskChart = new Chart(riskCtx, {
        type: 'doughnut',
        data: {
            labels: ['Critical', 'High', 'Medium', 'Low'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: [
                    'rgba(220, 38, 38, 0.8)',
                    'rgba(239, 68, 68, 0.7)',
                    'rgba(245, 158, 11, 0.7)',
                    'rgba(16, 185, 129, 0.7)',
                ],
                borderColor: [
                    'rgba(220, 38, 38, 1)',
                    'rgba(239, 68, 68, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(16, 185, 129, 1)',
                ],
                borderWidth: 2,
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#94a3b8',
                        font: { family: "'Inter', sans-serif", size: 11, weight: '500' },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 16,
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 42, 0.95)',
                    borderColor: 'rgba(99, 102, 241, 0.3)',
                    borderWidth: 1,
                    titleFont: { family: "'Inter', sans-serif", weight: '600' },
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                },
            },
            animation: {
                animateRotate: true,
                duration: 600,
            },
        },
    });
}


// ════════════════════════════════════════════════════════
// Chart update helpers
// ════════════════════════════════════════════════════════
let txnBucket = 0;
let alertBucket = 0;
let bucketInterval = null;

function startBucketInterval() {
    // Every 3 seconds, push aggregated counts to the chart
    bucketInterval = setInterval(() => {
        const now = new Date();
        const label = now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });

        state.volumeLabels.push(label);
        state.volumeData.push(txnBucket);
        state.alertVolumeData.push(alertBucket);

        // Trim to max points
        if (state.volumeLabels.length > state.maxChartPoints) {
            state.volumeLabels.shift();
            state.volumeData.shift();
            state.alertVolumeData.shift();
        }

        // Update chart
        volumeChart.data.labels = [...state.volumeLabels];
        volumeChart.data.datasets[0].data = [...state.volumeData];
        volumeChart.data.datasets[1].data = [...state.alertVolumeData];
        volumeChart.update('none');

        // Reset buckets
        txnBucket = 0;
        alertBucket = 0;
    }, 3000);
}


// ════════════════════════════════════════════════════════
// UI Update Functions
// ════════════════════════════════════════════════════════
function animateValue(el, value) {
    el.textContent = value;
    el.classList.add('updated');
    setTimeout(() => el.classList.remove('updated'), 300);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(amount);
}

function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

function updateStats(stats) {
    if (stats) {
        state.totalTransactions = stats.total_transactions || state.totalTransactions;
        state.totalAlerts = stats.total_alerts || state.totalAlerts;
        state.mlConfirmed = stats.ml_confirmed_fraud || state.mlConfirmed || 0;
        state.aiCount = stats.ai_briefings_generated || state.aiCount || 0;
        state.fraudRate = stats.fraud_rate || state.fraudRate;
        state.amountFlagged = stats.total_amount_flagged || state.amountFlagged;
    }

    if (els.statTotalTxns) animateValue(els.statTotalTxns, formatNumber(state.totalTransactions));
    if (els.statTotalAlerts) animateValue(els.statTotalAlerts, formatNumber(state.totalAlerts));
    if (els.statMlConfirmed) animateValue(els.statMlConfirmed, formatNumber(state.mlConfirmed));
    if (els.statAiCount) animateValue(els.statAiCount, formatNumber(state.aiCount));
    if (els.statFraudPct) animateValue(els.statFraudPct, state.fraudRate.toFixed(1) + '%');
    if (els.statAmountFlagged) animateValue(els.statAmountFlagged, formatCurrency(state.amountFlagged));
}

// ════════════════════════════════════════════════════════
// Entity Display Sanitizer (Guarantees crisp FinTech entities)
// ════════════════════════════════════════════════════════
const UI_MERCHANTS = {
    GROCERY: ["Whole Foods Market", "Trader Joe's", "Costco Wholesale", "Kroger Fresh"],
    ELECTRONICS: ["Apple Store Fifth Ave", "Best Buy Megastore", "Micro Center Tech", "Sony Flagship"],
    RESTAURANT: ["Nobu Downtown", "Le Bernardin", "Starbucks Reserve", "Chipotle Grill"],
    TRAVEL: ["Delta Air Lines", "Emirates First Class", "Airbnb Luxury Escapes", "Marriott Marquis"],
    GAS: ["Shell Oil Express", "Chevron Highway Fuel", "ExxonMobil Travel Stop", "BP Connect"],
    ONLINE_SHOPPING: ["Amazon Prime Direct", "Shopify Merchant Hub", "eBay Global Commerce", "Nordstrom Luxury"],
    ATM_WITHDRAWAL: ["Chase Premier ATM", "Bank of America Cash", "Wells Fargo Express", "Citibank Global Cash"],
    TRANSFER: ["Stripe Wire Transfer", "Apex Crypto Exchange", "Binance Global OTC", "Wise Wire Transfer"],
    ENTERTAINMENT: ["Netflix 4K Ultra", "Ticketmaster VIP", "Spotify Hi-Fi", "AMC IMAX Theatres"],
    HEALTHCARE: ["CVS Health Center", "Walgreens Care", "Mayo Clinic Health", "Kaiser Permanente"],
};
const UI_LOCATIONS = [
    "New York, NY (USA)", "San Francisco, CA (USA)", "London, UK",
    "Zurich, Switzerland", "Singapore, SG", "Dubai, UAE",
    "Tokyo, Japan", "Frankfurt, Germany", "Toronto, Canada",
    "Sydney, Australia", "Paris, France"
];

function stringHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

function sanitizeEntityClient(data) {
    if (!data) return {};
    const d = { ...data };

    // 1. Transaction ID
    let rawTx = String(d.transaction_id || '');
    if (!rawTx.startsWith('txn_') || rawTx.length > 20 || /[^a-zA-Z0-9_-]/.test(rawTx)) {
        const h = stringHash(rawTx || String(Math.random())).toString(16).padStart(8, '0').slice(0, 8);
        d.transaction_id = `txn_${h}`;
    }

    // 2. Alert ID
    let rawAlt = String(d.alert_id || '');
    if (d.alert_id || d.risk_level) {
        if (!rawAlt.startsWith('alt_') || rawAlt.length > 20 || /[^a-zA-Z0-9_-]/.test(rawAlt)) {
            const h = stringHash(rawAlt || rawTx || String(Math.random())).toString(16).padStart(8, '0').slice(0, 8);
            d.alert_id = `alt_${h}`;
        }
    }

    // 3. User ID
    let rawUser = String(d.user_id || '');
    if (!/^user_\d{3,4}$/.test(rawUser)) {
        const h = (stringHash(rawUser) % 900) + 100;
        d.user_id = `user_${h}`;
    }

    // 4. Category
    d.category = (d.category || 'ONLINE_SHOPPING').toUpperCase();

    // 5. Merchant
    let rawMerch = String(d.merchant || '').trim();
    if (!rawMerch || rawMerch.length < 3 || /[^a-zA-Z0-9\s'&.-]/.test(rawMerch)) {
        const list = UI_MERCHANTS[d.category] || UI_MERCHANTS.ONLINE_SHOPPING;
        d.merchant = list[stringHash(rawMerch + d.user_id) % list.length];
    }

    // 6. Location
    let rawLoc = String(d.location || '').trim();
    if (!rawLoc || rawLoc.length < 4 || /[^a-zA-Z0-9\s(),.-]/.test(rawLoc)) {
        d.location = UI_LOCATIONS[stringHash(rawLoc + d.user_id) % UI_LOCATIONS.length];
    }

    return d;
}

function addAlertToFeed(alert) {
    const data = sanitizeEntityClient(alert.data);

    // Remove empty state if present
    const emptyState = els.alertList.querySelector('.alert-empty');
    if (emptyState) emptyState.remove();

    // Create alert element
    const el = document.createElement('div');
    el.className = 'alert-item flash';

    const riskClass = `risk-${(data.risk_level || 'low').toLowerCase()}`;
    const time = data.flagged_at
        ? new Date(data.flagged_at).toLocaleTimeString('en-US', { hour12: false })
        : new Date().toLocaleTimeString('en-US', { hour12: false });

    const mlScore = data.ml_score;
    const aiBriefing = data.ai_briefing;

    const mlBadgeHtml = mlScore
        ? `<span class="ml-tag ml-${(mlScore.risk_tier || 'medium').toLowerCase()}">🧠 ML: ${mlScore.fraud_probability}% (${mlScore.ml_classification})</span>`
        : '';

    const aiBriefingHtml = aiBriefing
        ? `
        <div class="ai-briefing-accordion">
            <div class="ai-accordion-header" onclick="this.closest('.ai-briefing-accordion').classList.toggle('expanded')">
                <span class="ai-sparkle-icon">✨</span>
                <span class="ai-header-title">AI Forensic Intelligence Briefing</span>
                <span class="ai-chevron">▾</span>
            </div>
            <div class="ai-accordion-body">
                <p class="ai-narrative">${aiBriefing.briefing_summary}</p>
                <div class="ai-deviation-box">
                    <span class="deviation-icon">📊</span>
                    <span>${aiBriefing.behavioral_reasoning}</span>
                </div>
                <div class="ai-action-card action-threat-${(aiBriefing.threat_level || 'high').toLowerCase()}">
                    <div class="action-header">
                        <span class="action-tag">RECOMMENDED ACTION</span>
                        <span class="action-code">${aiBriefing.recommended_action}</span>
                    </div>
                    <div class="action-desc">${aiBriefing.action_text}</div>
                </div>
                ${mlScore && mlScore.risk_factors ? `
                <div class="ai-factors-row">
                    ${mlScore.risk_factors.map(f => `<span class="factor-badge">⚡ ${f.factor}: ${f.detail}</span>`).join('')}
                </div>
                ` : ''}
            </div>
        </div>
        `
        : '';

    el.innerHTML = `
        <div class="alert-top-row">
            <span class="alert-risk-badge ${riskClass}">${data.risk_level || 'UNKNOWN'}</span>
            ${mlBadgeHtml}
            <span class="alert-time">${time}</span>
        </div>
        <div class="alert-info">
            <div class="alert-title">${data.anomaly_type?.replace(/_/g, ' ') || 'Anomaly'} — ${data.merchant || 'Unknown'}</div>
            <div class="alert-details">
                <span class="alert-detail-item">
                    <span class="alert-amount">${formatCurrency(data.amount || 0)}</span>
                </span>
                <span class="alert-detail-item">👤 ${data.user_id || '?'}</span>
                <span class="alert-detail-item">📍 ${data.location || '?'}</span>
                <span class="alert-detail-item">💳 ${data.card_type || 'Card'}</span>
            </div>
        </div>
        ${aiBriefingHtml}
    `;

    // Prepend (newest first)
    els.alertList.prepend(el);

    // Trim old alerts
    while (els.alertList.children.length > state.maxAlerts) {
        els.alertList.lastChild.remove();
    }

    // Update counter
    els.alertCounter.textContent = `${state.totalAlerts} alerts`;

    // Update risk distribution
    const risk = (data.risk_level || 'LOW').toUpperCase();
    if (state.riskCounts[risk] !== undefined) {
        state.riskCounts[risk]++;
        riskChart.data.datasets[0].data = [
            state.riskCounts.CRITICAL,
            state.riskCounts.HIGH,
            state.riskCounts.MEDIUM,
            state.riskCounts.LOW,
        ];
        riskChart.update('none');
    }

    // Increment alert bucket for volume chart
    alertBucket++;
}

function addTransactionToTable(message) {
    const data = sanitizeEntityClient(message.data);
    const isFlagged = data.is_flagged || (data.ml_score && data.ml_score.fraud_probability >= 50.0) || false;
    const mlScore = data.ml_score;

    const row = document.createElement('tr');
    if (isFlagged) row.className = 'flagged';

    const statusHtml = isFlagged
        ? `<span class="status-pill status-flagged">⚠ Flagged ${mlScore ? `(${mlScore.fraud_probability}%)` : ''}</span>`
        : `<span class="status-pill status-ok">✓ Clean ${mlScore ? `(${mlScore.fraud_probability}%)` : ''}</span>`;

    row.innerHTML = `
        <td>${data.transaction_id || '—'}</td>
        <td>${data.user_id || '—'}</td>
        <td class="${isFlagged ? 'td-flagged' : 'td-amount'}">${formatCurrency(data.amount || 0)}</td>
        <td>${data.merchant || '—'}</td>
        <td>${data.category || '—'}</td>
        <td>${data.location || '—'}</td>
        <td>${statusHtml}</td>
    `;

    // Prepend (newest first)
    els.transactionsBody.prepend(row);

    // Trim old rows
    while (els.transactionsBody.children.length > state.maxTransactions) {
        els.transactionsBody.lastChild.remove();
    }

    // Increment txn bucket for volume chart
    txnBucket++;
}


// ════════════════════════════════════════════════════════
// WebSocket Connection
// ════════════════════════════════════════════════════════
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        state.connected = true;
        state.reconnectAttempts = 0;
        els.connectionStatus.classList.remove('disconnected');
        els.statusText.textContent = 'Connected';
        console.log('[WS] Connected');
    };

    state.ws.onclose = () => {
        state.connected = false;
        els.connectionStatus.classList.add('disconnected');
        els.statusText.textContent = 'Disconnected';
        console.log('[WS] Disconnected');

        // Reconnect
        if (state.reconnectAttempts < state.maxReconnectAttempts) {
            state.reconnectAttempts++;
            const delay = Math.min(
                state.reconnectDelay * Math.pow(1.5, state.reconnectAttempts - 1),
                30000
            );
            console.log(`[WS] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempts})`);
            setTimeout(connectWebSocket, delay);
        }
    };

    state.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
    };

    state.ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);

            switch (message.type) {
                case 'init':
                    // Initial state from server
                    if (message.mode === 'live') {
                        els.modeBadge.classList.add('live');
                        els.modeBadge.querySelector('span').textContent = 'LIVE';
                    }
                    updateStats(message.stats);
                    break;

                case 'transaction':
                    addTransactionToTable(message);
                    if (message.stats) updateStats(message.stats);
                    break;

                case 'fraud_alert':
                    addAlertToFeed(message);
                    if (message.stats) updateStats(message.stats);
                    break;

                case 'pong':
                    break;

                default:
                    console.log('[WS] Unknown message type:', message.type);
            }
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };
}

// Keep-alive ping
setInterval(() => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send('ping');
    }
}, 30000);


// ════════════════════════════════════════════════════════
// Uptime Timer
// ════════════════════════════════════════════════════════
function updateUptime() {
    const seconds = Math.floor((Date.now() - state.startTime) / 1000);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;

    const parts = [];
    if (h > 0) parts.push(`${h}h`);
    if (m > 0 || h > 0) parts.push(`${m}m`);
    parts.push(`${s}s`);

    els.footerUptime.textContent = `Uptime: ${parts.join(' ')}`;
}

setInterval(updateUptime, 1000);


// ════════════════════════════════════════════════════════
// Initialize
// ════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    startBucketInterval();
    connectWebSocket();
    updateUptime();
});
