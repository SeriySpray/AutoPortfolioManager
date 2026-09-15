"""
AutoPortfolioManager — S&P 500 Quant Sharpe Screener.
Main CLI entry point with interactive terminal menu and command-line arguments.
"""

import argparse
import os
import sys
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# Ensure local packages are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.sp500_loader import clear_cache, has_cached_data, load_sp500_data
from core.quant_metrics import compute_all_sp500_metrics
from ui.terminal_view import console, print_banner, render_rankings_table, render_ticker_card


def load_and_calculate_workflow(
    force_refresh: bool = False,
    rf_annual: float = 0.04,
) -> pd.DataFrame:
    """
    Orchestrates downloading/loading of data and computing quantitative metrics with progress indicators.
    """
    is_cached = has_cached_data() and not force_refresh

    if is_cached:
        with console.status("[bold cyan]Завантаження кешованих котирувань S&P 500 (Parquet)...[/bold cyan]", spinner="dots"):
            prices_df, meta = load_sp500_data(force_refresh=False)
        console.print(f"[green]✓[/green] Зчитано з кешу: [bold]{len(prices_df.columns)}[/bold] активів, історія з {prices_df.index[0].strftime('%Y-%m-%d')} по {prices_df.index[-1].strftime('%Y-%m-%d')}.")
    else:
        console.print("[yellow]Завантаження максимальної доступної історії для всіх активів S&P 500 з Yahoo Finance...[/yellow]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="bright_green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Завантаження активів...", total=503)

            def update_progress(current: int, total: int, msg: str):
                progress.update(task, completed=current, total=total, description=msg)

            prices_df, meta = load_sp500_data(force_refresh=True, progress_callback=update_progress)

        console.print(f"[green]✓[/green] Успішно завантажено та збережено в Parquet: [bold]{len(prices_df.columns)}[/bold] активів.")

    with console.status("[bold magenta]Розрахунок адаптованого показника SSQ-Sharpe для кожного активу...[/bold magenta]", spinner="line"):
        df_results = compute_all_sp500_metrics(prices_df, meta, rf_annual=rf_annual)

    console.print(f"[bright_green]✓ Розрахунок завершено для {len(df_results)} компаній.[/bright_green]\n")
    return df_results


def interactive_menu_loop(df_results: pd.DataFrame, rf_annual: float = 0.04) -> None:
    """
    Interactive terminal command loop.
    """
    while True:
        console.print("[bold cyan]Оберіть дію:[/bold cyan]")
        console.print("  [bold green]1[/bold green] — Показати [bold]ТОП-25 лідерів[/bold] за SSQ-Sharpe")
        console.print("  [bold yellow]2[/bold yellow] — Показати [bold]25 аутсайдерів[/bold] (найбільший хвостовий ризик)")
        console.print("  [bold cyan]3[/bold cyan] — [bold]Детальний аналіз[/bold] конкретної акції (ввести тікер)")
        console.print("  [bold magenta]4[/bold magenta] — [bold]Експортувати[/bold] результати всіх 500+ активів у CSV")
        console.print("  [bold red]5[/bold red] — [bold]Перезапустити аналіз[/bold] (скинути кеш та завантажити наново)")
        console.print("  [bold white]0[/bold white] (або q) — [dim]Вихід[/dim]\n")

        choice = console.input("[bold yellow]Ваш вибір > [/bold yellow]").strip().lower()

        if choice in ("0", "q", "quit", "exit"):
            console.print("[dim]Роботу завершено.[/dim]")
            break
        elif choice == "1":
            render_rankings_table(df_results, top_n=25, bottom=False)
        elif choice == "2":
            render_rankings_table(df_results, top_n=25, bottom=True)
        elif choice == "3":
            sym = console.input("[bold white]Введіть тікер акції (наприклад, NVDA, AAPL, MSFT, TSLA) > [/bold white]").strip()
            if sym:
                render_ticker_card(df_results, sym)
        elif choice == "4":
            filename = "results_sp500_sharpe.csv"
            df_results.to_csv(filename, index=False)
            console.print(f"[bold bright_green]✓ Результати збережено у файл: [underline]{filename}[/underline][/bold bright_green]\n")
        elif choice == "5":
            confirm = console.input("[bold red]Ви дійсно бажаєте видалити локальний кеш та завантажити котирування наново? (y/n) > [/bold red]").strip().lower()
            if confirm in ("y", "yes", "т", "так"):
                clear_cache()
                df_results = load_and_calculate_workflow(force_refresh=True, rf_annual=rf_annual)
                render_rankings_table(df_results, top_n=25, bottom=False)
        else:
            console.print("[red]Невідома команда. Спробуйте ще раз.[/red]\n")


def main():
    parser = argparse.ArgumentParser(
        description="AutoPortfolioManager — S&P 500 Quant Sharpe Screener with Single-Stock Adaptation"
    )
    parser.add_argument(
        "-r", "--refresh",
        action="store_true",
        help="Примусово очистити кеш і перезавантажити максимальну історію з Yahoo Finance"
    )
    parser.add_argument(
        "-t", "--ticker",
        type=str,
        help="Відкрити детальний звіт для одного конкретного тікера (наприклад: NVDA)"
    )
    parser.add_argument(
        "-n", "--top",
        type=int,
        default=25,
        help="Кількість топових активів для відображення (за замовчуванням: 25)"
    )
    parser.add_argument(
        "-e", "--export",
        type=str,
        help="Експортувати повні розрахунки у вказаний CSV файл (наприклад: sp500.csv)"
    )
    parser.add_argument(
        "--rf",
        type=float,
        default=0.04,
        help="Безризикова річна ставка (за замовчуванням: 0.04 = 4.0%%)"
    )

    args = parser.parse_args()

    print_banner()

    df_results = load_and_calculate_workflow(force_refresh=args.refresh, rf_annual=args.rf)

    if args.export:
        df_results.to_csv(args.export, index=False)
        console.print(f"[bold green]✓ Дані експортовано у: {args.export}[/bold green]")

    if args.ticker:
        render_ticker_card(df_results, args.ticker)
        return

    # Render initial top table
    render_rankings_table(df_results, top_n=args.top, bottom=False)

    # If no specific non-interactive flags, enter interactive mode
    if len(sys.argv) == 1 or args.refresh:
        interactive_menu_loop(df_results, rf_annual=args.rf)


if __name__ == "__main__":
    main()
