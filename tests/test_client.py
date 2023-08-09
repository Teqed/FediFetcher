"""Test the HttpMethod class."""
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

from fedifetcher.api.client import HttpMethod

pytest_plugins = ('pytest_asyncio',)  # noqa: Q000

class TestHttpMethod:
    """Test the HttpMethod class."""

    client: ClassVar[HttpMethod] = HttpMethod(
        token="token",  # noqa: S106
        api_base_url="example.com",
        session=MagicMock(),
    )

    class TestHandleResponseErrors:
        """Test the handle_response method."""

        async def test_success(self) -> None:
            """Test a 200 response with a body (success)."""
            response = MagicMock(
                status=200,
                json=AsyncMock(return_value={"key": "value"}),
            )
            expected_result = {"key": "value"}
            result = await TestHttpMethod.client.handle_response(response)
            assert result == expected_result

        async def test_success_no_body(self) -> None:
            """Test a 200 response without a body (success, {})."""
            response = MagicMock(
                status=200,
                json=AsyncMock(return_value={}),
            )
            expected_result = {"Status": "OK"}
            result = await TestHttpMethod.client.handle_response(response)
            assert result == expected_result

        async def test_failure(self) -> None:
            """Test a 400 response (failure)."""
            response = MagicMock(
                status=400,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = None
            result = await TestHttpMethod.client.handle_response(response)
            assert result == expected_result


    class TestPost:
        """Test the post method."""

        endpoint: ClassVar[str] = "/endpoint"
        json: ClassVar[dict] = {"key": "value"}

        async def test_post_success(self) -> None:
            """Test a successful post."""
            TestHttpMethod.client.session.post = MagicMock()
            TestHttpMethod.client.session.\
                    post.return_value.__aenter__.return_value = MagicMock(
                status=200,
                json=AsyncMock(return_value={"key": "value"}),
            )
            expected_result = self.json
            result = await TestHttpMethod.client.post(self.endpoint, self.json)
            assert result == expected_result

        async def test_post_no_json(self) -> None:
            """Test a successful post without a JSON body."""
            TestHttpMethod.client.session.\
                    post.return_value.__aenter__.return_value = MagicMock(
                status=400,
                json=AsyncMock(return_value={"error": "error"}),
            )
            expected_result = None
            result = await TestHttpMethod.client.post(self.endpoint, self.json)
            assert result == expected_result
