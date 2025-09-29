import ssl
from unittest import mock

import httpx

from imbi_automations import version
from imbi_automations.clients import http
from tests import base


class ClientTestCase(base.AsyncTestCase):
    """Tests for the Client class in the http module."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await http.HTTPClient.aclose()

    async def test_init(self) -> None:
        """Test the initialization of Client."""
        with mock.patch('truststore.SSLContext') as mock_ssl_context:
            mock_ctx = mock.MagicMock()
            mock_ssl_context.return_value = mock_ctx

            with mock.patch('httpx.AsyncClient') as mock_async_client:
                # Initialize the client
                client = http.HTTPClient()

                # Verify SSLContext was called correctly
                mock_ssl_context.assert_called_once_with(
                    ssl.PROTOCOL_TLS_CLIENT
                )

                # Verify AsyncClient was initialized correctly
                mock_async_client.assert_called_once_with(
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': f'imbi-automations/{version}',
                    },
                    transport=None,
                    timeout=30.0,
                    verify=mock_ctx,
                )

                # Verify http_client is set
                self.assertIsNotNone(client.http_client)

    async def test_getattr(self) -> None:
        """Test the __getattr__ method."""
        client = http.HTTPClient()
        client.http_client = mock.MagicMock()
        client.http_client.get = mock.MagicMock(return_value='test')

        # Access a method on the http_client through the Client
        result = client.get('https://example.com')

        # Verify the method was called on the http_client
        client.http_client.get.assert_called_once_with('https://example.com')
        self.assertEqual(result, 'test')

    async def test_getattr_attribute_error(self) -> None:
        """Test __getattr__ raises AttributeError for missing attributes."""
        client = http.HTTPClient()
        client.http_client = mock.MagicMock()

        # Configure the mock to raise AttributeError when a non-existent
        # attribute is accessed
        client.http_client.configure_mock(
            **{
                'non_existent_method.side_effect': AttributeError(
                    'No such attribute'
                )
            }
        )

        # Access a non-existent attribute should raise AttributeError
        with self.assertRaises(AttributeError):
            client.non_existent_method()

    async def test_add_header(self) -> None:
        """Test the add_header method."""
        client = http.HTTPClient()
        client.http_client = mock.MagicMock()
        client.http_client.headers = httpx.Headers()

        # Add a new header
        client.add_header('X-Test', 'test-value')

        # Verify the headers were updated
        self.assertEqual(
            client.http_client.headers.get('X-Test'), 'test-value'
        )

        # Test adding a second header
        client.add_header('X-Another', 'another-value')
        self.assertEqual(
            client.http_client.headers.get('X-Another'), 'another-value'
        )

        # Test overwriting an existing header
        client.add_header('X-Test', 'new-value')
        self.assertEqual(client.http_client.headers.get('X-Test'), 'new-value')

    async def test_aclose(self) -> None:
        """Test the aclose class method."""
        # Create mock instances to put in the _instances dict
        instance1 = mock.MagicMock()
        instance1.http_client = mock.MagicMock()
        instance1.http_client.aclose = mock.AsyncMock()

        instance2 = mock.MagicMock()
        instance2.http_client = mock.MagicMock()
        instance2.http_client.aclose = mock.AsyncMock()

        # Add the instances to the _instances dict
        http.HTTPClient._instances = {
            'instance1': instance1,
            'instance2': instance2,
        }

        # Call the aclose method
        await http.HTTPClient.aclose()

        # Verify all instances had aclose called
        instance1.http_client.aclose.assert_called_once()
        instance2.http_client.aclose.assert_called_once()

    async def test_aclose_empty(self) -> None:
        """Test the aclose class method with no instances."""
        # Ensure _instances is empty
        http.HTTPClient._instances = {}

        # Call the aclose method (should not raise)
        await http.HTTPClient.aclose()

    async def test_get_instance(self) -> None:
        """Test the get_instance method."""
        # Clear any existing instances
        http.HTTPClient._instances = {}

        # Get an instance
        instance1 = http.HTTPClient.get_instance()

        # Verify it's a Client
        self.assertIsInstance(instance1, http.HTTPClient)

        # Get another instance
        instance2 = http.HTTPClient.get_instance()

        # Verify it's the same instance
        self.assertIs(instance1, instance2)

        # Verify the instance is stored in _instances
        self.assertIn(http.HTTPClient, http.HTTPClient._instances)
        self.assertIs(http.HTTPClient._instances[http.HTTPClient], instance1)

    async def test_inheritance(self) -> None:
        """Test inheritance and separate singleton instances."""
        # Clear any existing instances
        http.HTTPClient._instances = {}

        # Get a base Client instance
        base_instance = http.HTTPClient.get_instance()

        # Create a subclass
        class SubClient(http.HTTPClient):
            pass

        # Get an instance of the subclass
        sub_instance = SubClient.get_instance()

        # Verify it's a SubClient
        self.assertIsInstance(sub_instance, SubClient)

        # Verify it's a different instance than Client
        self.assertIsNot(base_instance, sub_instance)

        # Verify the subclass instance is stored in _instances
        self.assertIn(SubClient, SubClient._instances)
        self.assertIs(SubClient._instances[SubClient], sub_instance)

        # Get another instance of SubClient and verify it's the same
        sub_instance2 = SubClient.get_instance()
        self.assertIs(sub_instance, sub_instance2)


class BaseURLHTTPClientTestCase(base.AsyncTestCase):
    """Tests for the BaseURLHTTPClient class in the http module."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await http.HTTPClient.aclose()

    async def test_init(self) -> None:
        """Test the initialization of BaseURLHTTPClient."""
        with mock.patch(
            'imbi_automations.clients.http.HTTPClient.__init__'
        ) as mock_init:
            mock_init.return_value = None

            # Initialize the client
            client = http.BaseURLHTTPClient()

            # Verify Client.__init__ was called
            mock_init.assert_called_once()

            # Verify the base_url property
            self.assertEqual(client.base_url, 'https://api.example.com')

    async def test_base_url_property(self) -> None:
        """Test the base_url property."""

        # Create a subclass with a custom base URL
        class CustomClient(http.BaseURLHTTPClient):
            _base_url = 'https://custom.example.com'

        # Create an instance of the subclass
        client = CustomClient()

        # Verify the base_url property
        self.assertEqual(client.base_url, 'https://custom.example.com')

        # Change the class's _base_url
        CustomClient._base_url = 'https://new.example.com'

        # Verify the base_url property returns the new value
        self.assertEqual(client.base_url, 'https://new.example.com')

    async def test_prepend_base_url(self) -> None:
        """Test the _prepend_base_url method."""
        client = http.BaseURLHTTPClient()

        # Test with absolute URLs (should be returned unchanged)
        self.assertEqual(
            client._prepend_base_url('http://example.com/path'),
            'http://example.com/path',
        )
        self.assertEqual(
            client._prepend_base_url('https://example.com/path'),
            'https://example.com/path',
        )
        self.assertEqual(
            client._prepend_base_url('//example.com/path'),
            '//example.com/path',
        )

        # Test with relative URLs and different leading/trailing slashes
        self.assertEqual(
            client._prepend_base_url('path'), 'https://api.example.com/path'
        )
        self.assertEqual(
            client._prepend_base_url('/path'), 'https://api.example.com/path'
        )
        self.assertEqual(
            client._prepend_base_url('path/'), 'https://api.example.com/path/'
        )
        self.assertEqual(
            client._prepend_base_url('/path/'), 'https://api.example.com/path/'
        )

        # Test with base URL that has trailing slash
        client._base_url = 'https://api.example.com/'
        self.assertEqual(
            client._prepend_base_url('/path'), 'https://api.example.com/path'
        )

    @mock.patch('imbi_automations.clients.http.LOGGER')
    async def test_http_method_wrapping(
        self, mock_logger: mock.MagicMock
    ) -> None:
        """Test the HTTP method wrapping functionality."""
        client = http.BaseURLHTTPClient()
        client.http_client = mock.MagicMock()

        # Create mock for HTTP method
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_get = mock.AsyncMock(return_value=mock_response)
        client.http_client.get = mock_get

        # Call the method with a relative path
        result = await client.get('api/endpoint')

        # Verify URL transformation and method call
        mock_get.assert_called_once_with(
            'https://api.example.com/api/endpoint'
        )
        mock_logger.debug.assert_called_once_with(
            'Using URL: %s', 'https://api.example.com/api/endpoint'
        )
        self.assertEqual(result, mock_response)

        # Test with absolute URL
        mock_get.reset_mock()
        mock_logger.debug.reset_mock()
        await client.get('https://other.example.com/api/endpoint')

        # Verify absolute URL was passed through unchanged
        mock_get.assert_called_once_with(
            'https://other.example.com/api/endpoint'
        )
        mock_logger.debug.assert_called_once_with(
            'Using URL: %s', 'https://other.example.com/api/endpoint'
        )

        # Test with path that has a leading slash
        mock_get.reset_mock()
        mock_logger.debug.reset_mock()
        await client.get('/api/endpoint')

        # Verify leading slash was properly handled
        mock_get.assert_called_once_with(
            'https://api.example.com/api/endpoint'
        )
        mock_logger.debug.assert_called_once_with(
            'Using URL: %s', 'https://api.example.com/api/endpoint'
        )

    async def test_non_http_method_attribute(self) -> None:
        """Test accessing non-HTTP method attributes."""
        client = http.BaseURLHTTPClient()
        client.http_client = mock.MagicMock()

        # Set up a non-HTTP method attribute
        client.http_client.headers = {'key': 'value'}

        # Access the attribute
        self.assertEqual(client.headers, {'key': 'value'})

    async def test_base_url_client_singleton(self) -> None:
        """Test the BaseURLHTTPClient singleton functionality."""
        # Clear any existing instances
        http.BaseURLHTTPClient._instances = {}

        # Get an instance
        instance1 = http.BaseURLHTTPClient.get_instance()

        # Verify it's a BaseURLHTTPClient
        self.assertIsInstance(instance1, http.BaseURLHTTPClient)

        # Get another instance
        instance2 = http.BaseURLHTTPClient.get_instance()

        # Verify it's the same instance
        self.assertIs(instance1, instance2)

        # Verify the instance is stored in _instances
        self.assertIn(
            http.BaseURLHTTPClient, http.BaseURLHTTPClient._instances
        )
        self.assertIs(
            http.BaseURLHTTPClient._instances[http.BaseURLHTTPClient],
            instance1,
        )

    async def test_base_url_inheritance(self) -> None:
        """Test inheritance of BaseURLHTTPClient."""

        # Define a subclass
        class CustomURLClient(http.BaseURLHTTPClient):
            _base_url = 'https://custom.example.com'

        # Define another subclass
        class AnotherURLClient(http.BaseURLHTTPClient):
            _base_url = 'https://another.example.com'

        # Get instances
        custom_instance = CustomURLClient.get_instance()
        another_instance = AnotherURLClient.get_instance()
        base_instance = http.BaseURLHTTPClient.get_instance()

        # Verify they're different instances
        self.assertIsNot(custom_instance, another_instance)
        self.assertIsNot(custom_instance, base_instance)
        self.assertIsNot(another_instance, base_instance)

        # Verify base_url properties
        self.assertEqual(
            custom_instance.base_url, 'https://custom.example.com'
        )
        self.assertEqual(
            another_instance.base_url, 'https://another.example.com'
        )
        self.assertEqual(base_instance.base_url, 'https://api.example.com')

    async def test_base_url_client_aclose(self) -> None:
        """Test that aclose works with BaseURLHTTPClient instances."""
        # Get a BaseURLHTTPClient instance
        instance = http.BaseURLHTTPClient()
        instance.http_client = mock.MagicMock()
        instance.http_client.aclose = mock.AsyncMock()

        # Add to instances dict
        http.BaseURLHTTPClient._instances = {http.BaseURLHTTPClient: instance}

        # Call aclose
        await http.BaseURLHTTPClient.aclose()

        # Verify aclose was called
        instance.http_client.aclose.assert_called_once()

    async def test_retry_on_rate_limit_success_first_attempt(self) -> None:
        """Test retry logic when request succeeds on first attempt."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        # Mock response that succeeds
        mock_response = mock.MagicMock()
        mock_response.status_code = 200

        mock_method = mock.AsyncMock(return_value=mock_response)

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=3
        )

        self.assertEqual(result, mock_response)
        mock_method.assert_called_once_with('/test')

    @mock.patch('asyncio.sleep')
    async def test_retry_on_rate_limit_success_after_retry(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic when request succeeds after 429 error."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        # First response: 429, second response: 200
        rate_limit_response = mock.MagicMock()
        rate_limit_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
        rate_limit_response.headers = {'retry-after': '2'}

        success_response = mock.MagicMock()
        success_response.status_code = 200

        mock_method = mock.AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=3
        )

        self.assertEqual(result, success_response)
        self.assertEqual(mock_method.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)  # Should use retry-after

    @mock.patch('asyncio.sleep')
    async def test_retry_on_rate_limit_max_retries_exceeded(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic when max retries are exceeded."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        # Always return 429
        rate_limit_response = mock.MagicMock()
        rate_limit_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
        rate_limit_response.headers = {}

        mock_method = mock.AsyncMock(return_value=rate_limit_response)

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=2
        )

        # Should return the last 429 response
        self.assertEqual(result, rate_limit_response)
        self.assertEqual(mock_method.call_count, 3)  # Initial + 2 retries

        # Should have slept twice (exponential backoff: 1.0, 2.0)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1.0)  # First retry delay
        mock_sleep.assert_any_call(2.0)  # Second retry delay

    @mock.patch('asyncio.sleep')
    async def test_retry_on_rate_limit_with_retry_after_header(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic respects Retry-After header."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        rate_limit_response = mock.MagicMock()
        rate_limit_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
        rate_limit_response.headers = {'retry-after': '5'}

        success_response = mock.MagicMock()
        success_response.status_code = 200

        mock_method = mock.AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=3, base_delay=1.0
        )

        self.assertEqual(result, success_response)
        # Should use the larger of retry-after (5) vs exponential backoff (1)
        mock_sleep.assert_called_once_with(5.0)

    @mock.patch('asyncio.sleep')
    async def test_retry_on_rate_limit_invalid_retry_after(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic with invalid Retry-After header."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        rate_limit_response = mock.MagicMock()
        rate_limit_response.status_code = http.HTTPStatus.TOO_MANY_REQUESTS
        rate_limit_response.headers = {'retry-after': 'invalid'}

        success_response = mock.MagicMock()
        success_response.status_code = 200

        mock_method = mock.AsyncMock(
            side_effect=[rate_limit_response, success_response]
        )

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=3, base_delay=1.0
        )

        self.assertEqual(result, success_response)
        # Should fall back to exponential backoff (1.0 * 2^0 = 1.0)
        mock_sleep.assert_called_once_with(1.0)

    @mock.patch('asyncio.sleep')
    async def test_retry_on_request_error(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic handles httpx.RequestError."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        request_error = httpx.ConnectError('Connection failed')
        success_response = mock.MagicMock()
        success_response.status_code = 200

        mock_method = mock.AsyncMock(
            side_effect=[request_error, success_response]
        )

        result = await client._retry_on_rate_limit(
            mock_method, '/test', max_retries=3, base_delay=1.0
        )

        self.assertEqual(result, success_response)
        self.assertEqual(mock_method.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    @mock.patch('asyncio.sleep')
    async def test_retry_on_request_error_max_retries_exceeded(
        self, mock_sleep: mock.AsyncMock
    ) -> None:
        """Test retry logic raises error when max retries exceeded."""
        client = http.BaseURLHTTPClient()
        client._base_url = 'https://api.example.com'

        request_error = httpx.ConnectError('Connection failed')
        mock_method = mock.AsyncMock(side_effect=request_error)

        with self.assertRaises(httpx.ConnectError):
            await client._retry_on_rate_limit(
                mock_method, '/test', max_retries=2, base_delay=1.0
            )

        self.assertEqual(mock_method.call_count, 3)  # Initial + 2 retries
        self.assertEqual(mock_sleep.call_count, 2)  # Should sleep before retry
