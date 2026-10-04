"""SANGYAN Command Line Interface (CLI) for server execution, migrations, and backups."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from sangyan.config import load_config, validate_production_config
from sangyan.core.logging import configure_logging, get_logger
from sangyan.database.backup import BackupManager
from sangyan.database.engine import create_engine
from sangyan.database.migrations import MigrationRunner

logger = get_logger("sangyan.cli")


@click.group()
@click.version_option(version="0.7.0")
def cli():
    """SANGYAN: Investor Safety & Content Intelligence Platform CLI."""
    pass


@cli.command("serve")
@click.option("--host", default=None, help="Host interface to bind (default: from config or 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to bind (default: from config or 8000)")
@click.option("--workers", default=1, type=int, help="Worker count (enforced to 1 for in-process state safety)")
@click.option("--log-level", default=None, help="Logging level (DEBUG, INFO, WARNING, ERROR)")
def serve(host: Optional[str], port: Optional[int], workers: int, log_level: Optional[str]):
    """Run production SANGYAN API server via Uvicorn with graceful signal handling."""
    config = load_config()
    validate_production_config(config)

    bind_host = host or config.host
    bind_port = port or config.port
    log_lvl = (log_level or config.log_level).lower()

    if workers > 1:
        click.echo(
            click.style(
                "WARNING: SANGYAN uses process-local state (rate limiter, SQLite checkpoints, investigation locks). "
                "Running with workers > 1 is not recommended. Clamping workers to 1.",
                fg="yellow",
            )
        )
        workers = 1

    configure_logging(level=log_lvl.upper())
    logger.info("Starting SANGYAN server on %s:%d (env=%s, workers=%d)", bind_host, bind_port, config.env, workers)

    import uvicorn

    uvicorn.run(
        "sangyan.api.app:app",
        host=bind_host,
        port=bind_port,
        workers=workers,
        log_level=log_lvl,
        access_log=True,
        timeout_graceful_shutdown=30,
    )


@cli.command("migrate")
@click.option("--database-url", default=None, help="Target database connection URL")
def migrate(database_url: Optional[str]):
    """Apply all pending linear schema migrations with concurrency locking."""
    config = load_config()
    db_url = database_url or config.database_url
    engine = create_engine(db_url)
    runner = MigrationRunner(engine)

    click.echo(f"Connecting to database: {config._sanitize_db_url(db_url)}")
    applied = runner.migrate()
    if applied:
        click.echo(click.style(f"Successfully applied {len(applied)} migrations:", fg="green"))
        for m in applied:
            click.echo(f"  + {m}")
    else:
        click.echo(click.style("Database schema is already up-to-date. Zero migrations applied.", fg="cyan"))


@cli.command("migrate-status")
@click.option("--database-url", default=None, help="Target database connection URL")
def migrate_status(database_url: Optional[str]):
    """Display applied and pending database schema migrations."""
    config = load_config()
    db_url = database_url or config.database_url
    engine = create_engine(db_url)
    runner = MigrationRunner(engine)

    status = runner.status()
    click.echo(f"Database dialect: {engine.dialect}")
    click.echo(f"Current version:  {status['current_version']}")
    click.echo(f"Latest version:   {status['latest_version']}")
    click.echo(f"Is up-to-date:    {status['is_current']}")
    click.echo(f"Applied versions: {status['applied_versions']}")
    if status["pending_versions"]:
        click.echo(click.style(f"Pending versions: {status['pending_versions']}", fg="yellow"))
    else:
        click.echo(click.style("No pending migrations.", fg="green"))


@cli.group("backup")
def backup_group():
    """Automated database backup, verification, and disaster recovery commands."""
    pass


@backup_group.command("create")
@click.option("--output-dir", default=None, help="Directory to save backup archive")
@click.option("--encrypt/--no-encrypt", default=False, help="Encrypt archive using AES-256-GCM")
@click.option("--key", default=None, help="Encryption key (or via SANGYAN_BACKUP_ENCRYPTION_KEY)")
def backup_create(output_dir: Optional[str], encrypt: bool, key: Optional[str]):
    """Create a point-in-time database snapshot with SHA-256 checksum and optional encryption."""
    config = load_config()
    db_url = config.database_url
    engine = create_engine(db_url)
    enc_key = key or config.backup_encryption_key
    out_dir = output_dir or config.backup_dir

    if encrypt and not enc_key:
        click.echo(click.style("Error: --encrypt specified but no key provided (or set in SANGYAN_BACKUP_ENCRYPTION_KEY).", fg="red"), err=True)
        sys.exit(1)

    manager = BackupManager(
        engine=engine,
        checkpoint_db_path=config.checkpoint_db_path,
        key_dir=config.key_dir,
        default_backup_dir=out_dir,
    )

    click.echo(f"Creating backup for database: {config._sanitize_db_url(db_url)}...")
    archive_path = manager.create_backup(
        backup_dir=out_dir,
        encrypt=encrypt or bool(enc_key),
        encryption_key=enc_key,
    )
    click.echo(click.style(f"Backup created successfully: {archive_path}", fg="green"))

    # Also display checksum file
    sha_file = archive_path.parent / f"{archive_path.name}.sha256"
    if sha_file.exists():
        click.echo(f"Checksum: {sha_file.read_text().strip()}")


@backup_group.command("verify")
@click.argument("backup_path", type=click.Path(exists=True))
@click.option("--key", default=None, help="Decryption key if archive is encrypted")
def backup_verify(backup_path: str, key: Optional[str]):
    """Verify backup SHA-256 checksum, archive readability, and database integrity."""
    config = load_config()
    engine = create_engine(config.database_url)
    enc_key = key or config.backup_encryption_key
    manager = BackupManager(engine=engine)

    click.echo(f"Verifying backup integrity for: {backup_path}...")
    try:
        res = manager.verify_backup(backup_path, encryption_key=enc_key)
        click.echo(click.style("Backup verification PASSED:", fg="green"))
        click.echo(f"  Archive:     {res['archive']}")
        click.echo(f"  SHA-256:     {res['sha256']}")
        click.echo(f"  Encrypted:   {res['encrypted']}")
        click.echo(f"  Integrity:   {res['integrity_check']}")
        click.echo(f"  Artifacts:   {res['artifacts']}")
    except Exception as e:
        click.echo(click.style(f"Backup verification FAILED: {e}", fg="red"), err=True)
        sys.exit(1)


@backup_group.command("restore")
@click.argument("backup_path", type=click.Path(exists=True))
@click.option("--target-dir", required=True, type=click.Path(), help="Target directory for restored artifacts")
@click.option("--key", default=None, help="Decryption key if archive is encrypted")
def backup_restore(backup_path: str, target_dir: str, key: Optional[str]):
    """Restore database and checkpoints into an isolated directory with verification."""
    config = load_config()
    engine = create_engine(config.database_url)
    enc_key = key or config.backup_encryption_key
    manager = BackupManager(engine=engine)

    click.echo(f"Restoring backup {backup_path} to {target_dir}...")
    try:
        res = manager.restore_backup(backup_path, target_dir=target_dir, encryption_key=enc_key)
        click.echo(click.style("Restore completed successfully:", fg="green"))
        click.echo(f"  Target Dir:          {res['target_dir']}")
        click.echo(f"  Restored Relational: {res['restored_relational']}")
        click.echo(f"  Restored Checkpoints:{res['restored_checkpoints']}")
        click.echo(f"  Table Count:         {res['table_count']}")
        click.echo(f"  Migrations Applied:  {res['migrations_applied']}")
    except Exception as e:
        click.echo(click.style(f"Restore failed: {e}", fg="red"), err=True)
        sys.exit(1)


@backup_group.command("prune")
@click.option("--backup-dir", default=None, help="Backup storage directory")
@click.option("--keep", default=7, type=int, help="Number of recent backups to keep")
def backup_prune(backup_dir: Optional[str], keep: int):
    """Prune older backups beyond the retention count."""
    config = load_config()
    engine = create_engine(config.database_url)
    b_dir = backup_dir or config.backup_dir
    manager = BackupManager(engine=engine, default_backup_dir=b_dir)

    pruned = manager.prune_backups(backup_dir=b_dir, keep_count=keep)
    if pruned:
        click.echo(click.style(f"Pruned {len(pruned)} older backups:", fg="yellow"))
        for p in pruned:
            click.echo(f"  - {p}")
    else:
        click.echo(click.style(f"No backups pruned (retention count: {keep}).", fg="cyan"))


@cli.command("health")
@click.option("--url", default="http://127.0.0.1:8000", help="Base URL of SANGYAN service")
def health_cmd(url: str):
    """Query SANGYAN operational health endpoints (live, ready, summary)."""
    import urllib.error
    import urllib.request

    base = url.rstrip("/")
    endpoints = ["/health/live", "/health/ready", "/health"]
    for ep in endpoints:
        target = f"{base}{ep}"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "Sangyan-CLI/0.7.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                code = response.getcode()
                body = response.read().decode("utf-8")
                color = "green" if code == 200 else "yellow"
                click.echo(f"{ep:<15} [{click.style(str(code), fg=color)}] {body}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            click.echo(f"{ep:<15} [{click.style(str(e.code), fg='red')}] {body}")
        except Exception as e:
            click.echo(f"{ep:<15} [{click.style('ERR', fg='red')}] {e}")


if __name__ == "__main__":
    cli()
