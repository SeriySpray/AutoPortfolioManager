import os
import io
from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
from data_manager import DataManager
from backtester import WalkForwardBacktester, PortfolioWalkForwardBacktester
from math_engine import MathEngine

app = Flask(__name__)
data_mgr = DataManager()


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@app.route("/")

def index():
    return render_template("index.html")


@app.route("/api/math-variables", methods=["GET"])
def get_math_variables():
    """Returns available quantitative mathematical variables for building formulas."""
    return jsonify(MathEngine.AVAILABLE_VARIABLES)


@app.route("/api/cached-tickers", methods=["GET"])
def get_cached_tickers():
    """Returns list of downloaded tickers with date ranges. Auto-seeds if empty."""
    tickers = data_mgr.list_cached_tickers()
    if not tickers:
        data_mgr.bootstrap_core_universe()
        tickers = data_mgr.list_cached_tickers()
    return jsonify(tickers)



@app.route("/api/download-all", methods=["POST"])
def download_all():
    """Downloads all-time historical data for a ticker with auto-adjust."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    if not ticker:
        return jsonify({"success": False, "message": "Введіть тікер"}), 400

    success, message, count = data_mgr.download_all_history(ticker)
    return jsonify({
        "success": success,
        "message": message,
        "count": count
    })


@app.route("/api/delete-ticker", methods=["POST"])
def delete_ticker():
    """Deletes cached data for a ticker."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    if not ticker:
        return jsonify({"success": False, "message": "Введіть тікер"}), 400

    success = data_mgr.delete_cached_ticker(ticker)
    return jsonify({"success": success, "message": f"Кеш для {ticker} видалено" if success else "Файл не знайдено"})


@app.route("/api/get-slice", methods=["POST"])
def get_slice():
    """Retrieves a specific time slice for a ticker."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    start_date = data.get("start_date") or None
    end_date = data.get("end_date") or None

    if not ticker:
        return jsonify({"success": False, "message": "Введіть тікер"}), 400

    df = data_mgr.get_data_slice(ticker, start_date, end_date)
    if df is None or df.empty:
        return jsonify({"success": False, "message": "Дані не знайдено за вказаний період"}), 404

    df["DateStr"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_50"] = df["Close"].rolling(50).mean()
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": row["DateStr"],
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
            "sma_20": round(float(row["SMA_20"]), 2) if pd.notna(row["SMA_20"]) else None,
            "sma_50": round(float(row["SMA_50"]), 2) if pd.notna(row["SMA_50"]) else None
        })

    return jsonify({
        "success": True,
        "ticker": ticker.upper(),
        "count": len(records),
        "start_date": records[0]["date"] if records else None,
        "end_date": records[-1]["date"] if records else None,
        "data": records
    })


@app.route("/api/export-slice-csv", methods=["GET"])
def export_slice_csv():
    """Exports a specific time slice directly to a downloadable CSV file."""
    ticker = request.args.get("ticker", "").strip()
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None

    if not ticker:
        return Response("Помилка: тікер не вказано", status=400)

    df = data_mgr.get_data_slice(ticker, start_date, end_date)
    if df is None or df.empty:
        return Response("Дані не знайдено", status=404)

    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    filename = f"{ticker.upper()}_{start_date or 'ALL'}_to_{end_date or 'ALL'}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@app.route("/api/run-backtest", methods=["POST"])
def run_backtest():
    """Executes quantitative walk-forward backtest for custom formulas or rules."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    start_date = data.get("start_date") or None
    end_date = data.get("end_date") or None
    
    try:
        train_bars = int(data.get("train_bars", 60))
        predict_bars = int(data.get("predict_bars", 15))
        step_bars = int(data.get("step_bars", 15))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Некоректні числові параметри вікон"}), 400

    condition_up = data.get("condition_up", "").strip()
    condition_down = data.get("condition_down", "").strip()
    sizing_mode = data.get("sizing_mode", "constant").strip().lower()
    atr_sl = float(data.get("atr_stop_loss_mult", 0.0))
    atr_tp = float(data.get("atr_take_profit_mult", 0.0))

    if not ticker:
        return jsonify({"success": False, "error": "Вкажіть тікер"}), 400

    df = data_mgr.get_data_slice(ticker, start_date, end_date)
    if df is None or df.empty:
        return jsonify({"success": False, "error": f"Дані для {ticker} за вказаний період відсутні."}), 404

    backtester = WalkForwardBacktester(df)
    results = backtester.run_walk_forward(
        train_bars=train_bars,
        predict_bars=predict_bars,
        step_bars=step_bars,
        condition_up=condition_up,
        condition_down=condition_down,
        sizing_mode=sizing_mode,
        atr_stop_loss_mult=atr_sl,
        atr_take_profit_mult=atr_tp
    )

    return jsonify(results)


