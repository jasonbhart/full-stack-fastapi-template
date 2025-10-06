import uuid
from typing import Any, cast

from sqlalchemy import desc
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    AgentEvaluation,
    AgentRun,
    Item,
    ItemCreate,
    User,
    UserCreate,
    UserUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


# Agent Run CRUD Operations
def create_agent_run(
    *,
    session: Session,
    user_id: uuid.UUID,
    input: str,
    output: str | None = None,
    status: str = "pending",
    latency_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    trace_id: str | None = None,
    thread_id: str | None = None,
) -> AgentRun:
    """Create a new agent run record.

    Args:
        session: Database session
        user_id: ID of the user who initiated the run
        input: Input prompt for the agent
        output: Generated output (optional)
        status: Execution status (default: "pending")
        latency_ms: Execution time in milliseconds (optional)
        prompt_tokens: Number of prompt tokens (optional)
        completion_tokens: Number of completion tokens (optional)
        trace_id: Langfuse trace ID (optional)
        thread_id: LangGraph thread ID for conversation tracking (optional)

    Returns:
        Created AgentRun instance
    """
    db_run = AgentRun(
        user_id=user_id,
        input=input,
        output=output,
        status=status,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        trace_id=trace_id,
        thread_id=thread_id,
    )
    session.add(db_run)
    session.commit()
    session.refresh(db_run)
    return db_run


def get_agent_run(*, session: Session, run_id: uuid.UUID) -> AgentRun | None:
    """Retrieve an agent run by ID.

    Args:
        session: Database session
        run_id: ID of the agent run

    Returns:
        AgentRun instance or None if not found
    """
    statement = select(AgentRun).where(AgentRun.id == run_id)
    return session.exec(statement).first()


def get_agent_runs_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> list[AgentRun]:
    """Retrieve agent runs for a specific user with pagination and filtering.

    Args:
        session: Database session
        user_id: ID of the user
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        search: Optional search query to filter by input or output content
        status: Optional status filter (e.g., 'success', 'error', 'timeout')

    Returns:
        List of AgentRun instances ordered by creation date (newest first)
    """
    statement = (
        select(AgentRun)
        .where(AgentRun.user_id == user_id)
        .order_by(desc(cast(ColumnElement[Any], AgentRun.created_at)))
    )

    # Apply status filter if provided
    if status:
        statement = statement.where(AgentRun.status == status)

    # Apply search filter if provided (case-insensitive search in input or output)
    if search:
        search_pattern = f"%{search}%"
        statement = statement.where(
            (col(AgentRun.input).ilike(search_pattern))
            | (col(AgentRun.output).ilike(search_pattern))
        )

    statement = statement.offset(skip).limit(limit)
    return list(session.exec(statement).all())


def get_agent_runs_by_trace_id(
    *, session: Session, trace_id: str
) -> list[AgentRun]:
    """Retrieve agent runs by Langfuse trace ID.

    Args:
        session: Database session
        trace_id: Langfuse trace ID

    Returns:
        List of AgentRun instances with the specified trace ID
    """
    statement = select(AgentRun).where(AgentRun.trace_id == trace_id)
    return list(session.exec(statement).all())


def update_agent_run(
    *,
    session: Session,
    db_run: AgentRun,
    output: str | None = None,
    status: str | None = None,
    latency_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> AgentRun:
    """Update an existing agent run.

    Args:
        session: Database session
        db_run: AgentRun instance to update
        output: Updated output (optional)
        status: Updated status (optional)
        latency_ms: Updated latency (optional)
        prompt_tokens: Updated prompt tokens (optional)
        completion_tokens: Updated completion tokens (optional)

    Returns:
        Updated AgentRun instance
    """
    update_data: dict[str, Any] = {}
    if output is not None:
        update_data["output"] = output
    if status is not None:
        update_data["status"] = status
    if latency_ms is not None:
        update_data["latency_ms"] = latency_ms
    if prompt_tokens is not None:
        update_data["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        update_data["completion_tokens"] = completion_tokens

    db_run.sqlmodel_update(update_data)
    session.add(db_run)
    session.commit()
    session.refresh(db_run)
    return db_run


# Agent Evaluation CRUD Operations
def create_agent_evaluation(
    *,
    session: Session,
    run_id: uuid.UUID,
    metric_name: str,
    score: float,
    eval_metadata: dict[str, Any] | None = None,
) -> AgentEvaluation:
    """Create a new evaluation for an agent run.

    Args:
        session: Database session
        run_id: ID of the associated agent run
        metric_name: Name of the evaluation metric
        score: Numerical score for the metric
        eval_metadata: Additional evaluation data (optional)

    Returns:
        Created AgentEvaluation instance
    """
    db_eval = AgentEvaluation(
        run_id=run_id,
        metric_name=metric_name,
        score=score,
        eval_metadata=eval_metadata,
    )
    session.add(db_eval)
    session.commit()
    session.refresh(db_eval)
    return db_eval


def get_evaluations_by_run(
    *, session: Session, run_id: uuid.UUID
) -> list[AgentEvaluation]:
    """Retrieve all evaluations for a specific agent run.

    Args:
        session: Database session
        run_id: ID of the agent run

    Returns:
        List of AgentEvaluation instances ordered by creation date
    """
    statement = (
        select(AgentEvaluation)
        .where(AgentEvaluation.run_id == run_id)
        .order_by(desc(cast(ColumnElement[Any], AgentEvaluation.created_at)))
    )
    return list(session.exec(statement).all())
