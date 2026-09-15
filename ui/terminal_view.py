"""
Terminal User Interface using Rich for AutoPortfolioManager.
Displays S&P 500 rankings, comparisons, progress bars, and deep-dive ticker cards.
"""

from typing import Optional
import pandas as pd
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def print_banner() -> None:
    """Print the application banner and methodology explanation."""
    banner_text = Text()
    banner_text.append("AutoPortfolioManager — Quant Sharpe Screener\n", style="bold cyan")
    banner_text.append("Single-Stock Quant Sharpe (SSQ-Sharpe) for S&P 500\n\n", style="bold white")
    banner_text.append("Formula: ", style="bold yellow")
    banner_text.append("SSQ-Sharpe = E(R - Rf) / [ σ_down,Lo × Ψ_tail × Φ_drawdown ]\n", style="italic green")
    banner_text.append("Components: Downside Volatility + Lo (2002) Autocorrelation + Cornish-Fisher Tails + Ulcer Drawdown", style="dim white")

    panel = Panel(
        Align.center(banner_text),
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def render_rankings_table(df: pd.DataFrame, top_n: int = 25, bottom: bool = False) -> None:
    """
    Renders a styled Rich table of stock rankings formatted cleanly for standard terminals.
    Guarantees that Sortino, SSQ-SR, and Delta columns are never clipped or wrapped.
    """
    if df.empty:
        console.print("[red]Немає даних для відображення.[/red]")
        return

    subset = df.tail(top_n).iloc[::-1] if bottom else df.head(top_n)
    title = f"Найбільш ризиковані активи S&P 500 (BOTTOM {top_n})" if bottom else f"ТОП-{top_n} Активів S&P 500 за SSQ-Sharpe"

    table = Table(
        title=title,
        title_style="bold bright_white",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim blue",
        padding=(0, 0),
        pad_edge=False,
    )

    table.add_column(" # ", justify="right", style="bold white")
    table.add_column(" Тікер ", justify="left", style="bold yellow")
    table.add_column(" Компанія ", justify="left", style="white", max_width=13, no_wrap=True)
    table.add_column(" CAGR ", justify="right")
    table.add_column(" MaxDD ", justify="right")
    table.add_column(" Sharpe ", justify="right", style="dim")
    table.add_column(" Sortino ", justify="right", style="dim")
    table.add_column(" SSQ-SR ", justify="right", style="bold bright_green")
    table.add_column(" Δ ", justify="center")

    for _, row in subset.iterrows():
        rank = str(int(row["ssq_rank"]))
        ticker = str(row["ticker"])
        name = str(row["name"])[:13]

        # CAGR formatting
        cagr = row["cagr"] * 100.0
        cagr_str = f"{cagr:+.1f}%"
        cagr_styled = f"[green]{cagr_str:>7}[/green]" if cagr >= 0 else f"[red]{cagr_str:>7}[/red]"

        # Max Drawdown formatting
        mdd = row["max_drawdown"] * 100.0
        mdd_styled = f"[red]{mdd:>6.1f}%[/red]"

        classic_sr = f"{row['classic_sharpe']:>6.2f}"
        sortino = f"{row['sortino_ratio']:>7.2f}"
        ssq = f"{row['ssq_sharpe']:>7.2f}"

        # Rank delta formatting
        delta = int(row["rank_delta"])
        if delta > 0:
            delta_str = f"[bright_green]+{delta}[/bright_green]"
        elif delta < 0:
            delta_str = f"[bright_red]{delta}[/bright_red]"
        else:
            delta_str = "[dim]=[/dim]"

        table.add_row(
            f" {rank} ",
            f" {ticker} ",
            f" {name} ",
            f" {cagr_styled} ",
            f" {mdd_styled} ",
            f" {classic_sr} ",
            f" {sortino} ",
            f" {ssq} ",
            f" {delta_str} ",
        )

    console.print(table)
    console.print(
        "[dim]Пояснення: [bold bright_green]SSQ-SR[/bold bright_green] — комбінований показник ризику (Downside + Lo + Tails + Drawdown). "
        "[bold]Δ[/bold] — зсув позиції відносно класичного Шарпа.[/dim]\n"
    )


def render_ticker_card(df: pd.DataFrame, ticker: str) -> None:
    """
    Renders a detailed breakdown card for a specific stock ticker.
    """
    ticker_clean = ticker.upper().strip().replace(".", "-")
    match = df[df["ticker"] == ticker_clean]

    if match.empty:
        console.print(f"[bold red][Помилка] Тікер '{ticker_clean}' не знайдено у списку активів S&P 500.[/bold red]\n")
        return

    row = match.iloc[0]

    content = Text()

    # 1. General Header
    content.append(f"{row['ticker']} — {row['name']}\n", style="bold bright_yellow")
    content.append(f"Сектор: {row['sector']}  |  Історичний період: {row['start_date']} — {row['end_date']} ({row['total_years']} років, {row['total_days']} торгових днів)\n", style="dim white")
    content.append(f"Ціни: Початкова = ${row['start_price']:.2f}  |  Кінцева = ${row['end_price']:.2f}\n\n", style="white")

    # 2. Key Returns & Risk
    cagr = row["cagr"] * 100.0
    vol = row["annual_vol"] * 100.0
    down_vol = row["downside_dev"] * 100.0
    mdd = row["max_drawdown"] * 100.0

    content.append("Базова прибутковість та волатильність:\n", style="bold cyan")
    content.append(f"  • Середньорічний дохід (CAGR):   ", style="white")
    content.append(f"{cagr:+.2f}%\n", style="bold green" if cagr >= 0 else "bold red")
    content.append(f"  • Загальна волатильність (σ):     {vol:.2f}% річних (включає як ріст, так і падіння)\n", style="white")
    content.append(f"  • Downside волатильність (σ_down): {down_vol:.2f}% річних (враховує виключно спади)\n", style="green")
    content.append(f"  • Максимальне просідання (Max DD): {mdd:.2f}%\n\n", style="red")

    # 3. Four Risk Factors
    content.append("Складові адаптованої квант-формули ризику:\n", style="bold magenta")

    # Lo Factor
    rho1 = row["autocorr_lag1"]
    lo_mult = row["lo_multiplier"]
    content.append(f"  1. Автокореляція (Andrew Lo):    ", style="white")
    content.append(f"ρ1 = {rho1:+.3f}, множник волатильності = {lo_mult:.3f}x\n", style="bold yellow")
    if rho1 > 0.05:
        content.append("     ↳ Присутня інерція прибутковості (моментум), що збільшує фактичний багатоперіодний ризик.\n", style="dim")
    elif rho1 < -0.05:
        content.append("     ↳ Присутнє повернення до середнього (mean-reversion), шум нівелює ризик.\n", style="dim")
    else:
        content.append("     ↳ Дохідності близькі до незалежних (i.i.d.).\n", style="dim")

    # Tails Factor
    skew = row["skewness"]
    kurt = row["kurtosis"]
    tail_pen = row["tail_penalty"]
    content.append(f"  2. Хвости (Cornish-Fisher):      ", style="white")
    content.append(f"Skew = {skew:+.2f}, Kurtosis = {kurt:.2f}, штрафний множник = {tail_pen:.3f}x\n", style="bold yellow")
    if skew < -0.2:
        content.append("     ↳ Лівосторонній хвіст: акція схильна до раптових глибоких обвалів на новинах.\n", style="dim red")
    if kurt > 4.0:
        content.append("     ↳ Важкі хвости: ймовірність екстремальних стрибків значно вища за нормальну.\n", style="dim yellow")

    # Ulcer Factor
    ui = row["ulcer_index"] * 100.0
    dd_pen = row["drawdown_penalty"]
    content.append(f"  3. Індекс виразки (Ulcer Index):  ", style="white")
    content.append(f"UI = {ui:.2f}%, штраф за дно = {dd_pen:.3f}x\n", style="bold yellow")
    content.append("     ↳ Вимірює не тільки глибину, але й час знаходження акції 'під водою'.\n\n", style="dim")

    # 4. Final Comparison
    sr_classic = row["classic_sharpe"]
    sr_sortino = row["sortino_ratio"]
    sr_ssq = row["ssq_sharpe"]
    rank_ssq = int(row["ssq_rank"])
    rank_classic = int(row["classic_rank"])
    delta = int(row["rank_delta"])

    content.append("Порівняння коефіцієнтів та ранг у S&P 500:\n", style="bold bright_white")
    content.append(f"  • Classic Sharpe Ratio:  {sr_classic:.2f}  (Ранг у S&P 500: #{rank_classic})\n", style="dim white")
    content.append(f"  • Sortino Ratio:         {sr_sortino:.2f}\n", style="dim white")
    content.append(f"  • SSQ-Sharpe (Адаптований): {sr_ssq:.2f}  (Ранг у S&P 500: #{rank_ssq})\n", style="bold bright_green")

    if delta > 10:
        content.append(f"\nВисновок: Акція суттєво піднялася в рейтингу (на +{delta} позицій) у порівнянні з класичним Шарпом, "
                       "оскільки її волатильність здебільшого висхідна, а просідання не були затяжними.", style="bright_green")
    elif delta < -10:
        content.append(f"\nВисновок: Акція опустилася в рейтингу (на {delta} позицій), тому що класичний Шарп "
                       "маскував небезпечні жирні ліві хвости та глибокі затяжні просідання.", style="bright_red")
    else:
        content.append("\nВисновок: Позиція активу стабільна, профіль ризику відповідає стандартним очікуванням.", style="cyan")

    panel = Panel(
        content,
        title=f"[bold bright_cyan]Детальний аналіз активу: {row['ticker']}[/bold bright_cyan]",
        border_style="green",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def render_backtest_summary(results: dict) -> None:
    """
    Renders a comprehensive Rich report of the 1-month leveraged backtest.
    """
    t1 = results["tier_1x"]
    t2 = results["tier_2x"]
    t3 = results["tier_3x"]

    # 1. Main comparison table
    table = Table(
        title=f"Результати бектесту з плечем ({results['start_date']} — {results['end_date']}, {results['total_months']} міс.)",
        title_style="bold bright_white",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim blue",
        pad_edge=False,
        padding=(0, 1),
    )

    table.add_column("Метрика", style="bold white")
    table.add_column("1x (Без плеча)", justify="right", style="white")
    table.add_column("2x (Помірне)", justify="right", style="bold bright_cyan")
    table.add_column("3x (Агресивне)", justify="right", style="bold bright_green")

    def color_stat(val: float, is_pct: bool = True, invert: bool = False) -> str:
        s = f"{val:+.1f}%" if is_pct else f"{val:.2f}"
        if invert:
            return f"[red]{s}[/red]" if val < 0 else f"[green]{s}[/green]"
        return f"[green]{s}[/green]" if val >= 0 else f"[red]{s}[/red]"

    table.add_row(
        "Кумулятивний прибуток",
        color_stat(t1["cum_return"]),
        color_stat(t2["cum_return"]),
        color_stat(t3["cum_return"]),
    )
    table.add_row(
        "Річна дохідність (CAGR)",
        color_stat(t1["cagr"]),
        color_stat(t2["cagr"]),
        color_stat(t3["cagr"]),
    )
    table.add_row(
        "Річна волатильність",
        f"{t1['annual_vol']:.1f}%",
        f"{t2['annual_vol']:.1f}%",
        f"{t3['annual_vol']:.1f}%",
    )
    table.add_row(
        "Максимальна просадка (Max DD)",
        f"[red]{t1['max_drawdown']:.1f}%[/red]",
        f"[red]{t2['max_drawdown']:.1f}%[/red]",
        f"[red]{t3['max_drawdown']:.1f}%[/red]",
    )
    table.add_row(
        "Win Rate (% прибуткових місяців)",
        f"[bold bright_yellow]{t1['win_rate']:.1f}%[/bold bright_yellow]",
        f"[bold bright_yellow]{t2['win_rate']:.1f}%[/bold bright_yellow]",
        f"[bold bright_yellow]{t3['win_rate']:.1f}%[/bold bright_yellow]",
    )
    table.add_row(
        "Реалізований Sharpe",
        f"{t1['sharpe']:.2f}",
        f"{t2['sharpe']:.2f}",
        f"{t3['sharpe']:.2f}",
    )
    table.add_row(
        "Найгірший місяць (Worst Month)",
        f"[red]{t1['worst_month']:+.1f}%[/red]",
        f"[red]{t2['worst_month']:+.1f}%[/red]",
        f"[red]{t3['worst_month']:+.1f}%[/red]",
    )
    table.add_row(
        "Найкращий місяць (Best Month)",
        f"[green]{t1['best_month']:+.1f}%[/green]",
        f"[green]{t2['best_month']:+.1f}%[/green]",
        f"[green]{t3['best_month']:+.1f}%[/green]",
    )

    console.print(table)
    console.print("[dim]Примітка: У розрахунках 2x та 3x враховано вартість брокерського фінансування позики 6.5% річних.[/dim]\n")

    # 2. Stock Leaderboard
    df_stocks = results.get("top_stocks")
    if df_stocks is not None and not df_stocks.empty:
        stock_table = Table(
            title="Найбільш стабільні та вигідні компанії для одномісячного утримання (All-Stars)",
            title_style="bold bright_white",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="dim blue",
            expand=True,
        )

        stock_table.add_column("Тікер", style="bold yellow", width=6)
        stock_table.add_column("Компанія", style="white", no_wrap=True)
        stock_table.add_column("Сектор", style="dim cyan", no_wrap=True)
        stock_table.add_column("Місяців", justify="center", width=9)
        stock_table.add_column("Сер. ріст", justify="right", width=11)
        stock_table.add_column("Win Rate", justify="right", style="bold bright_yellow", width=10)
        stock_table.add_column("Worst Month", justify="right", style="red", width=12)
        stock_table.add_column("Best Month", justify="right", style="green", width=12)

        for _, r in df_stocks.head(10).iterrows():
            avg_ret = r["avg_month_ret"]
            avg_str = f"[green]{avg_ret:+.1f}%[/green]" if avg_ret >= 0 else f"[red]{avg_ret:+.1f}%[/red]"

            stock_table.add_row(
                str(r["ticker"]),
                str(r["name"])[:20],
                str(r["sector"])[:16],
                f"{int(r['times_picked'])}",
                avg_str,
                f"{r['win_rate']:.0f}%",
                f"{r['worst_month']:+.1f}%",
                f"{r['best_month']:+.1f}%",
            )

        console.print(stock_table)
        console.print("[dim]Ці акції найчастіше потрапляли у відбір алгоритму і показували найвищу повторюваність прибутку.[/dim]\n")


def render_current_leveraged_picks(picks_df: pd.DataFrame) -> None:
    """
    Renders the current recommended portfolio for the upcoming 1-month period.
    """
    if picks_df.empty:
        console.print("[red]Не вдалося знайти кандидатів під критерії безпечного плеча.[/red]\n")
        return

    table = Table(
        title="ТОП актуальних акцій на найближчий 1 місяць (Рекомендації для плеча 2x-3x)",
        title_style="bold bright_white",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim green",
        expand=True,
    )

    table.add_column("Тікер", style="bold yellow", width=6)
    table.add_column("Компанія", style="white", min_width=14, max_width=20)
    table.add_column("Ріст 3M", justify="right", width=9)
    table.add_column("Волат.", justify="right", style="white", width=7)
    table.add_column("Max DD", justify="right", style="red", width=8)
    table.add_column("SSQ 3M", justify="right", style="bold bright_green", width=8)
    table.add_column("Плече", justify="center", width=12)
    table.add_column("Stop-Loss", justify="right", style="bold red", width=10)

    for i, (_, r) in enumerate(picks_df.iterrows(), 1):
        ret3 = r["recent_3m_ret"]
        ret_str = f"[green]{ret3:+.1f}%[/green]" if ret3 >= 0 else f"[red]{ret3:+.1f}%[/red]"

        lev_str = r["rec_leverage"]
        if "3x" in lev_str:
            lev_styled = "[bold bright_green]3x Stable[/bold bright_green]"
        else:
            lev_styled = "[bold bright_yellow]2x Medium[/bold bright_yellow]"

        table.add_row(
            str(r["ticker"]),
            str(r["name"])[:20],
            ret_str,
            f"{r['recent_vol']:.1f}%",
            f"{r['recent_max_dd']:.1f}%",
            f"{r['recent_ssq']:.2f}",
            lev_styled,
            f"-{r['stop_loss_pct']:.1f}%",
        )

    console.print(table)
    console.print(
        "[dim]Порада з ризик-менеджменту: Safe Stop-Loss розраховано так, щоб при відповідному плечі ваш загальний збиток на угоду "
        "не перевищував 17-18% капіталу в разі несподіваного розвороту ринку.[/dim]\n"
    )

