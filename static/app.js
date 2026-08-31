// AutoPortfolioManager Quantitative & Portfolio Engine Frontend

let cachedTickersList = [];
let sliceChartInstance = null;
let mfEquityChartInstance = null;
let portfolioEquityChartInstance = null;
let lastMfResult = null;
let activeConditionInput = "conditionUp";

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    loadCachedTickers();
    loadMathVariables();
    bindEvents();
});

function showAlert(message, isError = false, durationMs = 4000) {
    const alertBox = document.getElementById("alertBox");
    alertBox.textContent = message;
    alertBox.classList.remove("hidden");
    if (isError) {
        alertBox.style.borderColor = "#ffffff";
        alertBox.style.backgroundColor = "#27272a";
    } else {
        alertBox.style.borderColor = "#ffffff";
        alertBox.style.backgroundColor = "#18181b";
    }

    setTimeout(() => {
        alertBox.classList.add("hidden");
    }, durationMs);
}

function initTabs() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

            tab.classList.add("active");
            const targetId = tab.getAttribute("data-tab");
            const targetElem = document.getElementById(targetId);
            if (targetElem) targetElem.classList.add("active");
        });
    });
}

function bindEvents() {
    document.getElementById("btnDownloadAll").addEventListener("click", downloadAllData);
    document.getElementById("btnRefreshTickers").addEventListener("click", loadCachedTickers);

    document.getElementById("btnExportCsvDirect").addEventListener("click", () => {
        const ticker = document.getElementById("downloadTicker").value.trim();
        const start = document.getElementById("sliceStart").value;
        const end = document.getElementById("sliceEnd").value;
        if (!ticker) {
            showAlert("Введіть тікер для експорту", true);
            return;
        }
        window.location.href = `/api/export-slice-csv?ticker=${encodeURIComponent(ticker)}&start_date=${start}&end_date=${end}`;
    });

    document.getElementById("btnLoadSlice").addEventListener("click", loadDataSlice);
    document.getElementById("btnDownloadSliceCsv").addEventListener("click", () => {
        const ticker = document.getElementById("viewTickerSelect").value;
        const start = document.getElementById("viewStartDate").value;
        const end = document.getElementById("viewEndDate").value;
        if (!ticker) {
            showAlert("Оберіть тікер", true);
            return;
        }
        window.location.href = `/api/export-slice-csv?ticker=${encodeURIComponent(ticker)}&start_date=${start}&end_date=${end}`;
    });

    const cUp = document.getElementById("conditionUp");
    const cDown = document.getElementById("conditionDown");
    if (cUp) cUp.addEventListener("focus", () => { activeConditionInput = "conditionUp"; });
    if (cDown) cDown.addEventListener("focus", () => { activeConditionInput = "conditionDown"; });

    document.getElementById("btnRunMfBacktest").addEventListener("click", runMultiFactorBacktest);
    document.getElementById("btnGenerateLiveForecast").addEventListener("click", generateLiveForecast);
    document.getElementById("btnExportMfCsv").addEventListener("click", exportMfCsv);

    document.getElementById("btnRunPortfolioBacktest").addEventListener("click", runPortfolioBacktest);
    document.getElementById("btnRunCustomBacktest").addEventListener("click", runCustomBacktest);
}

async function loadMathVariables() {
    try {
        const res = await fetch("/api/math-variables");
        const vars = await res.json();
        const container = document.getElementById("varBadges");
        if (!container) return;
        
        container.innerHTML = vars.map(v => `
            <span class="var-badge" title="${v.description}" onclick="insertVarName('${v.name}')">${v.name}</span>
        `).join("");
    } catch (err) {
        console.error("Error loading math variables:", err);
    }
}

function insertVarName(varName) {
    const input = document.getElementById(activeConditionInput);
    if (!input) return;
    
    const start = input.selectionStart || input.value.length;
    const end = input.selectionEnd || input.value.length;
    const text = input.value;
    
    input.value = text.substring(0, start) + (start > 0 && text[start-1] !== ' ' ? ' ' : '') + varName + ' ' + text.substring(end);
    input.focus();
}

