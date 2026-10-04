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


@backup_group.command("upload")
@click.argument("backup_path", type=click.Path(exists=True))
@click.option("--bucket", default=None, help="S3 bucket or destination container")
@click.option("--prefix", default="backups/sangyan", help="Cloud object key prefix")
def backup_upload(backup_path: str, bucket: Optional[str], prefix: str):
    """Replicate an encrypted backup archive to cloud storage."""
    config = load_config()
    b_bucket = bucket or config.backup_s3_bucket
    if not b_bucket:
        click.echo(
            click.style(
                "Error: S3 bucket not specified (pass --bucket or set SANGYAN_BACKUP_S3_BUCKET)",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)

    from sangyan.database.cloud_backup import S3BackupStorage

    storage = S3BackupStorage(bucket=b_bucket, prefix=prefix, region=config.backup_s3_region)
    click.echo(f"Replicating backup {backup_path} to s3://{b_bucket}/{prefix}...")
    try:
        manifest = storage.upload_backup(backup_path)
        click.echo(click.style("Cloud backup replication SUCCESSFUL:", fg="green"))
        click.echo(f"  Cloud Key:   {manifest.cloud_key}")
        click.echo(f"  SHA-256:     {manifest.sha256}")
        click.echo(f"  Size Bytes:  {manifest.size_bytes}")
        click.echo(f"  Encrypted:   {manifest.encrypted}")
    except Exception as e:
        click.echo(click.style(f"Cloud replication FAILED: {e}", fg="red"), err=True)
        sys.exit(1)


@backup_group.command("restore-cloud")
@click.argument("cloud_key")
@click.option("--target-dir", required=True, type=click.Path(), help="Target directory for restored artifacts")
@click.option("--key", default=None, help="Decryption key for archive")
@click.option("--bucket", default=None, help="S3 bucket")
def backup_restore_cloud(cloud_key: str, target_dir: str, key: Optional[str], bucket: Optional[str]):
    """Download encrypted cloud backup, verify checksum, and restore into isolated directory."""
    config = load_config()
    b_bucket = bucket or config.backup_s3_bucket
    if not b_bucket:
        click.echo(
            click.style(
                "Error: S3 bucket not specified (pass --bucket or set SANGYAN_BACKUP_S3_BUCKET)",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)

    from sangyan.database.cloud_backup import S3BackupStorage

    storage = S3BackupStorage(bucket=b_bucket, region=config.backup_s3_region)
    engine = create_engine(config.database_url)
    enc_key = key or config.backup_encryption_key
    manager = BackupManager(engine=engine)

    click.echo(f"Restoring cloud backup s3://{b_bucket}/{cloud_key} to {target_dir}...")
    try:
        res = storage.restore_from_cloud(
            cloud_key=cloud_key,
            target_dir=target_dir,
            backup_manager=manager,
            encryption_key=enc_key,
        )
        click.echo(click.style("Cloud restore completed successfully:", fg="green"))
        click.echo(f"  Target Dir:          {res['target_dir']}")
        click.echo(f"  Restored Relational: {res['restored_relational']}")
        click.echo(f"  Restored Checkpoints:{res['restored_checkpoints']}")
        click.echo(f"  Table Count:         {res['table_count']}")
    except Exception as e:
        click.echo(click.style(f"Cloud restore failed: {e}", fg="red"), err=True)
        sys.exit(1)


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


@cli.command("worker")
@click.option("--worker-id", default=None, help="Explicit unique identifier for this worker instance")
@click.option("--concurrency", default=None, type=int, help="Thread concurrency (default: from config or 4)")
@click.option("--lease-sec", default=None, type=float, help="Task lease duration in seconds (default: 60.0)")
@click.option("--poll-ms", default=1000, type=int, help="Queue polling interval in milliseconds")
def worker_cmd(worker_id: Optional[str], concurrency: Optional[int], lease_sec: Optional[float], poll_ms: int):
    """Run asynchronous investigation worker consuming from Redis Streams with bounded leases."""
    config = load_config()
    validate_production_config(config)

    configure_logging(level=config.log_level)
    logger.info("Initializing SANGYAN async task worker in env=%s...", config.env)

    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()

    from sangyan.dr.manager import DisasterRecoveryManager
    dr_mgr = DisasterRecoveryManager(
        engine=engine,
        region_id=config.region_id,
        default_role=config.dr_role,
        default_epoch=config.dr_cluster_epoch,
    )

    from sangyan.tenancy.repository import TenantRepository
    def repo_factory(oid: str, user_id=None):
        return TenantRepository(
            engine,
            organization_id=oid,
            user_id=user_id or "system",
            dr_manager=dr_mgr if config.dr_fencing_enabled else None,
            region_id=config.region_id,
        )

    from sangyan.trust.service import TrustService
    from sangyan.verification.sources import AuthoritativeSourceRegistry
    from sangyan.verification.snapshots import SnapshotManager
    from sangyan.verification.trust_binding import TrustBindingService
    from sangyan.verification.engine import ClaimVerificationEngine
    from sangyan.verification.cache import VerificationCache, RateLimiter
    from sangyan.workflow.nodes import WorkflowNodeSuite
    from sangyan.workflow.checkpointer import WorkflowCheckpointer
    from sangyan.workflow.service import WorkflowService

    t_service = TrustService(engine, key_dir=config.key_dir)
    trust_binding = TrustBindingService(t_service)
    src_reg = AuthoritativeSourceRegistry()
    snap_mgr = SnapshotManager()

    verif_engine = ClaimVerificationEngine(
        source_registry=src_reg,
        snapshot_manager=snap_mgr,
        trust_binding=trust_binding,
        cache=VerificationCache(),
        rate_limiter=RateLimiter(),
    )

    node_suite = WorkflowNodeSuite(
        verification_engine=verif_engine,
        trust_binding=trust_binding,
        repository_factory=repo_factory,
    )

    if (
        config.checkpoint_backend == "postgres"
        and config.database_url
        and config.database_url.startswith(("postgresql://", "postgres://"))
    ):
        wf_cp = WorkflowCheckpointer(postgres_url=config.database_url)
    elif config.checkpoint_db_path:
        wf_cp = WorkflowCheckpointer(db_path=config.checkpoint_db_path)
    else:
        wf_cp = WorkflowCheckpointer(in_memory=True)

    wf_service = WorkflowService(
        repository_factory=repo_factory,
        node_suite=node_suite,
        checkpointer=wf_cp,
    )

    from sangyan.async_exec.models import AsyncTask
    from sangyan.async_exec.queue import InMemoryTaskQueue, RedisStreamTaskQueue
    from sangyan.async_exec.repository import AsyncTaskRepository
    from sangyan.async_exec.worker import AsyncInvestigationWorker

    task_repo = AsyncTaskRepository(engine)

    if config.task_queue_type == "redis_stream" and config.redis_url:
        queue = RedisStreamTaskQueue(
            redis_url=config.redis_url,
            stream_name=config.task_queue_stream,
            group_name=config.task_queue_group,
            dead_letter_stream=config.task_dead_letter_stream,
        )
    else:
        queue = InMemoryTaskQueue()

    lease_duration = lease_sec or config.task_lease_duration_sec
    effective_concurrency = concurrency if concurrency is not None else config.worker_concurrency
    worker = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=wf_service,
        worker_id=worker_id,
        lease_duration_sec=lease_duration,
        concurrency=effective_concurrency,
        maintenance_interval_sec=config.task_retry_sweep_interval_sec,
        stale_queue_requeue_sec=config.task_stale_queue_requeue_sec,
    )

    click.echo(click.style(f"Worker {worker.worker_id} started (lease={lease_duration}s, region={config.region_id})...", fg="green"))
    try:
        worker.run_forever(poll_interval_ms=poll_ms)
    finally:
        queue.close()
        engine.close()
        wf_cp.close()


@cli.group("dr")
def dr_group():
    """Multi-region disaster recovery, region authority, and split-brain fencing commands."""
    pass


@dr_group.command("status")
def dr_status():
    """Display active primary, cluster epoch, and region fencing status."""
    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.dr.manager import DisasterRecoveryManager
    mgr = DisasterRecoveryManager(engine=engine, region_id=config.region_id, default_role=config.dr_role, default_epoch=config.dr_cluster_epoch)
    status_data = mgr.get_cluster_status()

    click.echo(click.style("SANGYAN Multi-Region DR Status:", fg="cyan", bold=True))
    click.echo(f"  Local Region:    {status_data['local_region']}")
    click.echo(f"  Active Primary:  {status_data['active_primary']}")
    click.echo(f"  Cluster Epoch:   {status_data['current_epoch']}")
    click.echo("\nRegistered Regions:")
    for r in status_data["regions"]:
        fenced_str = click.style("[FENCED]", fg="red") if r["is_fenced"] else click.style("[ACTIVE/READY]", fg="green")
        click.echo(f"  - {r['region_id']:<20} Role: {r['role']:<15} Epoch: {r['cluster_epoch']} {fenced_str}")
        if r.get("fence_reason"):
            click.echo(f"      Fence reason: {r['fence_reason']}")


@dr_group.command("promote")
@click.argument("region_id")
@click.option("--reason", default="", help="Promotion justification")
@click.option("--yes", is_flag=True, default=False, help="Skip interactive confirmation (for automation)")
def dr_promote(region_id: str, reason: str, yes: bool):
    """Promote a standby region to active primary with epoch progression and fencing.

    Requires explicit operator intent: prompts for confirmation unless --yes is given.
    """
    if not yes:
        click.echo(
            click.style(
                f"About to promote region '{region_id}' to PRIMARY_ACTIVE. "
                "This increments the cluster epoch and fences the current primary.",
                fg="yellow",
                bold=True,
            )
        )
        if not click.confirm("Proceed with promotion?", default=False):
            click.echo(click.style("Promotion cancelled; no changes made.", fg="cyan"))
            sys.exit(0)

    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.dr.manager import DisasterRecoveryManager
    mgr = DisasterRecoveryManager(engine=engine, region_id=config.region_id, default_role=config.dr_role, default_epoch=config.dr_cluster_epoch)
    try:
        res = mgr.promote_region(region_id, reason=reason)
        click.echo(click.style(f"Region '{region_id}' successfully promoted to PRIMARY_ACTIVE (epoch {res.cluster_epoch})", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Promotion failed: {e}", fg="red"), err=True)
        sys.exit(1)


@dr_group.command("simulate")
@click.argument("from_region")
@click.argument("to_region")
@click.option("--reason", default="Simulated failover via CLI", help="Simulation reason")
@click.option("--yes", is_flag=True, default=False, help="Skip interactive confirmation (for automation)")
def dr_simulate(from_region: str, to_region: str, reason: str, yes: bool):
    """Simulate a controlled DR failover and verify cryptographic audit ledger continuity.

    This performs real role/epoch transitions; explicit operator intent is required.
    """
    if not yes:
        click.echo(
            click.style(
                f"About to simulate failover: '{from_region}' -> '{to_region}'. "
                "This demotes the current primary and promotes the target.",
                fg="yellow",
                bold=True,
            )
        )
        if not click.confirm("Proceed with simulated failover?", default=False):
            click.echo(click.style("Simulation cancelled; no changes made.", fg="cyan"))
            sys.exit(0)

    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.dr.manager import DisasterRecoveryManager
    mgr = DisasterRecoveryManager(engine=engine, region_id=config.region_id, default_role=config.dr_role, default_epoch=config.dr_cluster_epoch)
    try:
        report = mgr.simulate_failover(from_region, to_region, reason=reason)
        click.echo(click.style("Disaster Recovery Failover Simulation: SUCCESS", fg="green", bold=True))
        click.echo(f"  Demoted Source:      {report['from_region']['region_id']} ({report['from_region']['role']})")
        click.echo(f"  Promoted Target:     {report['to_region']['region_id']} ({report['to_region']['role']}, Epoch {report['epoch']})")
        click.echo(f"  Duration:            {report['duration_seconds']}s")
        click.echo(f"  Audit Hash Chain:    {'VALID' if report['audit_continuity']['valid'] else 'BROKEN'} ({report['audit_continuity']['event_count']} events)")
    except Exception as e:
        click.echo(click.style(f"Simulation failed: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.group("task")
def task_group():
    """Asynchronous task queue inspection, dead-letter management, and retry commands."""
    pass


@task_group.command("list")
@click.option("--status", default=None, help="Filter by task status (QUEUED, RUNNING, SUCCEEDED, DEAD_LETTERED, etc.)")
@click.option("--org", default=None, help="Filter by organization ID")
@click.option("--limit", default=20, type=int, help="Max tasks to display")
def task_list(status: Optional[str], org: Optional[str], limit: int):
    """List asynchronous tasks from relational outbox ledger."""
    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.async_exec.repository import AsyncTaskRepository
    repo = AsyncTaskRepository(engine)
    tasks = repo.list_tasks(organization_id=org, status=status, limit=limit)
    if not tasks:
        click.echo(click.style("No tasks found matching criteria.", fg="cyan"))
        return

    click.echo(f"{'TASK ID':<24} {'TYPE':<18} {'STATUS':<15} {'RETRIES':<8} {'INVESTIGATION ID'}")
    click.echo("-" * 80)
    for t in tasks:
        st_color = "green" if t.status == "SUCCEEDED" else ("red" if t.status == "DEAD_LETTERED" else "yellow")
        click.echo(f"{t.task_id:<24} {t.task_type:<18} {click.style(t.status, fg=st_color):<24} {t.retry_count:<8} {t.investigation_id}")


@task_group.command("inspect")
@click.argument("task_id")
def task_inspect(task_id: str):
    """Inspect detailed state, payload, result, and lease information for a task."""
    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.async_exec.repository import AsyncTaskRepository
    repo = AsyncTaskRepository(engine)
    task = repo.get_task_or_none(task_id)
    if not task:
        click.echo(click.style(f"Task '{task_id}' not found.", fg="red"), err=True)
        sys.exit(1)

    click.echo(click.style(f"Task Details: {task.task_id}", fg="cyan", bold=True))
    click.echo(f"  Organization:  {task.organization_id}")
    click.echo(f"  User:          {task.user_id}")
    click.echo(f"  Investigation: {task.investigation_id}")
    click.echo(f"  Type:          {task.task_type}")
    click.echo(f"  Status:        {task.status}")
    click.echo(f"  Retries:       {task.retry_count}/{task.max_retries}")
    click.echo(f"  Lease Owner:   {task.lease_owner or 'None'}")
    click.echo(f"  Lease Expires: {task.lease_expires_at or 'None'}")
    click.echo(f"  Created At:    {task.created_at}")
    click.echo(f"  Completed At:  {task.completed_at or 'None'}")
    if task.error_message:
        click.echo(click.style(f"  Error:         {task.error_message}", fg="red"))
    if task.result:
        click.echo(f"  Result:        {json.dumps(task.result, indent=2)}")


@task_group.command("dead-letter")
@click.option("--limit", default=20, type=int, help="Max dead-lettered tasks to list")
def task_dead_letter(limit: int):
    """List dead-lettered tasks that exhausted retries or suffered fatal errors."""
    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.async_exec.repository import AsyncTaskRepository
    repo = AsyncTaskRepository(engine)
    tasks = repo.list_dead_letter(limit=limit)
    if not tasks:
        click.echo(click.style("Zero dead-lettered tasks found. Queue is clean.", fg="green"))
        return

    click.echo(click.style(f"Dead-Lettered Tasks ({len(tasks)}):", fg="red", bold=True))
    for t in tasks:
        click.echo(f"  - {t.task_id:<24} Type: {t.task_type:<16} Failed at attempt {t.retry_count}: {t.error_message}")


@task_group.command("retry")
@click.argument("task_id")
def task_retry(task_id: str):
    """Re-queue a dead-lettered task for processing."""
    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.async_exec.repository import AsyncTaskRepository
    from sangyan.async_exec.queue import InMemoryTaskQueue, RedisStreamTaskQueue
    repo = AsyncTaskRepository(engine)

    if config.task_queue_type == "redis_stream" and config.redis_url:
        queue = RedisStreamTaskQueue(
            redis_url=config.redis_url,
            stream_name=config.task_queue_stream,
            group_name=config.task_queue_group,
            dead_letter_stream=config.task_dead_letter_stream,
        )
    else:
        queue = InMemoryTaskQueue()

    try:
        task = repo.retry_dead_letter_task(task_id)
        queue.enqueue(task)
        click.echo(click.style(f"Task '{task_id}' successfully re-queued to status QUEUED.", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Retry failed: {e}", fg="red"), err=True)
        sys.exit(1)
    finally:
        queue.close()


@task_group.command("prune")
@click.option("--older-than-days", default=30.0, type=float, help="Retention window for terminal task rows (default 30 days)")
@click.option("--status", default=None, help="Restrict to one retention-prunable status (SUCCEEDED or CANCELLED)")
@click.option("--org", default=None, help="Restrict to a single organization ID")
@click.option("--limit", default=1000, type=int, help="Maximum rows to delete in this invocation")
@click.option("--yes", is_flag=True, default=False, help="Skip interactive confirmation")
def task_prune(older_than_days: float, status: Optional[str], org: Optional[str], limit: int, yes: bool):
    """Apply the operational-telemetry retention window to terminal task rows.

    Only SUCCEEDED/CANCELLED task ledger rows are ever removed. DEAD_LETTERED
    tasks (quarantine evidence), in-flight tasks, audit events, investigations,
    evidence, and trust receipts are never touched by this command.
    """
    if not yes:
        click.echo(
            click.style(
                f"About to DELETE terminal task rows older than {older_than_days} days"
                + (f" with status {status}" if status else " (SUCCEEDED/CANCELLED)")
                + (f" for org {org}" if org else " for all orgs")
                + ".",
                fg="yellow",
                bold=True,
            )
        )
        if not click.confirm("Proceed with retention prune?", default=False):
            click.echo(click.style("Prune cancelled; no rows removed.", fg="cyan"))
            sys.exit(0)

    config = load_config()
    engine = create_engine(config.database_url)
    if config.auto_migrate:
        MigrationRunner(engine).migrate()
    from sangyan.async_exec.repository import AsyncTaskRepository
    from sangyan.core.errors import DomainValidationError

    repo = AsyncTaskRepository(engine)
    try:
        deleted = repo.prune_tasks(
            older_than_days=older_than_days,
            status=status,
            organization_id=org,
            limit=limit,
        )
    except DomainValidationError as e:
        click.echo(click.style(f"Prune refused: {e}", fg="red"), err=True)
        sys.exit(1)
    click.echo(click.style(f"Retention prune complete: {deleted} task row(s) removed.", fg="green"))


if __name__ == "__main__":
    cli()
