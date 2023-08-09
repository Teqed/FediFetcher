"""Generic client for API requests."""
import asyncio
import logging
from typing import Any

import aiohttp

from fedifetcher.helpers.helpers import Response


class HttpMethod:
    """A class representing a request client."""

    def __init__(
        self,
        api_base_url: str,
        session: aiohttp.ClientSession,
        token: str | None = None,
        pgupdater=None,  # noqa: ANN001
    ) -> None:
        """Initialize the client."""
        self.api_base_url = api_base_url
        self.token = token
        self.session = session
        self.pgupdater = pgupdater

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
        tries: int = 0,
        semaphore: asyncio.Semaphore | None = None,
    ) -> dict[str, Any] | None:
        """Perform a GET request to the server."""
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            try:
                url = f"https://{self.api_base_url}{endpoint}"
                logging.debug(f"Getting {url} with {params}")
                async with self.session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                    params=params,
                ) as response:
                    logging.debug(f"Got {url} with {params} status {response.status}")
                    if response.status == Response.TOO_MANY_REQUESTS:
                        ratelimit_reset_timer_in_minutes = 5
                        if tries > ratelimit_reset_timer_in_minutes:
                            logging.error(
                                f"Error with API on server {self.api_base_url}. "
                                f"Too many requests: {response}",
                            )
                            return None
                        logging.warning(
                            f"Too many requests to {self.api_base_url}. "
                            f"Waiting 60 seconds before trying again.",
                        )
                        await asyncio.sleep(60)
                        return await self.get(
                            endpoint=endpoint,
                            params=params,
                            tries=tries + 1,
                        )
                    return await self.handle_response(response)
            except asyncio.TimeoutError:
                logging.warning(
                    f"Timeout error with API on server {self.api_base_url}.",
                )
            except aiohttp.ClientConnectorSSLError:
                logging.warning(f"SSL error with API on server {self.api_base_url}.")
            except aiohttp.ClientConnectorError:
                logging.exception(
                    f"Connection error with API on server {self.api_base_url}.",
                )
            except aiohttp.ClientError:
                logging.exception(f"Error with API on server {self.api_base_url}.")
            except Exception:
                logging.exception(
                    f"Unknown error with API on server {self.api_base_url}.",
                )
            return None

    async def post(
        self,
        endpoint: str,
        json: dict | None = None,
        tries: int = 0,
        semaphore: asyncio.Semaphore | None = None,
    ) -> dict[str, Any] | None:
        """Perform a POST request to the server."""
        if semaphore is None:
            semaphore = asyncio.Semaphore(1)
        async with semaphore:
            try:
                url: str = f"https://{self.api_base_url}{endpoint}"
                logging.debug(f"Posting {url} with {json}")
                async with self.session.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                    },
                    json=json,
                ) as response:
                    logging.debug(f"Posted {url} with {json} status {response.status}")
                    if response.status == Response.TOO_MANY_REQUESTS:
                        ratelimit_reset_timer_in_minutes = 5
                        if tries > ratelimit_reset_timer_in_minutes:
                            logging.error(
                                f"Error with API on server {self.api_base_url}. "
                                f"Too many requests: {response}",
                            )
                            return None
                        logging.warning(
                            f"Too many requests to {self.api_base_url}. "
                            f"Waiting 60 seconds before trying again.",
                        )
                        await asyncio.sleep(60)
                        return await self.post(
                            endpoint=endpoint,
                            json=json,
                            tries=tries + 1,
                        )
                    return await self.handle_response(response)
            except asyncio.TimeoutError:
                logging.warning(
                    f"Timeout error with API on server {self.api_base_url}.",
                )
            except aiohttp.ClientConnectorSSLError:
                logging.warning(f"SSL error with API on server {self.api_base_url}.")
            except aiohttp.ClientConnectorError:
                logging.exception(
                    f"Connection error with API on server {self.api_base_url}.",
                )
            except aiohttp.ClientError:
                logging.exception(f"Error with API on server {self.api_base_url}.")
            except Exception:
                logging.exception(
                    f"Unknown error with API on server {self.api_base_url}.",
                )
            return None

    def handle_response_lists(
        self,
        body: dict | list[dict],
    ) -> dict[str, Any]:
        """Process the response into a dict."""
        if isinstance(body, list):
            body = {"list": body}
        if not isinstance(body, dict):
            msg = (
                f"Error with API on server {self.api_base_url}. "
                f"The server returned an unexpected response: {body}"
            )
            raise TypeError(
                msg,
            )
        return body

    def handle_response_pagination(
        self,
        body: dict,
        response: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Handle pagination in the response."""
        link_header = response.headers.get("Link")
        if link_header:
            links = {}
            link_parts = link_header.split(", ")
            for link_part in link_parts:
                url, rel = link_part.split("; ")
                url = url.strip("<>")
                rel = rel.strip('rel="')
                links[rel] = url
            if links.get("next"):
                body["_pagination_next"] = links["next"]
            if links.get("prev"):
                body["_pagination_prev"] = links["prev"]
        return body

    def handle_response_errors(
        self,
        response: aiohttp.ClientResponse,
    ) -> None:
        """Handle errors in the response."""
        if response.status == Response.BAD_REQUEST:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"400 Client error: {response}",
            )
        elif response.status == Response.UNAUTHORIZED:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"401 Authentication error: {response}",
            )
        elif response.status == Response.FORBIDDEN:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"403 Forbidden error: {response}",
            )
        elif response.status == Response.TOO_MANY_REQUESTS:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"429 Too many requests: {response}",
            )
        elif response.status == Response.INTERNAL_SERVER_ERROR:
            logging.warning(
                f"Error with API on server {self.api_base_url}. "
                f"500 Internal server error: {response}",
            )
        else:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"The server encountered an error: {response}",
            )

    async def handle_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> dict | None:
        """Handle errors in the response."""
        if response.status != Response.OK:
            return self.handle_response_errors(response)
        body = await response.json()
        if not body:  # Successful response with no body
            return {"Status": "OK"}
        try:
            body: dict[str, Any] = self.handle_response_lists(body)
        except TypeError:
            logging.error(
                f"Error with API on server {self.api_base_url}. "
                f"The server returned an unexpected response: {body}",
            )
            return None
        return self.handle_response_pagination(body, response)
