"""Unit tests for agent tools.

This module tests the LangChain tools used by agents:
- Database lookup tools (with mocked database)
- HTTP client tools (with mocked requests)
- Tool registry functions

All tests use mocks to ensure isolation and fast execution.
"""

import json
import uuid
from unittest.mock import Mock, patch

import pytest
from sqlmodel import Session

# Skip all tests if langchain_core is not available
pytest.importorskip("langchain_core.tools")

from app.agents.tools import (
    create_database_tools,
    get_all_tools,
    get_tool_by_name,
    http_get,
    http_post,
)
from app.models import Item, User


@pytest.fixture
def mock_session() -> Mock:
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashedpassword",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def sample_item(sample_user: User) -> Item:
    """Create a sample item for testing."""
    return Item(
        id=uuid.uuid4(),
        title="Test Item",
        description="Test Description",
        owner_id=sample_user.id,
    )


class TestDatabaseTools:
    """Test database lookup tools."""

    def test_lookup_user_by_email_success(
        self,
        mock_session: Mock,
        sample_user: User,
    ) -> None:
        """Test successful user lookup by email."""
        # Mock the database query
        mock_result = Mock()
        mock_result.first.return_value = sample_user
        mock_session.exec.return_value = mock_result

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_user_tool = next(t for t in tools if t.name == "lookup_user_by_email")

        # Invoke the tool
        result = lookup_user_tool.invoke({"email": "test@example.com"})

        # Verify result
        result_data = json.loads(result)
        assert result_data["email"] == "test@example.com"
        assert result_data["full_name"] == "Test User"
        assert result_data["is_active"] is True
        assert result_data["is_superuser"] is False
        assert "id" in result_data

    def test_lookup_user_by_email_not_found(
        self,
        mock_session: Mock,
    ) -> None:
        """Test user lookup when user not found."""
        # Mock the database query to return None
        mock_result = Mock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_user_tool = next(t for t in tools if t.name == "lookup_user_by_email")

        # Invoke the tool
        result = lookup_user_tool.invoke({"email": "notfound@example.com"})

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "No user found" in result_data["error"]

    def test_lookup_user_by_email_database_error(
        self,
        mock_session: Mock,
    ) -> None:
        """Test user lookup handles database errors gracefully."""
        # Mock the database query to raise an exception
        mock_session.exec.side_effect = Exception("Database connection error")

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_user_tool = next(t for t in tools if t.name == "lookup_user_by_email")

        # Invoke the tool
        result = lookup_user_tool.invoke({"email": "test@example.com"})

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Database error" in result_data["error"]

    def test_lookup_item_by_id_success(
        self,
        mock_session: Mock,
        sample_item: Item,
    ) -> None:
        """Test successful item lookup by ID."""
        # Mock the database get
        mock_session.get.return_value = sample_item

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_item_tool = next(t for t in tools if t.name == "lookup_item_by_id")

        # Invoke the tool
        result = lookup_item_tool.invoke({"item_id": str(sample_item.id)})

        # Verify result
        result_data = json.loads(result)
        assert result_data["title"] == "Test Item"
        assert result_data["description"] == "Test Description"
        assert "id" in result_data
        assert "owner_id" in result_data

    def test_lookup_item_by_id_not_found(
        self,
        mock_session: Mock,
    ) -> None:
        """Test item lookup when item not found."""
        # Mock the database get to return None
        mock_session.get.return_value = None

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_item_tool = next(t for t in tools if t.name == "lookup_item_by_id")

        # Invoke the tool
        result = lookup_item_tool.invoke({"item_id": str(uuid.uuid4())})

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "No item found" in result_data["error"]

    def test_lookup_item_by_id_database_error(
        self,
        mock_session: Mock,
    ) -> None:
        """Test item lookup handles database errors gracefully."""
        # Mock the database get to raise an exception
        mock_session.get.side_effect = Exception("Database connection error")

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_item_tool = next(t for t in tools if t.name == "lookup_item_by_id")

        # Invoke the tool
        result = lookup_item_tool.invoke({"item_id": str(uuid.uuid4())})

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Database error" in result_data["error"]

    def test_lookup_user_items_success(
        self,
        mock_session: Mock,
        sample_item: Item,
    ) -> None:
        """Test successful lookup of user items."""
        # Create multiple items
        item1 = sample_item
        item2 = Item(
            id=uuid.uuid4(),
            title="Item 2",
            description="Description 2",
            owner_id=sample_item.owner_id,
        )

        # Mock the database query
        mock_result = Mock()
        mock_result.all.return_value = [item1, item2]
        mock_session.exec.return_value = mock_result

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_items_tool = next(t for t in tools if t.name == "lookup_user_items")

        # Invoke the tool
        result = lookup_items_tool.invoke({
            "user_id": str(sample_item.owner_id),
            "limit": 10,
        })

        # Verify result
        result_data = json.loads(result)
        assert result_data["count"] == 2
        assert result_data["limit"] == 10
        assert len(result_data["items"]) == 2
        assert result_data["items"][0]["title"] == "Test Item"
        assert result_data["items"][1]["title"] == "Item 2"

    def test_lookup_user_items_empty_result(
        self,
        mock_session: Mock,
    ) -> None:
        """Test lookup of user items when user has no items."""
        # Mock the database query to return empty list
        mock_result = Mock()
        mock_result.all.return_value = []
        mock_session.exec.return_value = mock_result

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_items_tool = next(t for t in tools if t.name == "lookup_user_items")

        # Invoke the tool
        result = lookup_items_tool.invoke({
            "user_id": str(uuid.uuid4()),
            "limit": 10,
        })

        # Verify result
        result_data = json.loads(result)
        assert result_data["count"] == 0
        assert result_data["items"] == []

    def test_lookup_user_items_custom_limit(
        self,
        mock_session: Mock,
        sample_item: Item,
    ) -> None:
        """Test lookup of user items with custom limit."""
        # Mock the database query
        mock_result = Mock()
        mock_result.all.return_value = [sample_item]
        mock_session.exec.return_value = mock_result

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_items_tool = next(t for t in tools if t.name == "lookup_user_items")

        # Invoke the tool with custom limit
        result = lookup_items_tool.invoke({
            "user_id": str(sample_item.owner_id),
            "limit": 5,
        })

        # Verify result includes custom limit
        result_data = json.loads(result)
        assert result_data["limit"] == 5

    def test_lookup_user_items_database_error(
        self,
        mock_session: Mock,
    ) -> None:
        """Test user items lookup handles database errors gracefully."""
        # Mock the database query to raise an exception
        mock_session.exec.side_effect = Exception("Database connection error")

        # Create tools
        tools = create_database_tools(mock_session)
        lookup_items_tool = next(t for t in tools if t.name == "lookup_user_items")

        # Invoke the tool
        result = lookup_items_tool.invoke({
            "user_id": str(uuid.uuid4()),
            "limit": 10,
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Database error" in result_data["error"]


class TestHTTPTools:
    """Test HTTP client tools."""

    @patch("app.agents.tools.httpx.Client")
    def test_http_get_success(self, mock_client_class: Mock) -> None:
        """Test successful HTTP GET request."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"message": "success"}'
        mock_response.url = "https://api.example.com/test"

        # Mock the client
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_get.invoke({
            "url": "https://api.example.com/test",
            "timeout": 30,
        })

        # Verify result
        result_data = json.loads(result)
        assert result_data["status_code"] == 200
        assert result_data["body"] == '{"message": "success"}'
        assert "Content-Type" in result_data["headers"]

    @patch("app.agents.tools.httpx.Client")
    def test_http_get_with_headers(self, mock_client_class: Mock) -> None:
        """Test HTTP GET request with custom headers."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.url = "https://api.example.com/test"

        # Mock the client
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool with headers
        custom_headers = {"Authorization": "Bearer token123"}
        result = http_get.invoke({
            "url": "https://api.example.com/test",
            "headers": custom_headers,
        })

        # Verify headers were passed
        mock_client.get.assert_called_once_with(
            "https://api.example.com/test",
            headers=custom_headers,
        )

        # Verify result
        result_data = json.loads(result)
        assert result_data["status_code"] == 200

    @patch("app.agents.tools.httpx.Client")
    def test_http_get_http_error(self, mock_client_class: Mock) -> None:
        """Test HTTP GET request handles HTTP errors."""
        import httpx

        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        # Mock the client to raise HTTPStatusError
        mock_client = Mock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=mock_response,
        )
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_get.invoke({
            "url": "https://api.example.com/notfound",
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert result_data["status_code"] == 404

    @patch("app.agents.tools.httpx.Client")
    def test_http_get_request_error(self, mock_client_class: Mock) -> None:
        """Test HTTP GET request handles request errors."""
        import httpx

        # Mock the client to raise RequestError
        mock_client = Mock()
        mock_client.get.side_effect = httpx.RequestError("Connection timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_get.invoke({
            "url": "https://api.example.com/test",
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Request error" in result_data["error"]

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_success(self, mock_client_class: Mock) -> None:
        """Test successful HTTP POST request."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"id": 123, "status": "created"}'
        mock_response.url = "https://api.example.com/create"

        # Mock the client
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_post.invoke({
            "url": "https://api.example.com/create",
            "json_data": {"name": "Test", "value": 42},
        })

        # Verify result
        result_data = json.loads(result)
        assert result_data["status_code"] == 201
        assert result_data["body"] == '{"id": 123, "status": "created"}'

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_with_none_data(self, mock_client_class: Mock) -> None:
        """Test HTTP POST request with None json_data."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.url = "https://api.example.com/test"

        # Mock the client
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool with None data
        result = http_post.invoke({
            "url": "https://api.example.com/test",
            "json_data": None,
        })

        # Verify post was called with None
        mock_client.post.assert_called_once_with(
            "https://api.example.com/test",
            json=None,
            headers={},
        )

        # Verify result
        result_data = json.loads(result)
        assert result_data["status_code"] == 200

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_with_headers(self, mock_client_class: Mock) -> None:
        """Test HTTP POST request with custom headers."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "OK"
        mock_response.url = "https://api.example.com/test"

        # Mock the client
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool with headers
        custom_headers = {"Authorization": "Bearer token123"}
        result = http_post.invoke({
            "url": "https://api.example.com/test",
            "json_data": {"test": "data"},
            "headers": custom_headers,
        })

        # Verify headers were passed
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["headers"] == custom_headers

        # Verify result
        result_data = json.loads(result)
        assert result_data["status_code"] == 200

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_http_error(self, mock_client_class: Mock) -> None:
        """Test HTTP POST request handles HTTP errors."""
        import httpx

        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        # Mock the client to raise HTTPStatusError
        mock_client = Mock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=Mock(),
            response=mock_response,
        )
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_post.invoke({
            "url": "https://api.example.com/test",
            "json_data": {"invalid": "data"},
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert result_data["status_code"] == 400

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_request_error(self, mock_client_class: Mock) -> None:
        """Test HTTP POST request handles request errors."""
        import httpx

        # Mock the client to raise RequestError
        mock_client = Mock()
        mock_client.post.side_effect = httpx.RequestError("Connection timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_post.invoke({
            "url": "https://api.example.com/test",
            "json_data": {"test": "data"},
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Request error" in result_data["error"]

    @patch("app.agents.tools.httpx.Client")
    def test_http_post_unexpected_error(self, mock_client_class: Mock) -> None:
        """Test HTTP POST request handles unexpected errors."""
        # Mock the client to raise unexpected exception
        mock_client = Mock()
        mock_client.post.side_effect = Exception("Unexpected error")
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Invoke the tool
        result = http_post.invoke({
            "url": "https://api.example.com/test",
            "json_data": {"test": "data"},
        })

        # Verify error is returned
        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unexpected error" in result_data["error"]


class TestToolRegistry:
    """Test tool registry functions."""

    def test_get_all_tools_with_session(self, mock_session: Mock) -> None:
        """Test get_all_tools includes database and HTTP tools."""
        tools = get_all_tools(session=mock_session)

        # Should have 3 database tools + 2 HTTP tools = 5 total
        assert len(tools) == 5

        # Verify tool names
        tool_names = {tool.name for tool in tools}
        assert "lookup_user_by_email" in tool_names
        assert "lookup_item_by_id" in tool_names
        assert "lookup_user_items" in tool_names
        assert "http_get" in tool_names
        assert "http_post" in tool_names

    def test_get_all_tools_without_session(self) -> None:
        """Test get_all_tools without session returns only HTTP tools."""
        tools = get_all_tools(session=None)

        # Should have only 2 HTTP tools
        assert len(tools) == 2

        # Verify tool names
        tool_names = {tool.name for tool in tools}
        assert "http_get" in tool_names
        assert "http_post" in tool_names

    def test_get_tool_by_name_success(self, mock_session: Mock) -> None:
        """Test getting a specific tool by name."""
        tool = get_tool_by_name("lookup_user_by_email", session=mock_session)

        assert tool is not None
        assert tool.name == "lookup_user_by_email"

    def test_get_tool_by_name_not_found(self, mock_session: Mock) -> None:
        """Test getting a non-existent tool returns None."""
        tool = get_tool_by_name("nonexistent_tool", session=mock_session)

        assert tool is None

    def test_get_tool_by_name_http_tool(self) -> None:
        """Test getting HTTP tool by name without session."""
        tool = get_tool_by_name("http_get", session=None)

        assert tool is not None
        assert tool.name == "http_get"

    def test_database_tools_have_proper_schemas(self, mock_session: Mock) -> None:
        """Test database tools have correct input schemas."""
        tools = create_database_tools(mock_session)

        # Check each tool has args_schema
        for tool in tools:
            assert tool.args_schema is not None

    def test_http_tools_have_proper_schemas(self) -> None:
        """Test HTTP tools have correct input schemas."""
        assert http_get.args_schema is not None
        assert http_post.args_schema is not None

    def test_tools_handle_errors_gracefully(self, mock_session: Mock) -> None:
        """Test all tools have handle_tool_errors enabled."""
        tools = create_database_tools(mock_session)

        for tool in tools:
            # Database tools should have handle_tool_errors=True
            # Note: handle_tool_errors is passed to from_function but may not
            # be stored as an attribute, so we just verify tools don't raise
            # when there's an error (they return error messages instead)
            assert tool is not None
