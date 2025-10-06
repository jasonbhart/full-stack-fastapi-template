"""Pydantic schemas for agent API requests and responses.

This module defines the API contract for agent interactions, including
request/response models and pagination schemas.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field
from sqlmodel import SQLModel

# ============================================================================
# Agent Invocation Schemas
# ============================================================================


class AgentInvocationRequest(SQLModel):
    """Request schema for agent invocation.

    This schema defines the input for running an agent, including the user's
    message, optional conversation thread ID, and metadata.
    """

    message: str = Field(
        min_length=1,
        max_length=10000,
        description="User's message/prompt for the agent",
    )
    thread_id: str | None = Field(
        default=None,
        description="Optional conversation thread ID for continuity. "
        "If not provided, a new thread will be created.",
    )
    run_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata to attach to the agent run",
    )


class AgentInvocationResponse(SQLModel):
    """Response schema for agent invocation.

    This schema defines the output from running an agent, including the
    agent's response, trace IDs for observability, and execution metrics.
    """

    response: str = Field(
        description="Agent's response message",
    )
    thread_id: str = Field(
        description="Conversation thread ID for continuity",
    )
    trace_id: str | None = Field(
        default=None,
        description="Langfuse trace ID for observability correlation. "
        "None if tracing is disabled.",
    )
    trace_url: str | None = Field(
        default=None,
        description="URL to view the trace in Langfuse UI. "
        "None if tracing is disabled.",
    )
    run_id: str = Field(
        description="Unique identifier for this agent run",
    )
    latency_ms: int = Field(
        ge=0,
        description="Execution time in milliseconds",
    )
    status: str = Field(
        description="Run status (success, error, timeout, etc.)",
    )
    plan: str | None = Field(
        default=None,
        description="Execution plan created by the planner node",
    )


# ============================================================================
# Agent Run History Schemas
# ============================================================================


class AgentRunPublic(SQLModel):
    """Public schema for agent run records.

    This schema represents a single agent run from the database,
    including all relevant metadata for display in the UI.
    """

    id: uuid.UUID = Field(
        description="Unique identifier for the run",
    )
    user_id: uuid.UUID = Field(
        description="ID of the user who initiated the run",
    )
    thread_id: str = Field(
        description="Conversation thread ID",
    )
    input: str = Field(
        description="User's input message",
    )
    output: str = Field(
        description="Agent's output response",
    )
    status: str = Field(
        description="Run status (success, error, timeout, etc.)",
    )
    latency_ms: int = Field(
        ge=0,
        description="Execution time in milliseconds",
    )
    trace_id: str | None = Field(
        default=None,
        description="Langfuse trace ID for observability",
    )
    trace_url: str | None = Field(
        default=None,
        description="URL to view the trace in Langfuse UI",
    )
    created_at: datetime = Field(
        description="Timestamp when the run was created",
    )
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Number of tokens in the prompt (if available)",
    )
    completion_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Number of tokens in the completion (if available)",
    )


class AgentRunsPublic(SQLModel):
    """Paginated list of agent runs.

    This schema wraps a list of agent runs with pagination metadata,
    following the same pattern as ItemsPublic and UsersPublic.
    """

    data: list[AgentRunPublic] = Field(
        description="List of agent run records",
    )
    total: int = Field(
        ge=0,
        description="Total number of runs available for the user",
    )
    limit: int = Field(
        ge=1,
        le=1000,
        description="Maximum number of runs requested per page",
    )
    offset: int = Field(
        ge=0,
        description="Number of runs skipped (for pagination)",
    )


# ============================================================================
# Utility Schemas
# ============================================================================


class Message(SQLModel):
    """Generic message schema for simple API responses."""

    message: str = Field(
        description="Message content",
    )


class AgentHealthResponse(SQLModel):
    """Health check response for agent services."""

    status: str = Field(
        description="Service status (healthy, degraded, unhealthy)",
    )
    langfuse_enabled: bool = Field(
        description="Whether Langfuse tracing is enabled",
    )
    langfuse_configured: bool = Field(
        description="Whether Langfuse is properly configured",
    )
    model_name: str = Field(
        description="LLM model name being used",
    )
    available_tools: int = Field(
        ge=0,
        description="Number of tools available to the agent",
    )


# ============================================================================
# Evaluation Schemas
# ============================================================================


class AgentEvaluationCreate(SQLModel):
    """Request schema for creating an agent evaluation."""

    run_id: uuid.UUID = Field(
        description="UUID of the agent run to evaluate",
    )
    metric_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the evaluation metric (e.g., 'correctness', 'helpfulness')",
    )
    score: float = Field(
        description="Numerical score for the metric (typically 0.0 to 1.0)",
    )
    eval_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata for the evaluation",
    )