async function loadCachedTickers() {
    try {
        const res = await fetch("/api/cached-tickers");
        const data = await res.json();
        cachedTickersList = data;
        renderCachedTable(data);
        populateTickerSelects(data);
        populatePortfolioCheckboxes(data);
    } catch (err) {
        console.error("Error loading cached tickers:", err);
    }
}

function renderCachedTable(tickers) {
    const tbody = document.querySelector("#cachedTickersTable tbody");
    if (!tickers || tickers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Немає збережених даних. Введіть тікер та натисніть "Завантажити".</td></tr>`;
        return;
    }

    tbody.innerHTML = tickers.map(t => `
        <tr>
            <td><strong>${t.ticker}</strong></td>
            <td>${t.records.toLocaleString()}</td>
            <td>${t.start_date} &rarr; ${t.end_date}</td>
            <td>$${t.last_price}</td>
            <td>
                <button class="btn-danger-sm" onclick="deleteTicker('${t.ticker}')">Видалити</button>
            </td>
        </tr>
    `).join("");
}

function populateTickerSelects(tickers) {
    const selects = ["viewTickerSelect", "mfTickerSelect", "customTickerSelect"];
    const options = tickers.map(t => `<option value="${t.ticker}">${t.ticker} (${t.records} свічок: ${t.start_date} - ${t.end_date})</option>`).join("");

    selects.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = options || `<option value="">-- Немає даних --</option>`;
    });
}

function populatePortfolioCheckboxes(tickers) {
    const group = document.getElementById("portfolioTickersCheckboxGroup");
    if (!group) return;

    if (!tickers || tickers.length === 0) {
        group.innerHTML = `<span class="text-muted">Немає завантажених активів</span>`;
        return;
    }

    const defaultSelected = ["AAPL", "NVDA", "MSFT", "AMZN", "QQQ", "TSLA", "GOOGL"];
    group.innerHTML = tickers.map(t => {
        const checked = defaultSelected.includes(t.ticker) ? "checked" : "";
        return `
            <label class="pill-label">
                <input type="checkbox" name="portTicker" value="${t.ticker}" ${checked}>
                <span>${t.ticker}</span>
            </label>
        `;
    }).join("");
}

async function downloadAllData() {
    const tickerInput = document.getElementById("downloadTicker");
    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) {
        showAlert("Введіть символ тікера (наприклад: AAPL)", true);
        return;
    }

    const btn = document.getElementById("btnDownloadAll");
    const originalText = btn.textContent;
    btn.textContent = "Завантаження...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/download-all", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker })
        });
        const result = await res.json();
        if (result.success) {
            showAlert(result.message);
            tickerInput.value = "";
            await loadCachedTickers();
        } else {
            showAlert(result.message || "Помилка завантаження", true);
        }
    } catch (err) {
        showAlert("Помилка зв'язку з сервером: " + err.message, true);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function deleteTicker(ticker) {
    if (!confirm(`Ви дійсно бажаєте видалити збережені дані для ${ticker}?`)) return;

    try {
        const res = await fetch("/api/delete-ticker", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker })
        });
        const data = await res.json();
        showAlert(data.message);
        loadCachedTickers();
    } catch (err) {
        showAlert("Помилка видалення: " + err.message, true);
    }
}

async function loadDataSlice() {
    const ticker = document.getElementById("viewTickerSelect").value;
    const startDate = document.getElementById("viewStartDate").value;
    const endDate = document.getElementById("viewEndDate").value;

    if (!ticker) {
        showAlert("Оберіть збережений тікер", true);
        return;
    }

    const btn = document.getElementById("btnLoadSlice");
    btn.textContent = "Завантаження...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/get-slice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, start_date: startDate, end_date: endDate })
        });
        const data = await res.json();

        if (!data.success) {
            showAlert(data.message || "Помилка отримання зрізу", true);
            return;
        }

        renderSliceTable(data.data);
        renderSliceStats(data);
        renderSliceChart(data.ticker, data.data);
    } catch (err) {
        showAlert("Помилка: " + err.message, true);
    } finally {
        btn.textContent = "Показати зріз";
        btn.disabled = false;
    }
}

function renderSliceStats(data) {
    const records = data.data;
    if (!records || records.length === 0) return;

    const statsBar = document.getElementById("sliceStatsBar");
    statsBar.classList.remove("hidden");

    document.getElementById("sliceCount").textContent = records.length.toLocaleString();
    document.getElementById("sliceRange").textContent = `${data.start_date} -> ${data.end_date}`;

    const p0 = records[0].close;
    const pEnd = records[records.length - 1].close;
    const changePct = ((pEnd - p0) / p0) * 100.0;

    document.getElementById("sliceFirstClose").textContent = `$${p0.toFixed(2)}`;
    document.getElementById("sliceLastClose").textContent = `$${pEnd.toFixed(2)}`;
    document.getElementById("sliceChangePct").textContent = `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
}

function renderSliceTable(records) {
    const tbody = document.querySelector("#sliceDataTable tbody");
    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Дані відсутні</td></tr>`;
        return;
    }

    const displayRows = records.slice(-300);
    tbody.innerHTML = displayRows.map(r => `
        <tr>
            <td>${r.date}</td>
            <td>$${r.open}</td>
            <td>$${r.high}</td>
            <td>$${r.low}</td>
            <td>$${r.close}</td>
            <td>${r.volume.toLocaleString()}</td>
            <td>${r.sma_20 !== null ? "$" + r.sma_20 : "-"}</td>
            <td>${r.sma_50 !== null ? "$" + r.sma_50 : "-"}</td>
        </tr>
    `).join("");
}

function renderSliceChart(ticker, records) {
    const ctx = document.getElementById("sliceChart").getContext("2d");
    if (sliceChartInstance) {
        sliceChartInstance.destroy();
    }

    const labels = records.map(r => r.date);
    const closePrices = records.map(r => r.close);
    const sma20 = records.map(r => r.sma_20);
    const sma50 = records.map(r => r.sma_50);

    sliceChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: `${ticker} Close`,
                    data: closePrices,
                    borderColor: "#ffffff",
                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.1,
                    fill: true
                },
                {
                    label: "SMA 20",
                    data: sma20,
                    borderColor: "#a1a1aa",
                    borderWidth: 1,
                    borderDash: [4, 4],
                    pointRadius: 0,
                    tension: 0.1
                },
                {
                    label: "SMA 50",
                    data: sma50,
                    borderColor: "#71717a",
                    borderWidth: 1,
                    pointRadius: 0,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: { labels: { color: "#fafafa", font: { family: "SF Mono, monospace", size: 11 } } },
                tooltip: {
                    backgroundColor: "#18181b",
                    titleColor: "#fafafa",
                    bodyColor: "#a1a1aa",
                    borderColor: "#27272a",
                    borderWidth: 1,
                    titleFont: { family: "SF Mono, monospace" },
                    bodyFont: { family: "SF Mono, monospace" }
                }
            },
            scales: {
                x: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", maxTicksLimit: 12, font: { family: "SF Mono, monospace", size: 10 } } },
                y: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", font: { family: "SF Mono, monospace", size: 10 } } }
            }
        }
    });
}

// Tab 3: Multi-Factor Backtest with ATR Stop Loss
async function runMultiFactorBacktest() {
    const ticker = document.getElementById("mfTickerSelect").value;
    const startDate = document.getElementById("mfStartDate").value;
    const endDate = document.getElementById("mfEndDate").value;
    const trainBars = parseInt(document.getElementById("mfTrainBars").value) || 60;
    const predictBars = parseInt(document.getElementById("mfPredictBars").value) || 15;
    const sizingMode = document.getElementById("mfSizingMode").value;
    const atrSl = parseFloat(document.getElementById("mfAtrSl").value) || 2.0;
    const vBreaker = document.getElementById("mfVBreaker").checked;

    const wMr = parseFloat(document.getElementById("mfWMeanRevert").value) || 0.15;
    const wMom = parseFloat(document.getElementById("mfWMomentum").value) || 0.60;
    const wAr1 = parseFloat(document.getElementById("mfWAR1").value) || 0.15;
    const wCurv = parseFloat(document.getElementById("mfWCurv").value) || 0.10;
    const threshUp = parseFloat(document.getElementById("mfThreshUp").value) || 0.18;
    const threshDown = parseFloat(document.getElementById("mfThreshDown").value) || -0.18;

    if (!ticker) {
        showAlert("Оберіть збережену компанію для бектесту", true);
        return;
    }

    const btn = document.getElementById("btnRunMfBacktest");
    const originalText = btn.textContent;
    btn.textContent = "Обчислення бектесту з ATR-захистом...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/run-multi-factor-backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker,
                start_date: startDate,
                end_date: endDate,
                train_bars: trainBars,
                predict_bars: predictBars,
                step_bars: predictBars,
                w_mean_revert: wMr,
                w_momentum: wMom,
                w_ar1: wAr1,
                w_curv: wCurv,
                threshold_up: threshUp,
                threshold_down: threshDown,
                sizing_mode: sizingMode,
                atr_stop_loss_mult: atrSl,
                use_v_reversal_breaker: vBreaker
            })
        });

        const result = await res.json();

        if (!result.success) {
            showAlert(result.error || "Помилка виконання бектесту", true);
            return;
        }

        lastMfResult = result;
        renderMfResults(result);
        showAlert(`Бектест завершено: перевірено ${result.total_windows} вікон (${result.active_trades} угод)`);
    } catch (err) {
        showAlert("Помилка виконання: " + err.message, true);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function generateLiveForecast() {
    const ticker = document.getElementById("mfTickerSelect").value;
    const trainBars = parseInt(document.getElementById("mfTrainBars").value) || 60;
    const predictBars = parseInt(document.getElementById("mfPredictBars").value) || 15;
    const sizingMode = document.getElementById("mfSizingMode").value;
    const atrSl = parseFloat(document.getElementById("mfAtrSl").value) || 2.0;

    const wMr = parseFloat(document.getElementById("mfWMeanRevert").value) || 0.15;
    const wMom = parseFloat(document.getElementById("mfWMomentum").value) || 0.60;
    const wAr1 = parseFloat(document.getElementById("mfWAR1").value) || 0.15;
    const wCurv = parseFloat(document.getElementById("mfWCurv").value) || 0.10;
    const threshUp = parseFloat(document.getElementById("mfThreshUp").value) || 0.18;
    const threshDown = parseFloat(document.getElementById("mfThreshDown").value) || -0.18;

    if (!ticker) {
        showAlert("Оберіть збережену компанію", true);
        return;
    }

    const btn = document.getElementById("btnGenerateLiveForecast");
    const originalText = btn.textContent;
    btn.textContent = "Аналіз останніх даних...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/generate-live-forecast", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker,
                train_bars: trainBars,
                predict_bars: predictBars,
                w_mean_revert: wMr,
                w_momentum: wMom,
                w_ar1: wAr1,
                w_curv: wCurv,
                threshold_up: threshUp,
                threshold_down: threshDown,
                sizing_mode: sizingMode,
                atr_stop_loss_mult: atrSl
            })
        });

        const data = await res.json();

        if (!data.success) {
            showAlert(data.error || "Помилка формування прогнозу", true);
            return;
        }

        renderLiveForecast(data);
        showAlert(`Згенеровано сліпий прогноз для ${ticker} з ATR-рівнями!`);
    } catch (err) {
        showAlert("Помилка: " + err.message, true);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

function renderLiveForecast(fc) {
    const card = document.getElementById("liveForecastCard");
    card.classList.remove("hidden");

    document.getElementById("liveForecastDate").textContent = `Дані до: ${fc.as_of_date} ($${fc.last_price})`;
    document.getElementById("liveDirection").textContent = fc.direction_label;
    document.getElementById("liveScore").textContent = `Composite Score: ${fc.composite_score}`;
    
    document.getElementById("liveTargetPrice").textContent = `$${fc.target_price}`;
    const slText = fc.suggested_stop_loss_price ? `$${fc.suggested_stop_loss_price} (${fc.atr_pct}% ATR)` : "Без SL";
    document.getElementById("liveSlPrice").textContent = `Stop-Loss: ${slText}`;

    document.getElementById("livePosSize").textContent = `S = ${fc.recommended_position_size}`;
    document.getElementById("liveExpReturn").textContent = `Очікувана дохідність: ${fc.expected_return_pct >= 0 ? '+' : ''}${fc.expected_return_pct}%`;

    const qm = fc.quant_metrics || {};
    document.getElementById("liveAtr").textContent = `ATR: $${fc.atr_dollars} (${fc.atr_pct}%)`;
    document.getElementById("liveRegime").textContent = `Hurst: ${qm.hurst ?? '-'} | CHOP: ${fc.chop_index ?? '-'}`;

    document.getElementById("liveReasonBox").textContent = `Обґрунтування: ${fc.reason}. Динамічний ATR-захист встановлено на рівні $${fc.suggested_stop_loss_price || '-'}.`;
}

function renderMfResults(res) {
    document.getElementById("mfResultsArea").classList.remove("hidden");

    document.getElementById("mfResAccuracy").textContent = `${res.accuracy_pct}%`;
    document.getElementById("mfResTradesCount").textContent = `${res.correct_trades} вірно / ${res.active_trades} активних (${res.neutral_windows} нейтральних)`;

    const evSign = res.expected_value_pct >= 0 ? "+" : "";
    document.getElementById("mfResEV").textContent = `${evSign}${res.expected_value_pct}%`;
    document.getElementById("mfResWinLossRate").textContent = `Win: ${res.win_rate_pct}% | Loss: ${res.loss_rate_pct}% | Payoff: ${res.win_loss_payoff}`;

    document.getElementById("mfResSharpe").textContent = `${res.sharpe_ratio}`;
    document.getElementById("mfResSortino").textContent = `Sortino: ${res.sortino_ratio} | Calmar: ${res.calmar_ratio}`;

    const retElem = document.getElementById("mfResReturn");
    retElem.textContent = `${res.total_return_pct >= 0 ? "+" : ""}${res.total_return_pct}%`;
    document.getElementById("mfResBhReturn").textContent = `Buy & Hold: ${res.buy_and_hold_return_pct >= 0 ? "+" : ""}${res.buy_and_hold_return_pct}%`;

    document.getElementById("mfResMaxDd").textContent = `-${res.max_drawdown_pct}%`;
    document.getElementById("mfResProfitFactor").textContent = `Profit Factor: ${res.profit_factor}`;

    renderMfEquityChart(res.equity_curve);
    renderMfPredictionsTable(res.predictions);
}

function renderMfEquityChart(curve) {
    const ctx = document.getElementById("mfEquityChart").getContext("2d");
    if (mfEquityChartInstance) {
        mfEquityChartInstance.destroy();
    }

    const labels = curve.map(c => c.date);
    const strategyEq = curve.map(c => c.strategy_equity);
    const bhEq = curve.map(c => c.buy_hold_equity);

    mfEquityChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Стратегія з ATR-захистом",
                    data: strategyEq,
                    borderColor: "#ffffff",
                    backgroundColor: "rgba(255, 255, 255, 0.08)",
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.1,
                    fill: true
                },
                {
                    label: "Buy & Hold Benchmark",
                    data: bhEq,
                    borderColor: "#71717a",
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: { labels: { color: "#fafafa", font: { family: "SF Mono, monospace", size: 11 } } },
                tooltip: {
                    backgroundColor: "#18181b",
                    titleColor: "#fafafa",
                    bodyColor: "#a1a1aa",
                    borderColor: "#27272a",
                    borderWidth: 1,
                    titleFont: { family: "SF Mono, monospace" },
                    bodyFont: { family: "SF Mono, monospace" }
                }
            },
            scales: {
                x: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", maxTicksLimit: 12, font: { family: "SF Mono, monospace", size: 10 } } },
                y: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", font: { family: "SF Mono, monospace", size: 10 } } }
            }
        }
    });
}

function renderMfPredictionsTable(predictions) {
    const tbody = document.querySelector("#mfPredictionsTable tbody");
    if (!predictions || predictions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">Немає даних</td></tr>`;
        return;
    }

    tbody.innerHTML = predictions.map(p => {
        let predBadge = `<span class="badge badge-neutral">HOLD</span>`;
        if (p.predicted_direction === 1) predBadge = `<span class="badge badge-up">&uarr; BUY [S=${p.position_size}]</span>`;
        if (p.predicted_direction === -1) predBadge = `<span class="badge badge-down">&darr; SELL [S=${p.position_size}]</span>`;

        let resultBadge = `<span class="badge badge-neutral">-</span>`;
        if (p.is_correct === true) resultBadge = `<span class="badge badge-success">&#10003; ВІРНО</span>`;
        if (p.is_correct === false) resultBadge = `<span class="badge badge-fail">&#10007; ПОМИЛКА</span>`;

        const retSign = p.actual_return_pct >= 0 ? "+" : "";
        const stratRetSign = p.strategy_return_pct >= 0 ? "+" : "";

        return `
            <tr>
                <td>${p.window_index}</td>
                <td>${p.train_start} &rarr; ${p.train_end}</td>
                <td>${p.test_start} &rarr; ${p.test_end}</td>
                <td>${predBadge}</td>
                <td style="font-size:11px;">
                    <div>${p.reason}</div>
                    <div style="color:#a1a1aa; margin-top:2px; font-weight:bold;">Вихід: ${p.exit_reason || 'Час'}</div>
                </td>
                <td>$${p.price_start} &rarr; $${p.price_end}</td>
                <td>${retSign}${p.actual_return_pct}%</td>
                <td>${resultBadge}</td>
                <td><strong>${stratRetSign}${p.strategy_return_pct}%</strong></td>
            </tr>
        `;
    }).join("");
}

