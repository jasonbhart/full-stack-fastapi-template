"""LangChain tools registry for agent capabilities.

This module provides reusable LangChain tools that agents can use to
interact with the system, including database lookups and HTTP operations.

Tools are designed to be stateless and use dependency injection for
database sessions and other resources.
"""

import json
from typing import TYPE_CHECKING, Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Session, select

from app.models import Item, User

# JSON-compatible type - recursive for type checkers, simple at runtime
if TYPE_CHECKING:
    # Recursive type for static analysis
    JSONValue = dict[str, "JSONValue"] | list["JSONValue"] | str | int | float | bool | None
else:
    # Simple runtime type that Pydantic can handle
    JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None

# ============================================================================
# Database Lookup Tools
# ============================================================================


class UserLookupInput(BaseModel):
    """Input schema for user lookup tool."""

    email: str = Field(description="Email address of the user to look up")


class ItemLookupInput(BaseModel):
    """Input schema for item lookup tool."""

    item_id: str = Field(description="UUID of the item to look up")


class UserItemsLookupInput(BaseModel):
    """Input schema for user items lookup tool."""

    user_id: str = Field(description="UUID of the user whose items to retrieve")
    limit: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Maximum number of items to return (1-100)",
    )


def create_database_tools(session: Session) -> list[StructuredTool]:
    """Create database lookup tools with injected session.

    This factory function creates stateful tools with a bound database session.
    Each tool properly handles errors and returns structured data.

    Args:
        session: SQLModel database session to use for queries

    Returns:
        List of LangChain tools for database operations
    """

    def lookup_user_by_email(email: str) -> str:
        """Look up a user by their email address.

        Args:
            email: Email address of the user to find

        Returns:
            JSON string with user information or error message
        """
        try:
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                return json.dumps({"error": f"No user found with email: {email}"})

            return json.dumps(
                {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                }
            )
        except Exception as e:
            return json.dumps({"error": f"Database error: {str(e)}"})

    def lookup_item_by_id(item_id: str) -> str:
        """Look up an item by its ID.

        Args:
            item_id: UUID of the item to find

        Returns:
            JSON string with item information or error message
        """
        try:
            item = session.get(Item, item_id)
            if not item:
                return json.dumps({"error": f"No item found with ID: {item_id}"})

            return json.dumps(
                {
                    "id": str(item.id),
                    "title": item.title,
                    "description": item.description,
                    "owner_id": str(item.owner_id),
                }
            )
        except Exception as e:
            return json.dumps({"error": f"Database error: {str(e)}"})

    def lookup_user_items(user_id: str, limit: int = 10) -> str:
        """Look up all items owned by a specific user.

        Args:
            user_id: UUID of the user
            limit: Maximum number of items to return (default: 10)

        Returns:
            JSON string with list of items or error message
        """
        try:
            statement = select(Item).where(Item.owner_id == user_id).limit(limit)
            items = session.exec(statement).all()

            items_data = [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "description": item.description,
                    "owner_id": str(item.owner_id),
                }
                for item in items
            ]

            return json.dumps(
                {"count": len(items_data), "items": items_data, "limit": limit}
            )
        except Exception as e:
            return json.dumps({"error": f"Database error: {str(e)}"})

    # Create structured tools with proper schemas
    tools = [
        StructuredTool.from_function(
            func=lookup_user_by_email,
            name="lookup_user_by_email",
            description="Look up a user by their email address. Returns user details including ID, name, and status.",
            args_schema=UserLookupInput,
            handle_tool_errors=True,
        ),
        StructuredTool.from_function(
            func=lookup_item_by_id,
            name="lookup_item_by_id",
            description="Look up an item by its UUID. Returns item details including title, description, and owner.",
            args_schema=ItemLookupInput,
            handle_tool_errors=True,
        ),
        StructuredTool.from_function(
            func=lookup_user_items,
            name="lookup_user_items",
            description="Look up all items owned by a specific user. Returns a list of items with pagination.",
            args_schema=UserItemsLookupInput,
            handle_tool_errors=True,
        ),
    ]

    return tools


# ============================================================================
# HTTP Client Tools
# ============================================================================


class HTTPGetInput(BaseModel):
    """Input schema for HTTP GET tool."""

    url: str = Field(description="URL to send GET request to")
    headers: dict[str, str] | None = Field(
        default=None, description="Optional headers to include in the request"
    )
    timeout: int = Field(
        default=30, description="Request timeout in seconds (default: 30)"
    )


