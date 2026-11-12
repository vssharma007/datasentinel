"""DataSentinel Command-Line Interface (Typer + Rich)."""

import time
import uuid
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from datasentinel.alerts.email_service import EmailAlertService
from datasentinel.alerts.webhook_service import SlackAlertService
from datasentinel.anomaly.detector import AnomalyDetector
from datasentinel.config.loader import load_config_from_yaml
from datasentinel.config.schema import SentinelConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.core.exceptions import DataSentinelError
from datasentinel.core.types import (
    DriftType,
    RuleResult,
    RunSummary,
    Severity,
    ValidationStatus,
)
from datasentinel.reports.generator import ReportGenerator
from datasentinel.rules.executor import RuleExecutor
from datasentinel.scheduler.runner import ValidationScheduler
from datasentinel.schema.drift import SchemaDriftDetector
from datasentinel.schema.registry import SchemaRegistry
from datasentinel.store.result_store import ResultStore

app = typer.Typer(
    name="datasentinel",
    help="DataSentinel — Automated Data Quality & Pipeline Monitoring Platform.\n\n"
    "Examples:\n"
    "  datasentinel validate samples/configs/ecommerce_orders_rules.yaml\n"
    "  datasentinel compare-schemas samples/configs/ecommerce_orders_rules.yaml\n"
    "  datasentinel register-schema samples/configs/ecommerce_orders_rules.yaml\n"
    "  datasentinel history\n"
    "  datasentinel list-rules samples/configs/ecommerce_orders_rules.yaml",
    add_completion=False,
)

console = Console(safe_box=True)