// Tab 4: Multi-Asset Portfolio Ensemble Backtest
async function runPortfolioBacktest() {
    const checked = Array.from(document.querySelectorAll("input[name='portTicker']:checked")).map(el => el.value);
    if (!checked || checked.length === 0) {
        showAlert("Оберіть хоча б один актив для портфельного кошика", true);
        return;
    }

    const trainBars = parseInt(document.getElementById("portTrainBars").value) || 60;
    const predictBars = parseInt(document.getElementById("portPredictBars").value) || 15;
    const atrSl = parseFloat(document.getElementById("portAtrSl").value) || 2.0;

    const btn = document.getElementById("btnRunPortfolioBacktest");
    const originalText = btn.textContent;
    btn.textContent = `Обчислення портфеля (${checked.length} активів)...`;
    btn.disabled = true;

    try {
        const res = await fetch("/api/run-portfolio-backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                tickers: checked,
                train_bars: trainBars,
                predict_bars: predictBars,
                step_bars: predictBars,
                atr_stop_loss_mult: atrSl
            })
        });

        const result = await res.json();

        if (!result.success) {
            showAlert(result.error || "Помилка портфельного бектесту", true);
            return;
        }

        renderPortfolioResults(result);
        showAlert(`Портфельний бектест завершено! Диверсифіковано ${checked.length} активів, Sharpe ${result.sharpe_ratio}`);
    } catch (err) {
        showAlert("Помилка: " + err.message, true);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

function renderPortfolioResults(res) {
    document.getElementById("portfolioResultsArea").classList.remove("hidden");

    document.getElementById("portAccuracy").textContent = `${res.accuracy_pct}%`;
    document.getElementById("portTradesCount").textContent = `${res.total_trades} угод у кошику (${res.portfolio_assets.join(', ')})`;

    const evSign = res.expected_value_pct >= 0 ? "+" : "";
    document.getElementById("portEV").textContent = `${evSign}${res.expected_value_pct}%`;

    document.getElementById("portSharpe").textContent = `${res.sharpe_ratio}`;
    document.getElementById("portSortino").textContent = `Sortino: ${res.sortino_ratio}`;

    document.getElementById("portReturn").textContent = `${res.total_return_pct >= 0 ? '+' : ''}${res.total_return_pct}%`;
    document.getElementById("portBhReturn").textContent = `Buy & Hold: ${res.buy_and_hold_return_pct >= 0 ? '+' : ''}${res.buy_and_hold_return_pct}%`;

    document.getElementById("portMaxDd").textContent = `-${res.max_drawdown_pct}%`;

    renderPortfolioEquityChart(res.equity_curve);
}

function renderPortfolioEquityChart(curve) {
    const ctx = document.getElementById("portfolioEquityChart").getContext("2d");
    if (portfolioEquityChartInstance) {
        portfolioEquityChartInstance.destroy();
    }

    const labels = curve.map(c => c.date);
    const strategyEq = curve.map(c => c.strategy_equity);
    const bhEq = curve.map(c => c.buy_hold_equity);

    portfolioEquityChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Диверсифікований Портфельний Ансамбль",
                    data: strategyEq,
                    borderColor: "#ffffff",
                    backgroundColor: "rgba(255, 255, 255, 0.08)",
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.1,
                    fill: true
                },
                {
                    label: "Портфельний Buy & Hold Benchmark",
                    data: bhEq,
                    borderColor: "#71717a",
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: { labels: { color: "#fafafa", font: { family: "SF Mono, monospace", size: 11 } } },
                tooltip: {
                    backgroundColor: "#18181b",
                    titleColor: "#fafafa",
                    bodyColor: "#a1a1aa",
                    borderColor: "#27272a",
                    borderWidth: 1,
                    titleFont: { family: "SF Mono, monospace" },
                    bodyFont: { family: "SF Mono, monospace" }
                }
            },
            scales: {
                x: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", maxTicksLimit: 12, font: { family: "SF Mono, monospace", size: 10 } } },
                y: { grid: { color: "#1f1f23" }, ticks: { color: "#71717a", font: { family: "SF Mono, monospace", size: 10 } } }
            }
        }
    });
}