class HTTPPostInput(BaseModel):
    """Input schema for HTTP POST tool."""

    url: str = Field(description="URL to send POST request to")
    json_data: JSONValue = Field(
        default=None,
        description="JSON data to send in request body (dict, list, string, etc.)",
    )
    headers: dict[str, str] | None = Field(
        default=None, description="Optional headers to include in the request"
    )
    timeout: int = Field(
        default=30, description="Request timeout in seconds (default: 30)"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_json_data_before_coercion(cls, data: Any) -> Any:
        """Validate json_data before Pydantic coercion to catch non-serializable types."""
        if isinstance(data, dict) and "json_data" in data:
            json_data = data["json_data"]
            if json_data is not None:
                # Check for non-serializable types before Pydantic converts them
                if isinstance(json_data, set):
                    raise ValueError(
                        f"json_data must be valid JSON (no NaN/Infinity, must be serializable). "
                        f"Got type {type(json_data).__name__}: Object of type set is not JSON serializable"
                    )
                try:
                    # Attempt to serialize with strict JSON compliance (no NaN/Infinity)
                    json.dumps(json_data, allow_nan=False)
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"json_data must be valid JSON (no NaN/Infinity, must be serializable). "
                        f"Got type {type(json_data).__name__}: {e}"
                    ) from e
        return data

    @field_validator("json_data")
    @classmethod
    def validate_json_serializable(cls, v: Any) -> Any:
        """Ensure the data is JSON-serializable and compliant (after coercion)."""
        if v is None:
            return v
        try:
            # Attempt to serialize with strict JSON compliance (no NaN/Infinity)
            json.dumps(v, allow_nan=False)
            return v
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"json_data must be valid JSON (no NaN/Infinity, must be serializable). "
                f"Got type {type(v).__name__}: {e}"
            ) from e


@tool(args_schema=HTTPGetInput)
def http_get(
    url: str, headers: dict[str, str] | None = None, timeout: int = 30
) -> str:
    """Make an HTTP GET request to a URL.

    Args:
        url: URL to send GET request to
        headers: Optional headers to include in the request
        timeout: Request timeout in seconds (default: 30)

    Returns:
        JSON string with response data or error message
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers or {})
            response.raise_for_status()

            return json.dumps(
                {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "url": str(response.url),
                }
            )
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"HTTP error {e.response.status_code}: {e.response.text}",
                "status_code": e.response.status_code,
            }
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


@tool(args_schema=HTTPPostInput)
def http_post(
    url: str,
    json_data: JSONValue = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> str:
    """Make an HTTP POST request to a URL with JSON data.

    Args:
        url: URL to send POST request to
        json_data: JSON-serializable data to send in request body
        headers: Optional headers to include in the request
        timeout: Request timeout in seconds (default: 30)

    Returns:
        JSON string with response data or error message
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=json_data, headers=headers or {})
            response.raise_for_status()

            return json.dumps(
                {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "url": str(response.url),
                }
            )
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"HTTP error {e.response.status_code}: {e.response.text}",
                "status_code": e.response.status_code,
            }
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Request error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


# ============================================================================
# Tool Registry
# ============================================================================


def get_all_tools(session: Session | None = None) -> list[BaseTool]:
    """Get all available tools for agent use.

    This is the main entry point for retrieving tools. It combines
    database tools (if a session is provided) with HTTP tools.

    Args:
        session: Optional SQLModel database session for database tools

    Returns:
        List of all available LangChain tools
    """
    tools: list[BaseTool] = []

    # Add database tools if session is provided
    if session is not None:
        tools.extend(create_database_tools(session))

    # Add HTTP tools (stateless)
    tools.extend([http_get, http_post])

    return tools


def get_tool_by_name(
    name: str, session: Session | None = None
) -> BaseTool | None:
    """Get a specific tool by name.

    Args:
        name: Name of the tool to retrieve
        session: Optional SQLModel database session for database tools

    Returns:
        The requested tool or None if not found
    """
    all_tools = get_all_tools(session)
    for available_tool in all_tools:
        if available_tool.name == name:
            return available_tool
    return None


__all__ = [
    "create_database_tools",
    "get_all_tools",
    "get_tool_by_name",
    "http_get",
    "http_post",
    "HTTPGetInput",
    "HTTPPostInput",
    "UserLookupInput",
    "ItemLookupInput",
    "UserItemsLookupInput",
]
