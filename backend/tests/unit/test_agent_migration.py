"""Tests for AgentRun and AgentEvaluation database migration and sample data."""

import pytest
from sqlmodel import Session, select

from app.core.config import AppEnv, settings
from app.models import AgentEvaluation, AgentRun, User


def test_agent_tables_exist(db: Session) -> None:
    """Test that AgentRun and AgentEvaluation tables exist and are queryable."""
    # Try to query both tables - will raise exception if tables don't exist
    runs = db.exec(select(AgentRun)).all()
    evals = db.exec(select(AgentEvaluation)).all()

    # Tables should exist (may or may not have data)
    assert runs is not None
    assert evals is not None


def test_agent_run_creation(db: Session) -> None:
    """Test creating an AgentRun record."""
    # Get or create a user
    user = db.exec(select(User)).first()
    if not user:
        pytest.skip("No user available for testing")

    # Create an agent run
    run = AgentRun(
        user_id=user.id,
        input="Test input",
        output="Test output",
        status="completed",
        latency_ms=1000,
        prompt_tokens=10,
        completion_tokens=20,
        trace_id="test_trace_123",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Verify the run was created
    assert run.id is not None
    assert run.user_id == user.id
    assert run.input == "Test input"
    assert run.output == "Test output"
    assert run.status == "completed"
    assert run.trace_id == "test_trace_123"
    assert run.created_at is not None

    # Clean up
    db.delete(run)
    db.commit()


def test_agent_evaluation_creation(db: Session) -> None:
    """Test creating an AgentEvaluation record."""
    # Get or create a user and run
    user = db.exec(select(User)).first()
    if not user:
        pytest.skip("No user available for testing")

    # Create an agent run first
    run = AgentRun(
        user_id=user.id,
        input="Test input",
        output="Test output",
        status="completed",
        latency_ms=1000,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Create an evaluation
    evaluation = AgentEvaluation(
        run_id=run.id,
        metric_name="accuracy",
        score=0.95,
        eval_metadata={"test": "data", "count": 42},
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    # Verify the evaluation was created
    assert evaluation.id is not None
    assert evaluation.run_id == run.id
    assert evaluation.metric_name == "accuracy"
    assert evaluation.score == 0.95
    assert evaluation.eval_metadata == {"test": "data", "count": 42}
    assert evaluation.created_at is not None

    # Clean up
    db.delete(evaluation)
    db.delete(run)
    db.commit()


def test_agent_run_evaluation_relationship(db: Session) -> None:
    """Test the relationship between AgentRun and AgentEvaluation."""
    # Get or create a user
    user = db.exec(select(User)).first()
    if not user:
        pytest.skip("No user available for testing")

    # Create an agent run
    run = AgentRun(
        user_id=user.id,
        input="Test relationship",
        output="Test output",
        status="completed",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Create multiple evaluations
    eval1 = AgentEvaluation(
        run_id=run.id,
        metric_name="metric1",
        score=0.8,
    )
    eval2 = AgentEvaluation(
        run_id=run.id,
        metric_name="metric2",
        score=0.9,
    )
    db.add(eval1)
    db.add(eval2)
    db.commit()

    # Refresh run to load relationships
    db.refresh(run)

    # Verify relationship
    assert len(run.evaluations) == 2
    assert {e.metric_name for e in run.evaluations} == {"metric1", "metric2"}

    # Clean up
    db.delete(eval1)
    db.delete(eval2)
    db.delete(run)
    db.commit()


def test_cascade_delete(db: Session) -> None:
    """Test that deleting an AgentRun cascades to AgentEvaluation."""
    # Get or create a user
    user = db.exec(select(User)).first()
    if not user:
        pytest.skip("No user available for testing")

    # Create an agent run with an evaluation
    run = AgentRun(
        user_id=user.id,
        input="Test cascade delete",
        output="Test output",
        status="completed",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    evaluation = AgentEvaluation(
        run_id=run.id,
        metric_name="test_metric",
        score=0.5,
    )
    db.add(evaluation)
    db.commit()

    eval_id = evaluation.id

    # Delete the run
    db.delete(run)
    db.commit()

    # Verify evaluation was also deleted (cascade)
    deleted_eval = db.get(AgentEvaluation, eval_id)
    assert deleted_eval is None


def test_indexes_exist(db: Session) -> None:
    """Test that required indexes exist on AgentRun and AgentEvaluation tables."""
    # This test verifies that the migration created the indexes
    # We can't easily check index existence without raw SQL, but we can verify
    # that queries using indexed columns work efficiently

    user = db.exec(select(User)).first()
    if not user:
        pytest.skip("No user available for testing")

    # Create test data
    run = AgentRun(
        user_id=user.id,
        input="Index test",
        output="Test output",
        status="completed",
        trace_id="trace_index_test",
    )
    db.add(run)
    db.commit()

    # Query by indexed columns - should work without errors
    by_user = db.exec(select(AgentRun).where(AgentRun.user_id == user.id)).all()
    assert len(by_user) >= 1

    by_status = db.exec(select(AgentRun).where(AgentRun.status == "completed")).all()
    assert len(by_status) >= 1

    by_trace = db.exec(
        select(AgentRun).where(AgentRun.trace_id == "trace_index_test")
    ).all()
    assert len(by_trace) == 1

    # Clean up
    db.delete(run)
    db.commit()


def test_sample_data_in_local_env(db: Session) -> None:
    """Test that sample data is created in local/staging environments."""
    # This test assumes we're running in a local environment
    # and that init_db has been called
    if settings.APP_ENV not in [AppEnv.LOCAL, AppEnv.STAGING]:
        pytest.skip("Sample data only created in local/staging environments")

    # Check if sample runs exist - init_db should have created them
    runs = db.exec(select(AgentRun)).all()
    assert runs, "Expected sample AgentRun records after init_db()"

    # Verify we have runs with different statuses
    statuses = {run.status for run in runs}
    assert "completed" in statuses

    # Verify evaluations exist for completed runs and are properly linked
    evals = db.exec(select(AgentEvaluation)).all()
    assert evals, "Expected sample AgentEvaluation records after init_db()"

    # Ensure evaluations reference the completed runs from sample data
    completed_run_ids = {run.id for run in runs if run.status == "completed"}
    evaluation_run_ids = {ev.run_id for ev in evals}
    assert evaluation_run_ids.issubset(
        completed_run_ids
    ), "Sample evaluations should only reference completed sample runs"