function exportMfCsv() {
    if (!lastMfResult || !lastMfResult.predictions) {
        showAlert("Спочатку виконайте бектест", true);
        return;
    }

    const rows = [
        ["Window", "Train_Start", "Train_End", "Test_Start", "Test_End", "Predicted_Direction", "Position_Size", "Exit_Reason", "Price_Start", "Price_End", "Actual_Return_Pct", "Is_Correct", "Strategy_Return_Pct", "Equity_After"]
    ];

    lastMfResult.predictions.forEach(p => {
        rows.push([
            p.window_index,
            p.train_start,
            p.train_end,
            p.test_start,
            p.test_end,
            p.predicted_direction,
            p.position_size,
            `"${(p.exit_reason || '').replace(/"/g, '""')}"`,
            p.price_start,
            p.price_end,
            p.actual_return_pct,
            p.is_correct === null ? "NEUTRAL" : (p.is_correct ? "CORRECT" : "INCORRECT"),
            p.strategy_return_pct,
            p.equity_after
        ]);
    });

    const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `walk_forward_with_protective_barriers.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Tab 5: Run Custom Backtest
async function runCustomBacktest() {
    const ticker = document.getElementById("customTickerSelect").value;
    const startDate = document.getElementById("customStartDate").value;
    const endDate = document.getElementById("customEndDate").value;
    const trainBars = parseInt(document.getElementById("customTrainBars").value) || 60;
    const predictBars = parseInt(document.getElementById("customPredictBars").value) || 15;
    const stepBars = parseInt(document.getElementById("customStepBars").value) || 15;

    const conditionUp = document.getElementById("conditionUp").value.trim();
    const conditionDown = document.getElementById("conditionDown").value.trim();

    if (!ticker) {
        showAlert("Оберіть збережену компанію", true);
        return;
    }

    if (!conditionUp && !conditionDown) {
        showAlert("Введіть хоча б одну умову", true);
        return;
    }

    const btn = document.getElementById("btnRunCustomBacktest");
    const originalText = btn.textContent;
    btn.textContent = "Обчислення...";
    btn.disabled = true;

    try {
        const res = await fetch("/api/run-backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker,
                start_date: startDate,
                end_date: endDate,
                train_bars: trainBars,
                predict_bars: predictBars,
                step_bars: stepBars,
                condition_up: conditionUp,
                condition_down: conditionDown,
                sizing_mode: "constant"
            })
        });

        const result = await res.json();

        if (!result.success) {
            showAlert(result.error || "Помилка бектесту", true);
            return;
        }

        showAlert(`Бектест завершено: ${result.total_windows} вікон, точність ${result.accuracy_pct}%, дохідність ${result.total_return_pct}%`);
    } catch (err) {
        showAlert("Помилка: " + err.message, true);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}
