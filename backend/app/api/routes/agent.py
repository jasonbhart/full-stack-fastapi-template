"""Agent API endpoints for running agents, retrieving history, and evaluations.

This module provides REST endpoints for agent operations including:
- Running agent workflows with authentication and rate limiting
- Retrieving paginated agent run history
- Triggering evaluations on agent runs
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, func, select

from app.agents.schemas import (
    AgentEvaluationCreate,
    AgentHealthResponse,
    AgentInvocationRequest,
    AgentInvocationResponse,
    AgentRunPublic,
    AgentRunsPublic,
    Message,
)
from app.agents.service import create_agent_service
from app.agents.tools import get_all_tools
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.rate_limit import (
    agent_evaluation_limiter,
    agent_history_limiter,
    agent_run_limiter,
)
from app.crud import (
    create_agent_evaluation,
    create_agent_run,
    get_agent_run,
    get_agent_runs_by_user,
)
from app.models import AgentRun

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run", response_model=AgentInvocationResponse)
async def run_agent(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: AgentInvocationRequest,
    _rate_limit: Annotated[None, Depends(agent_run_limiter)],
) -> Any:
    """
    Run an agent with the provided message.

    This endpoint executes an agent workflow with:
    - User authentication and context
    - Langfuse tracing for observability
    - Database persistence of run metadata
    - Rate limiting protection

    Args:
        session: Database session dependency
        current_user: Authenticated user from JWT token
        request: Agent invocation request containing message and optional thread_id

    Returns:
        AgentInvocationResponse with agent output, trace IDs, and execution metrics

    Raises:
        HTTPException: If agent execution fails or rate limit is exceeded
    """
    # Create agent service
    agent_service = create_agent_service(session=session)

    try:
        # Execute the agent
        result = await agent_service.run_agent(
            user=current_user,
            message=request.message,
            thread_id=request.thread_id,
            metadata=request.run_metadata,
        )

        # Persist run to database
        db_run = create_agent_run(
            session=session,
            user_id=current_user.id,
            input=request.message,
            output=result.get("response", ""),
            status=result.get("status", "success"),
            latency_ms=result.get("latency_ms"),
            trace_id=result.get("trace_id"),
            thread_id=result.get("thread_id"),
        )

        # Build trace URL if Langfuse is enabled
        trace_url = None
        if result.get("trace_id") and settings.LANGFUSE_ENABLED:
            trace_url = f"{settings.LANGFUSE_HOST}/trace/{result['trace_id']}"

        # Return response
        return AgentInvocationResponse(
            response=result["response"],
            thread_id=result["thread_id"],
            trace_id=result.get("trace_id"),
            trace_url=trace_url,
            run_id=str(db_run.id),
            latency_ms=result["latency_ms"],
            status=result["status"],
            plan=result.get("plan"),
        )

    except HTTPException:
        # Preserve HTTP exceptions (auth, validation, rate limiting, etc.)
        raise
    except Exception as e:
        # Log and convert other exceptions to 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        ) from e


@router.get("/runs", response_model=AgentRunsPublic)
def get_agent_runs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
    _rate_limit: Annotated[None, Depends(agent_history_limiter)] = None,
) -> Any:
    """
    Retrieve paginated agent run history for the current user.

    This endpoint returns agent runs ordered by creation date (newest first).
    Includes trace URLs for observability integration when Langfuse is enabled.
    Supports filtering by search query and status.

    Args:
        session: Database session dependency
        current_user: Authenticated user from JWT token
        skip: Number of records to skip for pagination (default: 0)
        limit: Maximum number of records to return (default: 100, max: 1000)
        search: Optional search query to filter by input or output content
        status: Optional status filter (e.g., 'success', 'error', 'timeout')

    Returns:
        AgentRunsPublic with paginated list of runs and total count

    Raises:
        HTTPException: If query fails
    """
    # Enforce maximum limit
    if limit > 1000:
        limit = 1000

    # Build count statement with same filters as data query
    count_statement = (
        select(func.count()).select_from(AgentRun).where(AgentRun.user_id == current_user.id)
    )

    # Apply status filter to count
    if status:
        count_statement = count_statement.where(AgentRun.status == status)

    # Apply search filter to count (case-insensitive)
    if search:
        search_pattern = f"%{search}%"
        count_statement = count_statement.where(
            (col(AgentRun.input).ilike(search_pattern))
            | (col(AgentRun.output).ilike(search_pattern))
        )

    total = session.exec(count_statement).one()

    # Get paginated runs with filters
    runs = get_agent_runs_by_user(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
    )

    # Convert to public schema with trace URLs
    runs_public = []
    for run in runs:
        trace_url = None
        if run.trace_id and settings.LANGFUSE_ENABLED:
            trace_url = f"{settings.LANGFUSE_HOST}/trace/{run.trace_id}"

        runs_public.append(
            AgentRunPublic(
                id=run.id,
                user_id=run.user_id,
                thread_id=run.thread_id or "",
                input=run.input,
                output=run.output or "",
                status=run.status,
                latency_ms=run.latency_ms or 0,
                trace_id=run.trace_id,
                trace_url=trace_url,
                created_at=run.created_at,
                prompt_tokens=run.prompt_tokens,
                completion_tokens=run.completion_tokens,
            )
        )

    return AgentRunsPublic(
        data=runs_public,
        total=total,
        limit=limit,
        offset=skip,
    )


@router.get("/runs/{run_id}", response_model=AgentRunPublic)
def get_agent_run_by_id(
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
) -> Any:
    """
    Retrieve a specific agent run by ID.

    This endpoint returns a single agent run if it exists and belongs to the current user.

    Args:
        session: Database session dependency
        current_user: Authenticated user from JWT token
        run_id: UUID of the agent run to retrieve

    Returns:
        AgentRunPublic with run details

    Raises:
        HTTPException: If run not found or doesn't belong to current user
    """
    # Get the run
    run = get_agent_run(session=session, run_id=run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    # Verify ownership
    if run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this run",
        )

    # Build trace URL if available
    trace_url = None
    if run.trace_id and settings.LANGFUSE_ENABLED:
        trace_url = f"{settings.LANGFUSE_HOST}/trace/{run.trace_id}"

    return AgentRunPublic(
        id=run.id,
        user_id=run.user_id,
        thread_id=run.thread_id or "",
        input=run.input,
        output=run.output or "",
        status=run.status,
        latency_ms=run.latency_ms or 0,
        trace_id=run.trace_id,
        trace_url=trace_url,
        created_at=run.created_at,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
    )


@router.post("/evaluations")
async def trigger_evaluation(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    evaluation_in: AgentEvaluationCreate,
    _rate_limit: Annotated[None, Depends(agent_evaluation_limiter)],
) -> Message:
    """
    Trigger an evaluation for a specific agent run.

    This endpoint creates an evaluation record for an agent run.
    The run must belong to the current user unless they are a superuser.

    Args:
        session: Database session dependency
        current_user: Authenticated user from JWT token
        evaluation_in: Evaluation request containing run_id, metric_name, score, and optional metadata

    Returns:
        Message confirming evaluation creation

    Raises:
        HTTPException: If run not found or user lacks permission
    """
    # Get the run
    run = get_agent_run(session=session, run_id=evaluation_in.run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    # Verify ownership
    if run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to evaluate this run",
        )

    # Create evaluation
    create_agent_evaluation(
        session=session,
        run_id=evaluation_in.run_id,
        metric_name=evaluation_in.metric_name,
        score=evaluation_in.score,
        eval_metadata=evaluation_in.eval_metadata,
    )

    return Message(
        message=f"Evaluation '{evaluation_in.metric_name}' created successfully for run {evaluation_in.run_id}"
    )


@router.get("/health", response_model=AgentHealthResponse)
def get_agent_health() -> Any:
    """
    Health check for agent services.

    This endpoint provides status information about agent configuration
    and available capabilities.

    Returns:
        AgentHealthResponse with service status and configuration details
    """
    # Check Langfuse configuration
    langfuse_configured = bool(
        settings.LANGFUSE_SECRET_KEY and settings.LANGFUSE_PUBLIC_KEY
    )

    # Get available tools count
    tools = get_all_tools()
    tools_count = len(tools) if tools else 0

    # Determine overall status
    status_value = "healthy"
    if not langfuse_configured and settings.LANGFUSE_ENABLED:
        status_value = "degraded"

    return AgentHealthResponse(
        status=status_value,
        langfuse_enabled=settings.LANGFUSE_ENABLED,
        langfuse_configured=langfuse_configured,
        model_name=settings.LLM_MODEL_NAME,
        available_tools=tools_count,
    )
