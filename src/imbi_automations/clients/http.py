"""Base HTTP client with SSL verification, authentication, and errors.

Provides base HTTP client classes using httpx with singleton pattern, SSL
certificate handling via truststore, custom headers, and comprehensive
error handling. Implements both basic HTTPClient and BaseURLHTTPClient
with base URL management.
"""

import asyncio
import contextlib
import http
import logging
import ssl
import typing

import httpx
import truststore

from imbi_automations import utils, version

LOGGER = logging.getLogger(__name__)

HTTPStatus = http.HTTPStatus


class HTTPClient:
    """Wrapper for httpx that sets up SSL verification and headers."""

    _headers: dict[str, str] = {
        'Content-Type': 'application/json',
        'User-Agent': f'imbi-automations/{version}',
    }
    _instances: dict[type, typing.Self] = {}

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.http_client = httpx.AsyncClient(
            headers=self._headers,
            timeout=30.0,
            transport=transport,
            verify=ctx,
        )

    @classmethod
    def get_instance(
        cls,
        transport: httpx.BaseTransport | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Self:
        """Implement singleton behavior, return the instance for this class."""
        if cls not in cls._instances:
            cls._instances[cls] = cls(*args, **kwargs, transport=transport)
        return cls._instances[cls]

    def __getattr__(self, name: str) -> typing.Any:
        """Dynamically pass through methods on the http client"""
        return getattr(self.http_client, name)

    def add_header(self, key: str, value: str) -> None:
        """Add a default header to the http client"""
        self.http_client.headers.update({key: value})

    @classmethod
    async def aclose(cls) -> None:
        """Explicitly close the underlying HTTPX client."""
        for typ, instance in tuple(cls._instances.items()):
            await instance.http_client.aclose()
            del cls._instances[typ]
        cls._instances = {}


class BaseURLHTTPClient(HTTPClient):
    """Base client for APIs that use a common base URL.

    Subclasses should override the `_base_url` class variable to set the
    appropriate API endpoint. All HTTP method calls will automatically
    have the base URL prepended if not already absolute.
    """

    _base_url: str = 'https://api.example.com'
    _http_methods = {
        'get',
        'post',
        'put',
        'delete',
        'patch',
        'head',
        'options',
    }

    @property
    def base_url(self) -> str:
        """Return the base URL"""
        return self._base_url

    def _prepend_base_url(self, url_or_path: str) -> str:
        """Prepend the base URL to the given URL if it's not absolute."""
        if url_or_path.startswith(('http://', 'https://', '//')):
            return url_or_path
        return f'{self.base_url.rstrip("/")}/{url_or_path.lstrip("/")}'

    async def _retry_on_rate_limit(
        self,
        method: typing.Callable,
        url: str,
        *args: typing.Any,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs: typing.Any,
    ) -> httpx.Response:
        """Retry HTTP requests with exponential backoff on 429 errors."""
        for attempt in range(max_retries + 1):
            try:
                response = await method(url, *args, **kwargs)
                if response.status_code != HTTPStatus.TOO_MANY_REQUESTS:
                    return response

                if attempt == max_retries:
                    # Last attempt, return the response
                    return response

                # Calculate delay: base_delay * 2^attempt + jitter
                delay = base_delay * (2**attempt)

                # Check for Retry-After header
                retry_after = response.headers.get('retry-after')
                if retry_after:
                    with contextlib.suppress(ValueError):
                        # Retry-After can be in seconds or HTTP-date
                        delay = max(delay, float(retry_after))

                LOGGER.warning(
                    'Rate limited (429) on %s, retrying in %.1f seconds '
                    '(attempt %d/%d)',
                    utils.sanitize(url),
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)

            except httpx.RequestError as exc:
                if attempt == max_retries:
                    raise
                delay = base_delay * (2**attempt)
                LOGGER.warning(
                    'Request error on %s: %s, retrying in %.1f seconds '
                    '(attempt %d/%d)',
                    utils.sanitize(url),
                    exc,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)

        # This should never be reached, but helps with type checking
        raise RuntimeError('Retry logic failed unexpectedly')

    def __getattr__(self, name: str) -> typing.Any:
        """Override HTTP methods to prepend base URL when needed"""
        attr = getattr(self.http_client, name)
        if name in self._http_methods:

            async def wrapper(
                url: str, *args: typing.Any, **kwargs: typing.Any
            ) -> typing.Any:
                modified_url = self._prepend_base_url(url)
                LOGGER.debug('Using URL: %s', utils.sanitize(modified_url))
                return await self._retry_on_rate_limit(
                    attr, modified_url, *args, **kwargs
                )

            return wrapper
        return attr
