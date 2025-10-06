"""LangGraph workflow definitions for agent orchestration.

This module defines the LangGraph state graph with nodes for planning,
execution, and conversation memory management. It integrates Langfuse
tracing callbacks and persists conversation history to PostgreSQL.
"""

import uuid
from typing import Any, Annotated, Literal, Sequence, TypedDict, cast

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr
from sqlmodel import Session

from app.agents.tools import get_all_tools
from app.core.config import settings


# ============================================================================
# State Definitions
# ============================================================================


class AgentState(TypedDict):
    """State for the agent graph with conversation history.

    Attributes:
        messages: List of conversation messages (automatically merged)
        plan: Current execution plan from the planner
        user_id: ID of the user for this conversation thread
    """

    messages: Annotated[list[BaseMessage], add_messages]
    plan: str | None
    user_id: str | None


# ============================================================================
# Node Functions
# ============================================================================


def planner_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:  # noqa: ARG001
    """Planner node that analyzes the user request and creates an execution plan.

    This node examines the conversation history and current user message to
    determine what needs to be done and creates a plan for execution.

    Args:
        state: Current agent state with conversation history
        config: Runtime configuration

    Returns:
        Dict with updated plan and execution status
    """
    messages = state["messages"]

    # Create a planning prompt
    system_prompt = SystemMessage(
        content="""You are an AI planning assistant. Analyze the user's request and create a concise execution plan.

Your plan should:
1. Identify the key tasks needed to fulfill the request
2. Determine which tools (if any) are needed
3. Outline the steps in a clear, logical order

Keep the plan brief and actionable. If the request is simple (like a greeting or question),
indicate that no complex execution is needed.

Available tools: database lookups (users, items), HTTP requests (GET, POST)
"""
    )

    # Get the LLM (without tools for planning)
    api_key = SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    model = ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        temperature=settings.LLM_TEMPERATURE,
        api_key=api_key,
    )

    # Create plan
    planning_messages = [system_prompt] + messages
    response = model.invoke(planning_messages)

    plan = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "plan": plan,
        "messages": [response],
    }


def executor_node(
    state: AgentState,
    config: RunnableConfig,  # noqa: ARG001
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    """Executor node that carries out the plan using available tools.

    This node invokes the LLM with access to tools. If the LLM requests tools,
    they will be executed by the separate tool_executor node.

    Args:
        state: Current agent state with plan and conversation history
        config: Runtime configuration
        session: Optional database session for tool access

    Returns:
        Dict with the LLM response (may include tool calls)
    """
    messages = state["messages"]
    plan = state.get("plan", "No specific plan - respond naturally")

    # Create execution system prompt
    system_prompt = SystemMessage(
        content=f"""You are a helpful AI assistant. You have access to tools for database lookups and HTTP requests.

Current execution plan: {plan}

Follow the plan to help the user. Be concise and helpful. If you need to use tools, use them.
If the request is simple, just respond naturally without overthinking.
"""
    )

    # Get the LLM with tools
    api_key = SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    llm = ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        temperature=settings.LLM_TEMPERATURE,
        api_key=api_key,
    )

    # Bind tools to the model
    tools = get_all_tools(session)
    if tools:
        model_with_tools = llm.bind_tools(tools)
    else:
        model_with_tools = llm

    # Execute with tools - just invoke the model
    execution_messages = [system_prompt] + messages
    response = model_with_tools.invoke(execution_messages)

    # Return the response - routing logic will decide if we need to execute tools
    return {
        "messages": [response],
    }


def should_continue(state: AgentState) -> Literal["executor", "end"]:  # noqa: ARG001
    """Conditional edge function to determine next step after planning.

    Args:
        state: Current agent state

    Returns:
        Next node name or "end"
    """
    # Simple logic: always execute after planning
    # In a more complex system, you might skip execution for simple queries
    return "executor"


def route_after_executor(state: AgentState) -> Literal["tool_executor", "end"]:
    """Route after executor based on whether tools need to be called.

    Args:
        state: Current agent state with messages

    Returns:
        "tool_executor" if tools need to be called, "end" otherwise
    """
    messages = state["messages"]
    last_message = messages[-1]

    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tool_executor"

    # No tools to execute, we're done
    return "end"


# ============================================================================
# Graph Construction
# ============================================================================