def _run_pipeline(
    config: SentinelConfig,
    report_dir: Optional[Path] = None,
    save_baseline: bool = False,
    send_alerts: bool = True,
    store_result: bool = True,
) -> RunSummary:
    """Core execution engine running connectors, rules, drift, anomalies, reports, and alerts."""
    start_time = time.time()
    run_id = str(uuid.uuid4())

    console.print(
        Panel.fit(
            f"[bold blue][DataSentinel] Running Validation Pipeline[/bold blue]\n"
            f"[bold]Dataset:[/bold] {config.dataset_name} | [bold]Run ID:[/bold] {run_id[:8]}",
            border_style="blue",
        )
    )

    # 1. Connect and Load Data
    with console.status("[cyan]Connecting to data source and loading dataset...", spinner="dots"):
        connector: BaseConnector = ConnectorRegistry.create(config.source)
        dataset: DataSet = connector.load()

    console.print(
        f"[green][OK][/green] Loaded dataset '[bold]{dataset.name}[/bold]' with "
        f"[bold]{dataset.row_count:,}[/bold] rows and [bold]{len(dataset.column_names)}[/bold] columns."
    )

    # 2. Schema Baseline & Drift Detection
    schema_dir = Path(config.schema_drift.baseline_store_path) if config.schema_drift.baseline_store_path else None
    schema_registry = SchemaRegistry(schema_dir)
    current_fingerprint = schema_registry.extract_fingerprint(dataset, dataset_name=config.dataset_name)

    if save_baseline:
        saved_path = schema_registry.register_baseline(current_fingerprint)
        console.print(f"[green][OK] Registered baseline schema fingerprint at:[/green] {saved_path}")

    schema_report = None
    drift_detected = False
    if config.schema_drift.enabled:
        baseline = schema_registry.get_baseline(config.dataset_name)
        schema_report = SchemaDriftDetector.detect_drift(baseline, current_fingerprint)
        drift_detected = schema_report.has_drift
        if drift_detected:
            console.print(
                f"[bold red][WARN] Schema Drift Detected ({len(schema_report.drifts)} differences found!)[/bold red]"
            )
        else:
            console.print("[green][OK] Schema structure matches baseline (no drift detected).[/green]")

    # 3. Rule Execution with Rich Progress Bar
    executor = RuleExecutor(config.rules)
    rule_results: list[RuleResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]Evaluating quality rules...", total=len(config.rules))

        def on_step(current: int, total: int, rule_name: str) -> None:
            progress.update(task_id, completed=current, description=f"[cyan]Rule: {rule_name}")

        rule_results = executor.execute_all(dataset, progress_callback=on_step)

    # 4. Statistical Anomaly Detection
    anomaly_detector = AnomalyDetector(config.anomaly_detection)
    with console.status("[cyan]Running statistical anomaly detection (Z-score & IQR)...", spinner="dots"):
        anomaly_report = anomaly_detector.analyze(dataset)

    console.print(
        f"[green][OK] Anomaly detection completed:[/green] Flagged "
        f"[bold]{anomaly_report.total_anomalies}[/bold] potential outliers across "
        f"[bold]{anomaly_report.columns_evaluated}[/bold] numeric columns."
    )

    # 5. Calculate Metrics & Status
    duration = time.time() - start_time
    total_rules = len(rule_results)
    passed_rules = sum(1 for r in rule_results if r.passed)
    failed_rules = sum(1 for r in rule_results if not r.passed and r.severity != Severity.WARNING)
    warning_rules = sum(1 for r in rule_results if not r.passed and r.severity == Severity.WARNING)

    overall_pass_rate = round((passed_rules / total_rules * 100.0), 2) if total_rules > 0 else 100.0
    status = executor.calculate_status(rule_results)

    if drift_detected and config.schema_drift.fail_on_drift:
        status = ValidationStatus.FAILED

    summary = RunSummary(
        run_id=run_id,
        dataset_name=config.dataset_name,
        status=status,
        duration_seconds=round(duration, 3),
        total_rows=dataset.row_count,
        total_columns=len(dataset.column_names),
        total_rules=total_rules,
        passed_rules=passed_rules,
        failed_rules=failed_rules,
        warning_rules=warning_rules,
        overall_pass_rate=overall_pass_rate,
        schema_drift_detected=drift_detected,
        total_anomalies=anomaly_report.total_anomalies,
        rule_results=rule_results,
        schema_report=schema_report,
        anomaly_report=anomaly_report,
    )

    # 6. Persist to Result Store
    store = ResultStore()
    if store_result:
        store.record_run(summary)

    # 7. Generate Reports if requested
    if report_dir:
        report_gen = ReportGenerator()
        trend_data = store.get_trend(config.dataset_name, limit=10)
        html_p, pdf_p = report_gen.generate_all(summary, report_dir, trend_data=trend_data)
        console.print(f"[green][OK] Executive HTML report written to:[/green] {html_p}")
        console.print(f"[green][OK] Executive PDF report written to:[/green] {pdf_p}")

    # 8. Send Alerts if configured
    if send_alerts and config.alerts:
        if config.alerts.email and config.alerts.email.enabled:
            try:
                EmailAlertService(config.alerts.email).send_alert(summary)
                console.print("[green][OK] SMTP Email alert dispatched successfully.[/green]")
            except Exception as exc:
                console.print(f"[yellow][WARN] Failed to deliver Email alert: {exc}[/yellow]")

        if config.alerts.slack and config.alerts.slack.enabled:
            try:
                SlackAlertService(config.alerts.slack).send_alert(summary)
                console.print("[green][OK] Slack webhook alert dispatched successfully.[/green]")
            except Exception as exc:
                console.print(f"[yellow][WARN] Failed to deliver Slack alert: {exc}[/yellow]")

    return summary


