import ssl
from unittest import mock

import httpx

from imbi_automations import http, version
from tests import base


class ClientTestCase(base.AsyncTestCase):
    """Tests for the Client class in the http module."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await http.Client.aclose()

    async def test_init(self) -> None:
        """Test the initialization of Client."""
        with mock.patch('truststore.SSLContext') as mock_ssl_context:
            mock_ctx = mock.MagicMock()
            mock_ssl_context.return_value = mock_ctx

            with mock.patch('httpx.AsyncClient') as mock_async_client:
                # Initialize the client
                client = http.Client()

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
        client = http.Client()
        client.http_client = mock.MagicMock()
        client.http_client.get = mock.MagicMock(return_value='test')

        # Access a method on the http_client through the Client
        result = client.get('https://example.com')

        # Verify the method was called on the http_client
        client.http_client.get.assert_called_once_with('https://example.com')
        self.assertEqual(result, 'test')

    async def test_getattr_attribute_error(self) -> None:
        """Test __getattr__ raises AttributeError for missing attributes."""
        client = http.Client()
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
        client = http.Client()
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
        http.Client._instances = {
            'instance1': instance1,
            'instance2': instance2,
        }

        # Call the aclose method
        await http.Client.aclose()

        # Verify all instances had aclose called
        instance1.http_client.aclose.assert_called_once()
        instance2.http_client.aclose.assert_called_once()

    async def test_aclose_empty(self) -> None:
        """Test the aclose class method with no instances."""
        # Ensure _instances is empty
        http.Client._instances = {}

        # Call the aclose method (should not raise)
        await http.Client.aclose()

    async def test_get_instance(self) -> None:
        """Test the get_instance method."""
        # Clear any existing instances
        http.Client._instances = {}

        # Get an instance
        instance1 = http.Client.get_instance()

        # Verify it's a Client
        self.assertIsInstance(instance1, http.Client)

        # Get another instance
        instance2 = http.Client.get_instance()

        # Verify it's the same instance
        self.assertIs(instance1, instance2)

        # Verify the instance is stored in _instances
        self.assertIn(http.Client, http.Client._instances)
        self.assertIs(http.Client._instances[http.Client], instance1)

    async def test_inheritance(self) -> None:
        """Test inheritance and separate singleton instances."""
        # Clear any existing instances
        http.Client._instances = {}

        # Get a base Client instance
        base_instance = http.Client.get_instance()

        # Create a subclass
        class SubClient(http.Client):
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


class BaseURLClientTestCase(base.AsyncTestCase):
    """Tests for the BaseURLClient class in the http module."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await http.Client.aclose()

    async def test_init(self) -> None:
        """Test the initialization of BaseURLClient."""
        with mock.patch('imbi_automations.http.Client.__init__') as mock_init:
            mock_init.return_value = None

            # Initialize the client
            client = http.BaseURLClient()

            # Verify Client.__init__ was called
            mock_init.assert_called_once()

            # Verify the base_url property
            self.assertEqual(client.base_url, 'https://api.example.com')

    async def test_base_url_property(self) -> None:
        """Test the base_url property."""

        # Create a subclass with a custom base URL
        class CustomClient(http.BaseURLClient):
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
        client = http.BaseURLClient()

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

    @mock.patch('imbi_automations.http.LOGGER')
    async def test_http_method_wrapping(
        self, mock_logger: mock.MagicMock
    ) -> None:
        """Test the HTTP method wrapping functionality."""
        client = http.BaseURLClient()
        client.http_client = mock.MagicMock()

        # Create mock for HTTP method
        mock_get = mock.AsyncMock(return_value='response')
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
        self.assertEqual(result, 'response')

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
        client = http.BaseURLClient()
        client.http_client = mock.MagicMock()

        # Set up a non-HTTP method attribute
        client.http_client.headers = {'key': 'value'}

        # Access the attribute
        self.assertEqual(client.headers, {'key': 'value'})

    async def test_base_url_client_singleton(self) -> None:
        """Test the BaseURLClient singleton functionality."""
        # Clear any existing instances
        http.BaseURLClient._instances = {}

        # Get an instance
        instance1 = http.BaseURLClient.get_instance()

        # Verify it's a BaseURLClient
        self.assertIsInstance(instance1, http.BaseURLClient)

        # Get another instance
        instance2 = http.BaseURLClient.get_instance()

        # Verify it's the same instance
        self.assertIs(instance1, instance2)

        # Verify the instance is stored in _instances
        self.assertIn(http.BaseURLClient, http.BaseURLClient._instances)
        self.assertIs(
            http.BaseURLClient._instances[http.BaseURLClient], instance1
        )

    async def test_base_url_inheritance(self) -> None:
        """Test inheritance of BaseURLClient."""

        # Define a subclass
        class CustomURLClient(http.BaseURLClient):
            _base_url = 'https://custom.example.com'

        # Define another subclass
        class AnotherURLClient(http.BaseURLClient):
            _base_url = 'https://another.example.com'

        # Get instances
        custom_instance = CustomURLClient.get_instance()
        another_instance = AnotherURLClient.get_instance()
        base_instance = http.BaseURLClient.get_instance()

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
        """Test that aclose works with BaseURLClient instances."""
        # Get a BaseURLClient instance
        instance = http.BaseURLClient()
        instance.http_client = mock.MagicMock()
        instance.http_client.aclose = mock.AsyncMock()

        # Add to instances dict
        http.BaseURLClient._instances = {http.BaseURLClient: instance}

        # Call aclose
        await http.BaseURLClient.aclose()

        # Verify aclose was called
        instance.http_client.aclose.assert_called_once()
