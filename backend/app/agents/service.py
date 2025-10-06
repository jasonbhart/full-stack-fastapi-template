"""Agent service orchestration layer.

This module provides the high-level service interface for agent operations,
including execution orchestration, tracing, and run metadata persistence.
"""

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from sqlmodel import Session

from app.agents.graph import ainvoke_agent
from app.core import logging as app_logging
from app.core.config import settings
from app.models import User

# Conditional import for Langfuse (optional dependency)
if TYPE_CHECKING:
    from langfuse.callback import CallbackHandler  # type: ignore[import-not-found]
else:
    try:
        from langfuse.callback import CallbackHandler  # type: ignore[import-not-found]
    except ImportError:
        CallbackHandler = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


class AgentService:
    """Service for orchestrating agent execution with tracing and persistence.

    This service provides a high-level interface for agent operations that:
    - Resolves authenticated user context
    - Creates and manages Langfuse traces
    - Invokes LangGraph workflows with proper configuration
    - Persists run metadata to the database (when models are available)
    """

    def __init__(self, session: Session):
        """Initialize the agent service.

        Args:
            session: SQLModel database session for persistence and tool access
        """
        self.session = session

    def _create_langfuse_handler(
        self,
        user_id: str,
        trace_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create a Langfuse callback handler for tracing.

        Args:
            user_id: ID of the user for trace correlation
            trace_name: Optional name for the trace
            metadata: Optional metadata to attach to the trace

        Returns:
            CallbackHandler if Langfuse is enabled and available, None otherwise
        """
        # Check if Langfuse package is installed
        if CallbackHandler is None:
            logger.debug("Langfuse package not installed, tracing disabled")
            return None

        if not settings.LANGFUSE_ENABLED:
            return None

        if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
            return None

        try:
            handler = CallbackHandler(
                secret_key=settings.LANGFUSE_SECRET_KEY,
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                host=settings.LANGFUSE_HOST,
                sample_rate=settings.LANGFUSE_SAMPLE_RATE,
            )

            # Set trace metadata (copy to avoid mutating caller's dict)
            trace_metadata = dict(metadata or {})
            trace_metadata["user_id"] = user_id
            trace_metadata["app_env"] = settings.APP_ENV.value

            # Start a new trace
            handler.trace = handler.langfuse.trace(
                name=trace_name or "agent_run",
                user_id=user_id,
                metadata=trace_metadata,
            )

            return handler
        except Exception as e:
            # Log the error but don't fail the agent execution
            logger.warning("Failed to create Langfuse handler: %s", e)
            return None

    async def run_agent(
        self,
        user: User,
        message: str,
        thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an agent with user context and tracing.

        This method orchestrates the complete agent execution workflow:
        1. Resolves user context from the authenticated user
        2. Creates a Langfuse trace for observability
        3. Invokes the LangGraph workflow with tools
        4. Persists run metadata to the database
        5. Returns the agent response with trace information

        Args:
            user: Authenticated user from the request
            message: User's message/prompt for the agent
            thread_id: Optional conversation thread ID for continuity
            metadata: Optional metadata to attach to the run

        Returns:
            Dict containing:
                - response: Agent's response message
                - thread_id: Conversation thread ID (for continuity)
                - trace_id: Langfuse trace ID (if tracing enabled)
                - run_id: Database run ID (when persistence is implemented)
                - latency_ms: Execution time in milliseconds
                - status: Run status (success, error)

        Raises:
            Exception: If agent execution fails
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())
        user_id = str(user.id)

        # Generate thread_id if not provided
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        # Create Langfuse handler for tracing
        trace_metadata = {
            "run_id": run_id,
            "thread_id": thread_id,
            "user_email": user.email,
            **(metadata or {}),
        }
        langfuse_handler = self._create_langfuse_handler(
            user_id=user_id,
            trace_name="agent_execution",
            metadata=trace_metadata,
        )

        # Prepare callbacks for LangGraph
        callbacks = [langfuse_handler] if langfuse_handler else None

        # Set trace ID in logging context if available
        if langfuse_handler and hasattr(langfuse_handler, "trace"):
            try:
                trace_id = langfuse_handler.trace.id
                app_logging.set_trace_id(trace_id)
                logger.info(f"Starting agent execution with trace_id: {trace_id}")
            except Exception as e:
                logger.debug(f"Failed to set trace ID in logging context: {e}")

        try:
            # Invoke the agent graph
            result = await ainvoke_agent(
                message=message,
                user_id=user_id,
                thread_id=thread_id,
                session=self.session,
                callbacks=callbacks,
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract the response from the result
            messages = result.get("messages", [])
            response_content = ""
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "content"):
                    content = last_message.content
                    # Handle content that can be str or list
                    response_content = content if isinstance(content, str) else str(content)
                else:
                    response_content = str(last_message)

            # Get trace ID if available
            trace_id = None
            if langfuse_handler and hasattr(langfuse_handler, "trace"):
                trace_id = langfuse_handler.trace.id

            # TODO (Task #8): Persist run metadata to AgentRun table
            # Once AgentRun model is created in task #8, add:
            # - Create AgentRun record with:
            #   - id: run_id
            #   - user_id: user.id
            #   - thread_id: thread_id
            #   - input: message
            #   - output: response_content
            #   - status: "success"
            #   - latency_ms: latency_ms
            #   - trace_id: trace_id
            #   - created_at: timestamp
            # - Commit to database
            # - Handle token counting if available from result

            return {
                "response": response_content,
                "thread_id": thread_id,
                "trace_id": trace_id,
                "run_id": run_id,
                "latency_ms": latency_ms,
                "status": "success",
                "plan": result.get("plan"),
            }

        except Exception:
            # Calculate latency even for errors
            latency_ms = int((time.time() - start_time) * 1000)

            # Get trace ID if available
            trace_id = None
            if langfuse_handler and hasattr(langfuse_handler, "trace"):
                trace_id = langfuse_handler.trace.id

            # TODO (Task #8): Persist error run to AgentRun table
            # - Create AgentRun record with status: "error"
            # - Include error message in metadata

            # Log the failure and re-raise original exception to preserve type/context
            logger.exception("Agent execution failed")
            raise

        finally:
            # Note: Context cleanup (correlation_id and trace_id) is handled by
            # CorrelationIDMiddleware in its finally block after response headers
            # are set. Do NOT clear trace_id here or it won't appear in response headers.

            # Flush Langfuse events
            if langfuse_handler and hasattr(langfuse_handler, "langfuse"):
                try:
                    langfuse_handler.langfuse.flush()
                except Exception:
                    pass  # Ignore flush errors

    async def get_run_history(
        self,
        user: User,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Retrieve agent run history for a user.

        Args:
            user: Authenticated user
            limit: Maximum number of runs to return
            offset: Number of runs to skip (for pagination)

        Returns:
            Dict containing:
                - runs: List of run records
                - total: Total number of runs for the user
                - limit: Requested limit
                - offset: Requested offset

        Note:
            This method currently returns a placeholder response.
            Full implementation depends on AgentRun model from task #8.
        """
        # user_id will be used when querying AgentRun table in Task #8
        # user_id = str(user.id)

        # TODO (Task #8): Query AgentRun table for user's runs
        # user_id = str(user.id)
        # - SELECT * FROM agent_run WHERE user_id = :user_id
        # - ORDER BY created_at DESC
        # - LIMIT :limit OFFSET :offset
        # - Return runs with trace URLs

        return {
            "runs": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "message": "Run history will be available after AgentRun model is created (Task #8)",
        }

    async def get_run_by_id(
        self,
        user: User,
        run_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a specific agent run by ID.

        Args:
            user: Authenticated user
            run_id: ID of the run to retrieve

        Returns:
            Run record if found and belongs to user, None otherwise

        Note:
            This method currently returns None.
            Full implementation depends on AgentRun model from task #8.
        """
        # user_id will be used when querying AgentRun table in Task #8
        # user_id = str(user.id)

        # TODO (Task #8): Query AgentRun table for specific run
        # user_id = str(user.id)
        # - SELECT * FROM agent_run WHERE id = :run_id AND user_id = :user_id
        # - Return run with trace URL

        return None


def create_agent_service(session: Session) -> AgentService:
    """Factory function to create an AgentService instance.

    Args:
        session: SQLModel database session

    Returns:
        Configured AgentService instance
    """
    return AgentService(session=session)


__all__ = [
    "AgentService",
    "create_agent_service",
]
