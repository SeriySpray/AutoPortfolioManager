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
    banner_text.append("⚡ AutoPortfolioManager — Quant Sharpe Screener ⚡\n", style="bold cyan")
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
    Renders a styled Rich table of stock rankings.
    """
    if df.empty:
        console.print("[red]Немає даних для відображення.[/red]")
        return

    subset = df.tail(top_n).iloc[::-1] if bottom else df.head(top_n)
    title = f"🔻 Найбільш ризиковані активи S&P 500 (BOTTOM {top_n})" if bottom else f"🏆 ТОП-{top_n} Активів S&P 500 за SSQ-Sharpe"

    table = Table(
        title=title,
        title_style="bold bright_white",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim blue",
        expand=True,
    )

    table.add_column("#", justify="right", style="bold white", width=4)
    table.add_column("Тікер", justify="left", style="bold yellow", width=8)
    table.add_column("Компанія", justify="left", style="white", min_width=18, max_width=25)
    table.add_column("Сектор", justify="left", style="dim cyan", min_width=14, max_width=22)
    table.add_column("Роки", justify="right", style="dim white", width=5)
    table.add_column("CAGR %", justify="right", width=9)
    table.add_column("Max DD %", justify="right", width=9)
    table.add_column("Classic SR", justify="right", style="dim", width=10)
    table.add_column("Sortino", justify="right", style="dim", width=9)
    table.add_column("SSQ-Sharpe", justify="right", style="bold bright_green", width=11)
    table.add_column("Δ Ранг", justify="center", width=8)

    for _, row in subset.iterrows():
        rank = str(int(row["ssq_rank"]))
        ticker = str(row["ticker"])
        name = str(row["name"])[:25]
        sector = str(row["sector"])[:22]
        years = f"{row['total_years']:.0f}"

        # CAGR formatting
        cagr = row["cagr"] * 100.0
        cagr_str = f"{cagr:+.1f}%"
        cagr_styled = f"[green]{cagr_str}[/green]" if cagr >= 0 else f"[red]{cagr_str}[/red]"

        # Max Drawdown formatting
        mdd = row["max_drawdown"] * 100.0
        mdd_styled = f"[red]{mdd:.1f}%[/red]"

        classic_sr = f"{row['classic_sharpe']:.2f}"
        sortino = f"{row['sortino_ratio']:.2f}"
        ssq = f"{row['ssq_sharpe']:.2f}"

        # Rank delta formatting
        delta = int(row["rank_delta"])
        if delta > 0:
            delta_str = f"[bright_green]▲+{delta}[/bright_green]"
        elif delta < 0:
            delta_str = f"[bright_red]▼{delta}[/bright_red]"
        else:
            delta_str = "[dim]=[/dim]"

        table.add_row(
            rank,
            ticker,
            name,
            sector,
            years,
            cagr_styled,
            mdd_styled,
            classic_sr,
            sortino,
            ssq,
            delta_str,
        )

    console.print(table)
    console.print(
        "[dim]Пояснення: [bold bright_green]SSQ-Sharpe[/bold bright_green] враховує лише падіння, штрафує жирні хвости та глибину дна. "
        "[bright_green]▲[/bright_green]/[bright_red]▼[/bright_red] показує, на скільки позицій актив піднявся/опустився відносно класичного Шарпа.[/dim]\n"
    )


def render_ticker_card(df: pd.DataFrame, ticker: str) -> None:
    """
    Renders a detailed breakdown card for a specific stock ticker.
    """
    ticker_clean = ticker.upper().strip().replace(".", "-")
    match = df[df["ticker"] == ticker_clean]

    if match.empty:
        console.print(f"[bold red]❌ Тікер '{ticker_clean}' не знайдено у списку активів S&P 500.[/bold red]\n")
        return

    row = match.iloc[0]

    content = Text()

    # 1. General Header
    content.append(f"📌 {row['ticker']} — {row['name']}\n", style="bold bright_yellow")
    content.append(f"Сектор: {row['sector']}  |  Історичний період: {row['start_date']} — {row['end_date']} ({row['total_years']} років, {row['total_days']} торгових днів)\n", style="dim white")
    content.append(f"Ціни: Початкова = ${row['start_price']:.2f}  |  Кінцева = ${row['end_price']:.2f}\n\n", style="white")

    # 2. Key Returns & Risk
    cagr = row["cagr"] * 100.0
    vol = row["annual_vol"] * 100.0
    down_vol = row["downside_dev"] * 100.0
    mdd = row["max_drawdown"] * 100.0

    content.append("📈 Базова прибутковість та волатильність:\n", style="bold cyan")
    content.append(f"  • Середньорічний дохід (CAGR):   ", style="white")
    content.append(f"{cagr:+.2f}%\n", style="bold green" if cagr >= 0 else "bold red")
    content.append(f"  • Загальна волатильність (σ):     {vol:.2f}% річних (включає як ріст, так і падіння)\n", style="white")
    content.append(f"  • Downside волатильність (σ_down): {down_vol:.2f}% річних (враховує виключно спади)\n", style="green")
    content.append(f"  • Максимальне просідання (Max DD): {mdd:.2f}%\n\n", style="red")

    # 3. Four Risk Factors
    content.append("🔬 Складові адаптованої квант-формули ризику:\n", style="bold magenta")

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

    content.append("⚖️ Порівняння коефіцієнтів та ранг у S&P 500:\n", style="bold bright_white")
    content.append(f"  • Classic Sharpe Ratio:  {sr_classic:.2f}  (Ранг у S&P 500: #{rank_classic})\n", style="dim white")
    content.append(f"  • Sortino Ratio:         {sr_sortino:.2f}\n", style="dim white")
    content.append(f"  • SSQ-Sharpe (Адаптований): {sr_ssq:.2f}  (Ранг у S&P 500: #{rank_ssq})\n", style="bold bright_green")

    if delta > 10:
        content.append(f"\n💡 Висновок: Акція суттєво піднялася в рейтингу (на +{delta} позицій) у порівнянні з класичним Шарпом, "
                       "оскільки її волатильність здебільшого висхідна, а просідання не були затяжними.", style="bright_green")
    elif delta < -10:
        content.append(f"\n⚠️ Висновок: Акція опустилася в рейтингу (на {delta} позицій), тому що класичний Шарп "
                       "маскував небезпечні жирні ліві хвости та глибокі затяжні просідання.", style="bright_red")
    else:
        content.append("\nℹ️ Висновок: Позиція активу стабільна, профіль ризику відповідає стандартним очікуванням.", style="cyan")

    panel = Panel(
        content,
        title=f"[bold bright_cyan]Детальний аналіз активу: {row['ticker']}[/bold bright_cyan]",
        border_style="green",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
