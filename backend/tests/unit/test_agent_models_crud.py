"""Unit tests for agent models and CRUD operations."""

import uuid
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.crud import (
    create_agent_evaluation,
    create_agent_run,
    get_agent_run,
    get_agent_runs_by_trace_id,
    get_agent_runs_by_user,
    get_evaluations_by_run,
    update_agent_run,
)
from app.models import AgentEvaluation, AgentRun, User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user for agent run tests."""
    # Use the first available user from db initialization
    from app import crud
    from app.core.config import settings

    user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user is not None
    return user


def test_create_agent_run(db: Session, test_user: User) -> None:
    """Test creating an agent run."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Test prompt",
        output="Test output",
        status="completed",
        latency_ms=1500,
        prompt_tokens=10,
        completion_tokens=20,
        trace_id="test-trace-123",
    )

    assert run.id is not None
    assert run.user_id == test_user.id
    assert run.input == "Test prompt"
    assert run.output == "Test output"
    assert run.status == "completed"
    assert run.latency_ms == 1500
    assert run.prompt_tokens == 10
    assert run.completion_tokens == 20
    assert run.trace_id == "test-trace-123"
    assert isinstance(run.created_at, datetime)


def test_create_agent_run_minimal(db: Session, test_user: User) -> None:
    """Test creating an agent run with minimal required fields."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Minimal test prompt",
    )

    assert run.id is not None
    assert run.user_id == test_user.id
    assert run.input == "Minimal test prompt"
    assert run.output is None
    assert run.status == "pending"
    assert run.latency_ms is None
    assert run.prompt_tokens is None
    assert run.completion_tokens is None
    assert run.trace_id is None


def test_get_agent_run(db: Session, test_user: User) -> None:
    """Test retrieving an agent run by ID."""
    created_run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Test retrieval",
    )

    retrieved_run = get_agent_run(session=db, run_id=created_run.id)

    assert retrieved_run is not None
    assert retrieved_run.id == created_run.id
    assert retrieved_run.input == "Test retrieval"


def test_get_agent_run_not_found(db: Session) -> None:
    """Test retrieving a non-existent agent run."""
    non_existent_id = uuid.uuid4()
    run = get_agent_run(session=db, run_id=non_existent_id)

    assert run is None


def test_get_agent_runs_by_user(db: Session, test_user: User) -> None:
    """Test retrieving all agent runs for a user."""
    # Create multiple runs
    run1 = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="First run",
    )
    run2 = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Second run",
    )

    runs = get_agent_runs_by_user(session=db, user_id=test_user.id)

    assert len(runs) >= 2
    # Verify runs are ordered by created_at descending (newest first)
    run_ids = [r.id for r in runs]
    assert run2.id in run_ids
    assert run1.id in run_ids


def test_get_agent_runs_by_user_pagination(db: Session, test_user: User) -> None:
    """Test pagination when retrieving user's agent runs."""
    # Create several runs
    for i in range(5):
        create_agent_run(
            session=db,
            user_id=test_user.id,
            input=f"Pagination test run {i}",
        )

    # Test skip and limit
    first_page = get_agent_runs_by_user(session=db, user_id=test_user.id, skip=0, limit=2)
    second_page = get_agent_runs_by_user(session=db, user_id=test_user.id, skip=2, limit=2)

    assert len(first_page) == 2
    assert len(second_page) == 2
    # Ensure pages have different runs
    first_page_ids = {r.id for r in first_page}
    second_page_ids = {r.id for r in second_page}
    assert first_page_ids.isdisjoint(second_page_ids)


def test_get_agent_runs_by_trace_id(db: Session, test_user: User) -> None:
    """Test retrieving agent runs by Langfuse trace ID."""
    trace_id = "unique-trace-456"

    run1 = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Run with trace",
        trace_id=trace_id,
    )

    runs = get_agent_runs_by_trace_id(session=db, trace_id=trace_id)

    assert len(runs) >= 1
    assert run1.id in [r.id for r in runs]