@app.route("/api/run-multi-factor-backtest", methods=["POST"])
def run_multi_factor_backtest():
    """Executes Multi-Parameter Quantitative Factor Walk-Forward backtest with ATR barriers and circuit breakers."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    start_date = data.get("start_date") or None
    end_date = data.get("end_date") or None
    
    try:
        train_bars = int(data.get("train_bars", 60))
        predict_bars = int(data.get("predict_bars", 15))
        step_bars = int(data.get("step_bars", 15))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Некоректні числові параметри вікон"}), 400

    w_mr = float(data.get("w_mean_revert", 0.15))
    w_mom = float(data.get("w_momentum", 0.60))
    w_ar1 = float(data.get("w_ar1", 0.15))
    w_curv = float(data.get("w_curv", 0.10))
    thresh_up = float(data.get("threshold_up", 0.18))
    thresh_down = float(data.get("threshold_down", -0.18))
    sizing_mode = data.get("sizing_mode", "kelly").strip().lower()
    
    atr_sl = float(data.get("atr_stop_loss_mult", 2.0))
    atr_tp = float(data.get("atr_take_profit_mult", 0.0))
    use_chop = bool(data.get("use_chop_filter", True))
    use_v_breaker = bool(data.get("use_v_reversal_breaker", True))

    if not ticker:
        return jsonify({"success": False, "error": "Вкажіть тікер"}), 400

    df = data_mgr.get_data_slice(ticker, start_date, end_date)
    if df is None or df.empty:
        return jsonify({"success": False, "error": f"Дані для {ticker} відсутні."}), 404

    backtester = WalkForwardBacktester(df)
    results = backtester.run_multi_factor_walk_forward(
        train_bars=train_bars,
        predict_bars=predict_bars,
        step_bars=step_bars,
        w_mean_revert=w_mr,
        w_momentum=w_mom,
        w_ar1=w_ar1,
        w_curv=w_curv,
        threshold_up=thresh_up,
        threshold_down=thresh_down,
        sizing_mode=sizing_mode,
        atr_stop_loss_mult=atr_sl,
        atr_take_profit_mult=atr_tp,
        use_chop_filter=use_chop,
        use_v_reversal_breaker=use_v_breaker
    )

    return jsonify(results)


@app.route("/api/run-portfolio-backtest", methods=["POST"])
def run_portfolio_backtest():
    """Executes Multi-Asset Ensemble Portfolio Walk-Forward backtest."""
    data = request.get_json() or {}
    tickers = data.get("tickers", ["AAPL", "NVDA", "MSFT", "AMZN", "QQQ"])
    train_bars = int(data.get("train_bars", 60))
    predict_bars = int(data.get("predict_bars", 15))
    step_bars = int(data.get("step_bars", 15))
    
    w_mr = float(data.get("w_mean_revert", 0.15))
    w_mom = float(data.get("w_momentum", 0.60))
    w_ar1 = float(data.get("w_ar1", 0.15))
    w_curv = float(data.get("w_curv", 0.10))
    thresh_up = float(data.get("threshold_up", 0.18))
    thresh_down = float(data.get("threshold_down", -0.18))
    sizing_mode = data.get("sizing_mode", "kelly").strip().lower()
    atr_sl = float(data.get("atr_stop_loss_mult", 2.0))

    data_dict = {}
    for t in tickers:
        df = data_mgr.get_data_slice(t)
        if df is not None and not df.empty:
            data_dict[t] = df

    if not data_dict:
        return jsonify({"success": False, "error": "Не вдалося отримати дані для вказаних активів"}), 400

    res = PortfolioWalkForwardBacktester.run_portfolio_walk_forward(
        data_dict=data_dict,
        train_bars=train_bars,
        predict_bars=predict_bars,
        step_bars=step_bars,
        w_mean_revert=w_mr,
        w_momentum=w_mom,
        w_ar1=w_ar1,
        w_curv=w_curv,
        threshold_up=thresh_up,
        threshold_down=thresh_down,
        sizing_mode=sizing_mode,
        atr_stop_loss_mult=atr_sl
    )

    return jsonify(res)


@app.route("/api/generate-live-forecast", methods=["POST"])
def generate_live_forecast():
    """Generates the latest Out-of-Sample Blind Forecast on the most recent data with ATR Stop Loss."""
    data = request.get_json() or {}
    ticker = data.get("ticker", "").strip()
    train_bars = int(data.get("train_bars", 60))
    predict_bars = int(data.get("predict_bars", 15))
    
    w_mr = float(data.get("w_mean_revert", 0.15))
    w_mom = float(data.get("w_momentum", 0.60))
    w_ar1 = float(data.get("w_ar1", 0.15))
    w_curv = float(data.get("w_curv", 0.10))
    thresh_up = float(data.get("threshold_up", 0.18))
    thresh_down = float(data.get("threshold_down", -0.18))
    sizing_mode = data.get("sizing_mode", "kelly").strip().lower()
    atr_sl = float(data.get("atr_stop_loss_mult", 2.0))

    if not ticker:
        return jsonify({"success": False, "error": "Вкажіть тікер"}), 400

    df = data_mgr.get_data_slice(ticker)
    if df is None or df.empty:
        return jsonify({"success": False, "error": f"Дані для {ticker} відсутні."}), 404

    backtester = WalkForwardBacktester(df)
    forecast = backtester.generate_latest_blind_forecast(
        train_bars=train_bars,
        predict_bars=predict_bars,
        w_mean_revert=w_mr,
        w_momentum=w_mom,
        w_ar1=w_ar1,
        w_curv=w_curv,
        threshold_up=thresh_up,
        threshold_down=thresh_down,
        sizing_mode=sizing_mode,
        atr_stop_loss_mult=atr_sl
    )

    return jsonify(forecast)


@app.route("/api/live/status", methods=["GET"])
def get_live_status():
    """Returns real-time state of the Live Quant Daemon, open positions, scanner, and trade history."""
    import sqlite3
    db_path = "live_portfolio.db"
    
    # Tracked tickers list
    tracked_tickers = ["AAPL", "NVDA", "MSFT", "AMZN", "TSLA", "QQQ", "META", "GOOGL"]

    if not os.path.exists(db_path):
        return jsonify({
            "status": "INITIALIZING",
            "last_heartbeat": None,
            "active_positions_count": 0,
            "unrealized_total_pnl_pct": 0.0,
            "monitored_tickers": tracked_tickers,
            "positions": [],
            "scanner": [],
            "history": []
        })

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Status & Heartbeat
        cur.execute("SELECT value, updated_at FROM live_system_status WHERE key='status'")
        status_row = cur.fetchone()
        status = status_row[0] if status_row else "IDLE"

        cur.execute("SELECT value, updated_at FROM live_system_status WHERE key='last_heartbeat'")
        hb_row = cur.fetchone()
        last_heartbeat = hb_row[0] if hb_row else None

        # Open Positions with live price calculation
        cur.execute("SELECT ticker, direction, size, entry_price, entry_date, atr_sl_price, target_price, composite_score, unrealized_pnl_pct, updated_at FROM positions")
        pos_rows = cur.fetchall()
        positions = []
        tot_unrealized_pnl = 0.0

        for r in pos_rows:
            ticker = r[0]
            direction = r[1]
            size = r[2]
            entry_p = r[3]
            
            # Fetch latest close price from data cache
            df = data_mgr.get_data_slice(ticker)
            curr_p = float(df["Close"].iloc[-1]) if (df is not None and not df.empty) else entry_p

            pnl_pct = ((curr_p - entry_p) / entry_p * 100.0) if direction == 1 else ((entry_p - curr_p) / entry_p * 100.0)
            sized_pnl_pct = round(pnl_pct * abs(size), 2)
            tot_unrealized_pnl += sized_pnl_pct

            positions.append({
                "ticker": ticker,
                "direction": direction,
                "direction_label": "BUY / LONG" if direction == 1 else ("SELL / SHORT" if direction == -1 else "FLAT"),
                "size": size,
                "entry_price": round(entry_p, 2),
                "current_price": round(curr_p, 2),
                "entry_date": r[4],
                "atr_sl_price": round(r[5], 2) if r[5] else None,
                "target_price": round(r[6], 2) if r[6] else None,
                "composite_score": round(r[7], 3) if r[7] else 0.0,
                "unrealized_pnl_pct": sized_pnl_pct,
                "updated_at": r[9]
            })

        # Scanner metrics across monitored assets
        scanner_list = []
        for t in tracked_tickers:
            df = data_mgr.get_data_slice(t)
            if df is not None and len(df) >= 30:
                eval_res = MathEngine.evaluate_multi_factor_window(
                    train_df=df.iloc[-60:],
                    w_mean_revert=0.15,
                    w_momentum=0.60,
                    w_ar1=0.15,
                    w_curv=0.10,
                    threshold_up=0.18,
                    threshold_down=-0.18,
                    sizing_mode="kelly"
                )
                m = eval_res.get("metrics", {})
                is_held = any(p["ticker"] == t for p in positions)
                scanner_list.append({
                    "ticker": t,
                    "price": round(float(df["Close"].iloc[-1]), 2),
                    "composite_score": eval_res.get("composite_score", 0.0),
                    "signal": "LONG" if eval_res.get("direction") == 1 else ("SHORT" if eval_res.get("direction") == -1 else "NEUTRAL"),
                    "hurst": m.get("hurst", 0.5),
                    "slope": m.get("slope", 0.0),
                    "atr_pct": m.get("atr_pct", 0.0),
                    "chop_index": m.get("chop_index", 50.0),
                    "status": "У ПОЗИЦІЇ" if is_held else "МОНІТОРИНГ"
                })

        # History (Last 50 closed trades)
        cur.execute("SELECT ticker, direction, size, entry_price, exit_price, entry_date, exit_date, pnl_pct, exit_reason, created_at FROM trade_history ORDER BY id DESC LIMIT 50")
        hist_rows = cur.fetchall()
        history = []
        for r in hist_rows:
            history.append({
                "ticker": r[0],
                "direction": "LONG" if r[1] == 1 else "SHORT",
                "size": r[2],
                "entry_price": round(r[3], 2),
                "exit_price": round(r[4], 2),
                "entry_date": r[5],
                "exit_date": r[6],
                "pnl_pct": round(r[7], 2),
                "exit_reason": r[8],
                "created_at": r[9]
            })

        conn.close()
        return jsonify({
            "status": status,
            "last_heartbeat": last_heartbeat,
            "active_positions_count": len(positions),
            "unrealized_total_pnl_pct": round(tot_unrealized_pnl, 2),
            "monitored_tickers": tracked_tickers,
            "positions": positions,
            "scanner": scanner_list,
            "history": history
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/live/trigger-tick", methods=["POST"])
def trigger_live_tick():
    """Manually triggers an immediate live market tick cycle."""
    try:
        from live_trader_daemon import LiveQuantDaemon
        daemon = LiveQuantDaemon(poll_interval_seconds=60)
        daemon.update_system_status("RUNNING", 0)
        for t in daemon.tickers:
            daemon.process_ticker_live_tick(t)
        return jsonify({"success": True, "message": "Live такт успішно виконано по всіх активах"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



if __name__ == "__main__":
    port = int(os.getenv("PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=True)


