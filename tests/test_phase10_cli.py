"""Phase 10: operational CLI safety — confirmation gates, scoping, retention guards.

Covers:
- `dr promote` / `dr simulate` require explicit operator intent (--yes or prompt).
- Declined confirmation performs no state change.
- `task prune` refuses non-prunable statuses (dead-letter quarantine protected).
- `task prune` deletes only aged terminal rows within the retention window.
- `task list` honors status/org filters; `task inspect` on missing id exits non-zero.
"""
import time

import pytest
from click.testing import CliRunner

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.cli import cli
from sangyan.core.errors import DomainValidationError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    db_path = tmp_path / "cli.db"
    engine = SQLiteDatabaseEngine(db_path)
    MigrationRunner(engine).migrate()
    monkeypatch.setenv("SANGYAN_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SANGYAN_ENV", "test")
    monkeypatch.setenv("SANGYAN_AUTO_MIGRATE", "false")
    yield {"engine": engine, "db_path": db_path}
    engine.close()


def _save(engine, task_id: str, status: str, completed_at=None, org: str = "org-1") -> None:
    repo = AsyncTaskRepository(engine)
    task = AsyncTask(
        task_id=task_id,
        organization_id=org,
        user_id="usr-1",
        investigation_id=f"inv-{task_id}",
        task_type=TaskType.WORKFLOW_START,
        status=status,
        payload={"contents": ["x"]},
        completed_at=completed_at,
    )
    if completed_at is not None:
        task.updated_at = completed_at
    repo.save_task(task)


def test_dr_promote_declined_prompt_changes_nothing(cli_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["dr", "promote", "standby-b"], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()

    rows = cli_env["engine"].query_all(
        "SELECT region_id, role FROM sangyan_region_fencing WHERE region_id='standby-b'"
    )
    # No standby-b region created by a declined promotion of an unregistered region
    assert rows == []


def test_dr_promote_requires_explicit_yes_for_execution(cli_env):
    runner = CliRunner()
    # Declined interactive prompt must not run the promotion
    result = runner.invoke(cli, ["dr", "promote", "never-registered"], input="n\n")
    assert result.exit_code == 0
    assert "no changes made" in result.output

    # With --yes the command attempts execution and fails closed on unregistered region
    result2 = runner.invoke(cli, ["dr", "promote", "never-registered", "--yes"])
    assert result2.exit_code == 1
    assert "Promotion failed" in result2.output


def test_dr_simulate_declined_prompt_changes_nothing(cli_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["dr", "simulate", "region-a", "region-b"], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()


def test_task_prune_refuses_dead_letter_status(cli_env):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["task", "prune", "--status", "DEAD_LETTERED", "--older-than-days", "0", "--yes"],
    )
    assert result.exit_code == 1
    assert "Prune refused" in result.output
    assert "retention-prunable" in result.output


def test_task_prune_refuses_non_terminal_status(cli_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "prune", "--status", "RUNNING", "--yes"])
    assert result.exit_code == 1
    assert "Prune refused" in result.output


def test_task_prune_deletes_only_aged_terminal_rows(cli_env):
    engine = cli_env["engine"]
    stale_success_at = time.time() - 60 * 86400  # 60 days ago
    _save(engine, "tks-old-success", TaskStatus.SUCCEEDED, completed_at=stale_success_at)
    _save(engine, "tks-new-success", TaskStatus.SUCCEEDED, completed_at=time.time())
    _save(engine, "tks-old-dl", TaskStatus.DEAD_LETTERED, completed_at=stale_success_at)
    _save(engine, "tks-old-cancel", TaskStatus.CANCELLED, completed_at=stale_success_at)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["task", "prune", "--older-than-days", "30", "--limit", "100", "--yes"],
    )
    assert result.exit_code == 0
    # Aged SUCCEEDED + aged CANCELLED are retention-prunable (2 rows)
    assert "2 task row(s) removed" in result.output

    remaining = {r["task_id"] for r in engine.query_all("SELECT task_id FROM sangyan_async_tasks")}
    assert "tks-old-success" not in remaining
    assert "tks-old-cancel" not in remaining
    assert "tks-new-success" in remaining   # inside retention window
    assert "tks-old-dl" in remaining        # dead-letter quarantine never pruned


def test_task_prune_respects_org_scope(cli_env):
    engine = cli_env["engine"]
    stale = time.time() - 60 * 86400
    _save(engine, "tks-org-a", TaskStatus.SUCCEEDED, completed_at=stale, org="org-a")
    _save(engine, "tks-org-b", TaskStatus.SUCCEEDED, completed_at=stale, org="org-b")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["task", "prune", "--older-than-days", "30", "--org", "org-a", "--yes"]
    )
    assert result.exit_code == 0
    assert "1 task row(s) removed" in result.output
    remaining = {r["task_id"] for r in engine.query_all("SELECT task_id FROM sangyan_async_tasks")}
    assert "tks-org-a" not in remaining
    assert "tks-org-b" in remaining


def test_task_inspect_missing_id_exits_nonzero(cli_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "inspect", "tsk-missing"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_task_list_filters_by_status(cli_env):
    engine = cli_env["engine"]
    _save(engine, "tks-list-a", TaskStatus.SUCCEEDED, completed_at=time.time())
    _save(engine, "tks-list-b", TaskStatus.DEAD_LETTERED, completed_at=time.time())

    runner = CliRunner()
    result = runner.invoke(cli, ["task", "list", "--status", "DEAD_LETTERED"])
    assert result.exit_code == 0
    assert "tks-list-b" in result.output
    assert "tks-list-a" not in result.output


def test_repo_prune_guard_is_defensive():
    """Repository-level guard refuses non-prunable statuses even without the CLI."""
    import tempfile
    from pathlib import Path

    tmp = tempfile.mkdtemp()
    try:
        engine = SQLiteDatabaseEngine(Path(tmp) / "guard.db")
        MigrationRunner(engine).migrate()
        repo = AsyncTaskRepository(engine)
        with pytest.raises(DomainValidationError):
            repo.prune_tasks(older_than_days=0, status="DEAD_LETTERED")
        with pytest.raises(DomainValidationError):
            repo.prune_tasks(older_than_days=0, status="RUNNING")
        engine.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