def _print_summary_tables(summary: RunSummary) -> None:
    """Print Rich styled summary tables to the terminal."""
    # Rules Table
    table = Table(
        title=f"\nQuality Rules Execution Summary: {summary.dataset_name}",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Status", justify="center", style="bold")
    table.add_column("Rule Name", style="bold")
    table.add_column("Type")
    table.add_column("Column")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Violations", justify="right")
    table.add_column("Summary Message")

    for r in summary.rule_results:
        status_str = "[green]PASS[/green]" if r.passed else f"[{'yellow' if r.severity == Severity.WARNING else 'red'}]FAIL[/{'yellow' if r.severity == Severity.WARNING else 'red'}]"
        table.add_row(
            status_str,
            r.rule_name,
            r.rule_type.value,
            r.column,
            f"{r.pass_rate}%",
            str(r.violation_count),
            r.message[:80] + ("..." if len(r.message) > 80 else ""),
        )

    console.print(table)

    # Schema Drift Table if drift exists
    if summary.schema_report and summary.schema_report.drifts:
        drift_table = Table(
            title="[bold red][WARN] Schema Drift Differences[/bold red]",
            header_style="bold magenta",
        )
        drift_table.add_column("Drift Type")
        drift_table.add_column("Column")
        drift_table.add_column("Baseline Value")
        drift_table.add_column("Current Value")
        drift_table.add_column("Details")
        for d in summary.schema_report.drifts:
            drift_table.add_row(
                d.drift_type.value,
                d.column_name,
                d.baseline_value or "-",
                d.current_value or "-",
                d.details,
            )
        console.print(drift_table)

    # Overall Summary Banner
    banner_color = (
        "green"
        if summary.status == ValidationStatus.PASSED
        else ("yellow" if summary.status == ValidationStatus.WARNING else "red")
    )
    console.print(
        Panel.fit(
            f"[{banner_color} bold]Validation Status: {summary.status.value.upper()}[/{banner_color} bold]\n"
            f"Pass Rate: [bold]{summary.overall_pass_rate}%[/bold] | "
            f"Rules Passed: [green]{summary.passed_rules}[/green] / {summary.total_rules} | "
            f"Anomalies: [yellow]{summary.total_anomalies}[/yellow] | "
            f"Schema Drift: [{'red' if summary.schema_drift_detected else 'green'}]{'DETECTED' if summary.schema_drift_detected else 'NONE'}[/{'red' if summary.schema_drift_detected else 'green'}] | "
            f"Time: {summary.duration_seconds}s",
            border_style=banner_color,
        )
    )


@app.command("validate")
def validate(
    config_path: Path = typer.Argument(
        ...,
        help="Path to YAML rule configuration file. (e.g. 'samples/configs/ecommerce_orders_rules.yaml')",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    report_dir: Optional[Path] = typer.Option(
        None,
        "--report-dir",
        "-r",
        help="Output directory to generate executive HTML and PDF reports.",
    ),
    save_baseline: bool = typer.Option(
        False,
        "--save-baseline",
        "-b",
        help="Store current dataset schema fingerprint as the baseline for future drift diffs.",
    ),
    send_alerts: bool = typer.Option(
        True,
        "--send-alerts/--no-alerts",
        help="Send configured email or Slack alerts upon completion.",
    ),
) -> None:
    """Validate a dataset against quality rules, detect schema drift and statistical anomalies.

    Example:
        datasentinel validate config.yaml --report-dir ./reports --save-baseline
    """
    try:
        config = load_config_from_yaml(config_path)
        summary = _run_pipeline(
            config,
            report_dir=report_dir,
            save_baseline=save_baseline,
            send_alerts=send_alerts,
        )
        _print_summary_tables(summary)

        if summary.status == ValidationStatus.FAILED:
            raise typer.Exit(code=1)
    except DataSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


@app.command("report")
def report(
    config_path: Path = typer.Argument(
        ...,
        help="Path to YAML rule configuration file.",
        exists=True,
        file_okay=True,
    ),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output-dir",
        "-o",
        help="Directory to save generated HTML and PDF reports.",
    ),
) -> None:
    """Generate professional HTML and PDF reports without executing alerts.

    Example:
        datasentinel report config.yaml -o ./executive_reports
    """
    try:
        config = load_config_from_yaml(config_path)
        summary = _run_pipeline(
            config,
            report_dir=output_dir,
            send_alerts=False,
            store_result=True,
        )
        _print_summary_tables(summary)
    except DataSentinelError as exc:
        console.print(f"[bold red]Report Generation Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


@app.command("compare-schemas")
def compare_schemas(
    config_path: Path = typer.Argument(
        ...,
        help="Path to YAML rule configuration file.",
        exists=True,
        file_okay=True,
    ),
) -> None:
    """Compare current dataset schema against registered baseline fingerprint and show diffs.

    Example:
        datasentinel compare-schemas config.yaml
    """
    try:
        config = load_config_from_yaml(config_path)
        connector = ConnectorRegistry.create(config.source)
        dataset = connector.load()

        schema_dir = Path(config.schema_drift.baseline_store_path) if config.schema_drift.baseline_store_path else None
        registry = SchemaRegistry(schema_dir)
        current_fp = registry.extract_fingerprint(dataset, dataset_name=config.dataset_name)
        baseline_fp = registry.get_baseline(config.dataset_name)

        if not baseline_fp:
            console.print(
                f"[yellow]No baseline registered for dataset '{config.dataset_name}'. "
                f"Run with '--save-baseline' or 'datasentinel register-schema' first.[/yellow]"
            )
            return

        report = SchemaDriftDetector.detect_drift(baseline_fp, current_fp)

        if not report.has_drift:
            console.print(f"[green][OK] Schema for '{config.dataset_name}' matches baseline perfectly. No drift detected.[/green]")
            return

        table = Table(title=f"Schema Drift Detected: {config.dataset_name}", header_style="bold red")
        table.add_column("Drift Type", style="bold")
        table.add_column("Column")
        table.add_column("Baseline")
        table.add_column("Current")
        table.add_column("Details")

        for d in report.drifts:
            table.add_row(
                d.drift_type.value,
                d.column_name,
                d.baseline_value or "-",
                d.current_value or "-",
                d.details,
            )
        console.print(table)
    except DataSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


@app.command("register-schema")
def register_schema(
    config_path: Path = typer.Argument(
        ...,
        help="Path to YAML rule configuration file.",
        exists=True,
        file_okay=True,
    ),
) -> None:
    """Extract and register current schema fingerprint as baseline for future runs.

    Example:
        datasentinel register-schema config.yaml
    """
    try:
        config = load_config_from_yaml(config_path)
        connector = ConnectorRegistry.create(config.source)
        dataset = connector.load()

        schema_dir = Path(config.schema_drift.baseline_store_path) if config.schema_drift.baseline_store_path else None
        registry = SchemaRegistry(schema_dir)
        fp = registry.extract_fingerprint(dataset, dataset_name=config.dataset_name)
        saved_path = registry.register_baseline(fp)

        console.print(
            Panel.fit(
                f"[green bold][OK] Registered Schema Baseline Fingerprint[/green bold]\n"
                f"Dataset: [bold]{fp.dataset_name}[/bold]\n"
                f"Columns: [bold]{fp.column_count}[/bold]\n"
                f"Rows: [bold]{fp.row_count}[/bold]\n"
                f"Fingerprint SHA256: [dim]{fp.hash_fingerprint}[/dim]\n"
                f"Saved to: [cyan]{saved_path}[/cyan]",
                border_style="green",
            )
        )
    except DataSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


@app.command("list-rules")
def list_rules(
    config_path: Optional[Path] = typer.Argument(
        None,
        help="Optional path to YAML rule configuration file to inspect configured rules.",
    ),
) -> None:
    """List all available rule types or inspect rules configured within a YAML file.

    Example:
        datasentinel list-rules
        datasentinel list-rules config.yaml
    """
    if config_path is None:
        table = Table(title="Available Quality Rule Validators", header_style="bold cyan")
        table.add_column("Rule Type", style="bold")
        table.add_column("Description")
        table.add_column("Configurable Parameters (YAML)")

        table.add_row(
            "null_check",
            "Validates missing / null values",
            "allow_null (bool), max_null_percentage (float), max_null_count (int)",
        )
        table.add_row(
            "unique_check",
            "Detects duplicate rows / entries",
            "allow_duplicates (bool), max_duplicate_percentage (float), max_duplicate_count (int)",
        )
        table.add_row(
            "range",
            "Validates numeric or date bounds",
            "min_value (num), max_value (num), inclusive (bool)",
        )
        table.add_row(
            "regex",
            "Regex pattern verification",
            "pattern (str), invert_match (bool), case_sensitive (bool), allow_null (bool)",
        )
        table.add_row(
            "foreign_key",
            "Referential integrity across columns",
            "reference_column (str), allowed_values (list), allow_null (bool)",
        )
        console.print(table)
        return

    try:
        config = load_config_from_yaml(config_path)
        table = Table(title=f"Configured Rules: {config.dataset_name}", header_style="bold cyan")
        table.add_column("#", justify="center")
        table.add_column("Rule Name", style="bold")
        table.add_column("Type")
        table.add_column("Column")
        table.add_column("Severity")
        table.add_column("Parameters")

        for idx, r in enumerate(config.rules, 1):
            table.add_row(
                str(idx),
                r.name,
                r.type.value,
                r.column,
                r.severity.value,
                str(r.parameters),
            )
        console.print(table)
    except DataSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


@app.command("history")
def history(
    dataset_name: Optional[str] = typer.Option(
        None,
        "--dataset",
        "-d",
        help="Filter historical runs by dataset name.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of historical runs to display.",
    ),
) -> None:
    """Display past validation runs and pass rate trends from SQLite result store.

    Example:
        datasentinel history --limit 5
        datasentinel history --dataset ecommerce_orders
    """
    store = ResultStore()
    runs = store.get_history(dataset_name=dataset_name, limit=limit)

    if not runs:
        console.print("[yellow]No historical validation runs found in store.[/yellow]")
        return

    table = Table(title="Validation Run History", header_style="bold cyan")
    table.add_column("Run ID", style="dim")
    table.add_column("Dataset", style="bold")
    table.add_column("Timestamp")
    table.add_column("Status", justify="center")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Rules (P/F/W)")
    table.add_column("Anomalies", justify="right")
    table.add_column("Drift", justify="center")
    table.add_column("Duration")

    for r in runs:
        status_color = "green" if r.status == ValidationStatus.PASSED else ("yellow" if r.status == ValidationStatus.WARNING else "red")
        table.add_row(
            r.run_id[:8],
            r.dataset_name,
            r.timestamp.strftime("%Y-%m-%d %H:%M"),
            f"[{status_color}]{r.status.value.upper()}[/{status_color}]",
            f"{r.overall_pass_rate}%",
            f"{r.passed_rules}/{r.failed_rules}/{r.warning_rules}",
            str(r.total_anomalies),
            "YES" if r.schema_drift_detected else "NO",
            f"{r.duration_seconds:.2f}s",
        )

    console.print(table)


@app.command("schedule")
def schedule(
    config_path: Path = typer.Argument(
        ...,
        help="Path to YAML rule configuration file containing scheduler settings.",
        exists=True,
        file_okay=True,
    ),
) -> None:
    """Start APScheduler recurring validation daemon with cron expression and coalesce=True.

    Example:
        datasentinel schedule config.yaml
    """
    try:
        config = load_config_from_yaml(config_path)
        if not config.scheduler or not config.scheduler.cron:
            console.print(
                "[bold red]Error:[/bold red] The configuration file has no 'scheduler.cron' setting defined."
            )
            raise typer.Exit(code=2)

        def run_task() -> None:
            console.print(f"[bold cyan][CRON] Trigger fired for '{config.dataset_name}'[/bold cyan]")
            summary = _run_pipeline(config, send_alerts=True, store_result=True)
            _print_summary_tables(summary)

        scheduler_runner = ValidationScheduler(config, task_callback=run_task)
        console.print(
            Panel.fit(
                f"[bold green]Starting DataSentinel Recurring Scheduler[/bold green]\n"
                f"Dataset: [bold]{config.dataset_name}[/bold]\n"
                f"Cron: [bold]{config.scheduler.cron}[/bold]\n"
                f"Coalesce: [bold]{config.scheduler.coalesce}[/bold] (missed runs coalesced to prevent overlap)\n"
                f"Press [bold red]Ctrl+C[/bold red] to stop.",
                border_style="green",
            )
        )
        scheduler_runner.start()
    except DataSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
