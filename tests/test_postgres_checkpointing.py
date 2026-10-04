"""Tests for durable PostgreSQL checkpointing and tenant thread validation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sangyan.workflow.checkpointer import (
    WorkflowCheckpointer,
    format_thread_id,
    parse_thread_id,
    validate_thread_access,
)
from sangyan.workflow.errors import TenantMismatchError


def test_format_and_parse_thread_id():
    org_id = "org_sebi_investigations"
    inv_id = "inv_ponzi_scheme_401"
    run_id = "run_20261004_step3"

    thread_id = format_thread_id(org_id, inv_id, run_id)
    assert thread_id == "org_sebi_investigations:inv_ponzi_scheme_401:run_20261004_step3"

    parsed_org, parsed_inv, parsed_run = parse_thread_id(thread_id)
    assert parsed_org == org_id
    assert parsed_inv == inv_id
    assert parsed_run == run_id


def test_parse_invalid_thread_id():
    with pytest.raises(ValueError) as excinfo:
        parse_thread_id("invalid_format_without_three_parts")
    assert "Invalid thread_id format" in str(excinfo.value)


def test_validate_thread_access_success():
    thread_id = "org_authorized:inv_123:run_1"
    # Should not raise
    validate_thread_access(thread_id, caller_organization_id="org_authorized")


def test_validate_thread_access_rejection():
    thread_id = "org_victim:inv_confidential:run_9"
    with pytest.raises(TenantMismatchError) as excinfo:
        validate_thread_access(thread_id, caller_organization_id="org_attacker")
    assert "Access denied" in str(excinfo.value)
    assert "org_victim" in str(excinfo.value)
    assert "org_attacker" in str(excinfo.value)


def test_postgres_checkpointer_initialization():
    checkpointer = WorkflowCheckpointer(postgres_url="postgresql://user:pass@localhost:5432/sangyandb")
    assert checkpointer.is_postgres is True
    assert checkpointer.postgres_url == "postgresql://user:pass@localhost:5432/sangyandb"


def test_postgres_checkpointer_saver_setup():
    mock_conn = MagicMock()
    checkpointer = WorkflowCheckpointer(conn=mock_conn)
    assert checkpointer.is_postgres is True

    with patch("langgraph.checkpoint.postgres.PostgresSaver") as mock_saver_cls:
        mock_instance = MagicMock()
        mock_saver_cls.return_value = mock_instance

        saver = checkpointer.get_saver()
        assert saver is mock_instance
        # Verify setup() is invoked to ensure checkpoint tables are created
        mock_instance.setup.assert_called_once()