def create_agent_graph(
    session: Session | None = None,
    checkpointer: PostgresSaver | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Create and compile the agent graph with planner and executor nodes.

    This function builds a LangGraph StateGraph with:
    - Planner node: Analyzes requests and creates execution plans
    - Executor node: Invokes LLM with tools
    - Tool executor node: Executes tool calls and returns results
    - Conditional routing: Routes to tools when needed, loops back to executor
    - PostgreSQL checkpointing: Persists conversation history

    Args:
        session: Optional database session for tool access
        checkpointer: Optional PostgreSQL checkpointer for persistence

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create the graph
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("planner", planner_node)

    # Wrap executor to inject session if provided
    def executor_with_session(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        return executor_node(state, config, session=session)

    builder.add_node("executor", executor_with_session)

    # Add tool executor node using LangGraph's prebuilt ToolNode
    tools = get_all_tools(session)
    if tools:
        tool_node = ToolNode(tools)
        builder.add_node("tool_executor", tool_node)

    # Add edges
    builder.add_edge(START, "planner")
    builder.add_conditional_edges(
        "planner",
        should_continue,
        {
            "executor": "executor",
            "end": END,
        },
    )

    # Route after executor: if tools are called, execute them; otherwise end
    if tools:
        builder.add_conditional_edges(
            "executor",
            route_after_executor,
            {
                "tool_executor": "tool_executor",
                "end": END,
            },
        )
        # After tool execution, go back to executor to process results
        builder.add_edge("tool_executor", "executor")
    else:
        # No tools available, just end after executor
        builder.add_edge("executor", END)

    # Compile with checkpointer if provided
    if checkpointer:
        compiled_graph = builder.compile(checkpointer=checkpointer)
    else:
        compiled_graph = builder.compile()

    # Cast to the correct type - builder.compile() returns a generic StateT but we know
    # the concrete type is AgentState since we created StateGraph(AgentState)
    return cast(CompiledStateGraph[AgentState, None, AgentState, AgentState], compiled_graph)


def _get_connection_string() -> str:
    """Get PostgreSQL connection string for checkpointer.

    Returns:
        PostgreSQL connection string compatible with psycopg
    """
    # Convert PostgresDsn to string for langgraph
    # Remove SQLAlchemy driver suffix (+psycopg) if present, as psycopg doesn't understand it
    return str(settings.SQLALCHEMY_DATABASE_URI).replace(
        "postgresql+psycopg://", "postgresql://"
    )


def invoke_agent(
    message: str,
    user_id: str,
    thread_id: str | None = None,
    session: Session | None = None,
    callbacks: Sequence[BaseCallbackHandler] | None = None,
) -> AgentState:
    """Invoke the agent graph with a user message.

    This is a convenience function that handles:
    - Creating the graph with checkpointing
    - Setting up the configuration with thread_id and user_id
    - Invoking the graph with the message
    - Integrating Langfuse callbacks if provided

    Args:
        message: User message to process
        user_id: ID of the user (for memory namespacing)
        thread_id: Optional conversation thread ID (generated if not provided)
        session: Optional database session for tool access
        callbacks: Optional Langfuse callbacks for tracing

    Returns:
        Final state of the graph execution
    """
    # Generate thread_id if not provided
    if thread_id is None:
        thread_id = str(uuid.uuid4())

    # Use checkpointer context manager for proper connection lifecycle
    connection_string = _get_connection_string()
    with PostgresSaver.from_conn_string(connection_string) as checkpointer:
        checkpointer.setup()

        # Create graph
        graph = create_agent_graph(session=session, checkpointer=checkpointer)

        # Set up configuration
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            },
        }

        # Add callbacks if provided (for Langfuse tracing)
        if callbacks:
            config["callbacks"] = list(callbacks)

        # Invoke the graph
        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "plan": None,
            "user_id": user_id,
        }

        result = cast(AgentState, graph.invoke(initial_state, config))

        return result


async def ainvoke_agent(
    message: str,
    user_id: str,
    thread_id: str | None = None,
    session: Session | None = None,
    callbacks: Sequence[BaseCallbackHandler] | None = None,
) -> AgentState:
    """Async version of invoke_agent.

    Args:
        message: User message to process
        user_id: ID of the user (for memory namespacing)
        thread_id: Optional conversation thread ID (generated if not provided)
        session: Optional database session for tool access
        callbacks: Optional Langfuse callbacks for tracing

    Returns:
        Final state of the graph execution
    """
    # Generate thread_id if not provided
    if thread_id is None:
        thread_id = str(uuid.uuid4())

    # Use checkpointer context manager for proper connection lifecycle
    connection_string = _get_connection_string()
    with PostgresSaver.from_conn_string(connection_string) as checkpointer:
        checkpointer.setup()

        # Create graph
        graph = create_agent_graph(session=session, checkpointer=checkpointer)

        # Set up configuration
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            },
        }

        # Add callbacks if provided (for Langfuse tracing)
        if callbacks:
            config["callbacks"] = list(callbacks)

        # Invoke the graph asynchronously
        initial_state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "plan": None,
            "user_id": user_id,
        }

        result = cast(AgentState, await graph.ainvoke(initial_state, config))

        return result


def get_conversation_history(
    thread_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve conversation history for a thread.

    Args:
        thread_id: Conversation thread ID
        limit: Optional limit on number of checkpoints to retrieve

    Returns:
        List of state snapshots in chronological order
    """
    # Use checkpointer context manager for proper connection lifecycle
    connection_string = _get_connection_string()
    with PostgresSaver.from_conn_string(connection_string) as checkpointer:
        checkpointer.setup()
        graph = create_agent_graph(checkpointer=checkpointer)

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        history = []
        for state in graph.get_state_history(config):
            history.append({
                "values": state.values,
                "created_at": state.created_at,
                "metadata": state.metadata,
                "config": state.config,
            })

            if limit and len(history) >= limit:
                break

        return history


__all__ = [
    "AgentState",
    "create_agent_graph",
    "invoke_agent",
    "ainvoke_agent",
    "get_conversation_history",
    "planner_node",
    "executor_node",
    "route_after_executor",
]