def test_update_agent_run(db: Session, test_user: User) -> None:
    """Test updating an agent run."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Test update",
        status="pending",
    )

    updated_run = update_agent_run(
        session=db,
        db_run=run,
        output="Updated output",
        status="completed",
        latency_ms=2000,
        prompt_tokens=15,
        completion_tokens=30,
    )

    assert updated_run.id == run.id
    assert updated_run.output == "Updated output"
    assert updated_run.status == "completed"
    assert updated_run.latency_ms == 2000
    assert updated_run.prompt_tokens == 15
    assert updated_run.completion_tokens == 30
    assert updated_run.input == "Test update"  # Unchanged field


def test_update_agent_run_partial(db: Session, test_user: User) -> None:
    """Test partially updating an agent run."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Partial update test",
        status="pending",
        latency_ms=1000,
    )

    updated_run = update_agent_run(
        session=db,
        db_run=run,
        status="running",
    )

    assert updated_run.status == "running"
    assert updated_run.latency_ms == 1000  # Unchanged


def test_create_agent_evaluation(db: Session, test_user: User) -> None:
    """Test creating an evaluation for an agent run."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Run for evaluation",
    )

    evaluation = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="accuracy",
        score=0.95,
        eval_metadata={"evaluator": "test", "notes": "Great performance"},
    )

    assert evaluation.id is not None
    assert evaluation.run_id == run.id
    assert evaluation.metric_name == "accuracy"
    assert evaluation.score == 0.95
    assert evaluation.eval_metadata == {"evaluator": "test", "notes": "Great performance"}
    assert isinstance(evaluation.created_at, datetime)


def test_create_agent_evaluation_minimal(db: Session, test_user: User) -> None:
    """Test creating an evaluation with minimal fields."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Minimal evaluation run",
    )

    evaluation = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="relevance",
        score=0.8,
    )

    assert evaluation.id is not None
    assert evaluation.eval_metadata is None


def test_get_evaluations_by_run(db: Session, test_user: User) -> None:
    """Test retrieving all evaluations for a run."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Multi-evaluation run",
    )

    eval1 = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="accuracy",
        score=0.9,
    )
    eval2 = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="relevance",
        score=0.85,
    )

    evaluations = get_evaluations_by_run(session=db, run_id=run.id)

    assert len(evaluations) >= 2
    eval_ids = [e.id for e in evaluations]
    assert eval1.id in eval_ids
    assert eval2.id in eval_ids


def test_agent_run_evaluation_relationship(db: Session, test_user: User) -> None:
    """Test the relationship between AgentRun and AgentEvaluation."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Relationship test",
    )

    evaluation = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="coherence",
        score=0.88,
    )

    # Refresh to load relationships
    db.refresh(run)
    db.refresh(evaluation)

    # Test back_populates relationship
    assert evaluation.run is not None
    assert evaluation.run.id == run.id
    assert len(run.evaluations) >= 1
    assert evaluation.id in [e.id for e in run.evaluations]


def test_cascade_delete(db: Session, test_user: User) -> None:
    """Test that deleting a run cascades to its evaluations."""
    run = create_agent_run(
        session=db,
        user_id=test_user.id,
        input="Cascade delete test",
    )

    evaluation = create_agent_evaluation(
        session=db,
        run_id=run.id,
        metric_name="test_metric",
        score=0.75,
    )

    run_id = run.id
    eval_id = evaluation.id

    # Delete the run
    db.delete(run)
    db.commit()

    # Verify run is deleted
    deleted_run = get_agent_run(session=db, run_id=run_id)
    assert deleted_run is None

    # Verify evaluation is also deleted (cascade)
    from sqlmodel import select

    statement = select(AgentEvaluation).where(AgentEvaluation.id == eval_id)
    deleted_eval = db.exec(statement).first()
    assert deleted_eval is None


def test_server_defaults_for_raw_sql_inserts(db: Session, test_user: User) -> None:
    """Test that database-level defaults work for raw SQL inserts.

    This validates that the Alembic migration correctly set server_default
    values for status and created_at columns.
    """
    from app.core.db import engine

    run_id = uuid.uuid4()

    # Insert using raw SQL without providing status or created_at
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO agentrun (id, user_id, input)
                VALUES (:id, :user_id, :input)
            """),
            {"id": run_id, "user_id": test_user.id, "input": "Raw SQL test"},
        )
        conn.commit()

    # Verify the row was created with defaults
    run = get_agent_run(session=db, run_id=run_id)
    assert run is not None
    assert run.status == "pending", "Database default for status should be 'pending'"
    assert run.created_at is not None, "Database default for created_at should be set"
    assert isinstance(run.created_at, datetime)

    # Clean up
    db.delete(run)
    db.commit()
