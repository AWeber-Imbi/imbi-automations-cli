import http
import unittest

import httpx

from imbi_automations import gitlab, models
from imbi_automations import http as ia_http
from tests.base import AsyncTestCase


class TestGitLabClient(AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.config = models.GitLabConfiguration(
            api_key='glpat_test_token', hostname='gitlab.example.com'
        )
        self.instance = gitlab.GitLab(self.config, self.http_client_transport)

    async def test_gitlab_init(self) -> None:
        """Test GitLab client initialization."""
        client = gitlab.GitLab(self.config)

        self.assertEqual(client.base_url, 'https://gitlab.example.com')
        # Check that the PRIVATE-TOKEN header is set
        headers = client.http_client.headers
        self.assertIn('PRIVATE-TOKEN', headers)
        self.assertEqual(headers['PRIVATE-TOKEN'], 'glpat_test_token')

    async def test_gitlab_init_with_custom_transport(self) -> None:
        """Test GitLab client initialization with custom transport."""
        transport = httpx.MockTransport(lambda request: httpx.Response(200))
        client = gitlab.GitLab(self.config, transport)

        self.assertEqual(client.base_url, 'https://gitlab.example.com')
        self.assertIsInstance(
            client.http_client._transport, httpx.MockTransport
        )

    async def test_get_project_success(self) -> None:
        """Test successful project retrieval by ID."""
        # Setup mock response data with all required fields
        project_data = {
            'id': 123,
            'name': 'test-project',
            'description': 'A test project',
            'name_with_namespace': 'group/test-project',
            'path': 'test-project',
            'path_with_namespace': 'group/test-project',
            'created_at': '2023-01-01T00:00:00.000Z',
            'default_branch': 'main',
            'ssh_url_to_repo': 'git@gitlab.example.com:group/test-project.git',
            'http_url_to_repo': 'https://gitlab.example.com/group/test-project.git',
            'web_url': 'https://gitlab.example.com/group/test-project',
            'visibility': 'private',
            'namespace': {
                'id': 456,
                'name': 'group',
                'path': 'group',
                'kind': 'group',
                'full_path': 'group',
                'web_url': 'https://gitlab.example.com/group',
            },
        }

        # Mock the HTTP response
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=project_data,
            request=httpx.Request(
                'GET', 'https://gitlab.example.com/api/v4/projects/123'
            ),
        )

        result = await self.instance.get_project(123)

        self.assertIsInstance(result, models.GitLabProject)
        self.assertEqual(result.id, 123)
        self.assertEqual(result.name, 'test-project')
        self.assertEqual(result.path_with_namespace, 'group/test-project')

    async def test_get_project_not_found(self) -> None:
        """Test project retrieval when project doesn't exist."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET', 'https://gitlab.example.com/api/v4/projects/999'
            ),
        )

        result = await self.instance.get_project(999)

        self.assertIsNone(result)

    async def test_get_project_http_error(self) -> None:
        """Test project retrieval with HTTP error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            request=httpx.Request(
                'GET', 'https://gitlab.example.com/api/v4/projects/123'
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_project(123)

    async def test_get_project_by_path_success(self) -> None:
        """Test successful project retrieval by path."""
        project_data = {
            'id': 789,
            'name': 'my-project',
            'description': 'My test project',
            'name_with_namespace': 'group/subgroup/my-project',
            'path': 'my-project',
            'path_with_namespace': 'group/subgroup/my-project',
            'created_at': '2023-02-01T00:00:00.000Z',
            'default_branch': 'main',
            'ssh_url_to_repo': 'git@gitlab.example.com:group/subgroup/my-project.git',  # noqa: E501
            'http_url_to_repo': 'https://gitlab.example.com/group/subgroup/my-project.git',
            'web_url': 'https://gitlab.example.com/group/subgroup/my-project',
            'visibility': 'internal',
            'namespace': {
                'id': 123,
                'name': 'subgroup',
                'path': 'subgroup',
                'kind': 'group',
                'full_path': 'group/subgroup',
                'web_url': 'https://gitlab.example.com/group/subgroup',
            },
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=project_data,
            request=httpx.Request(
                'GET',
                'https://gitlab.example.com/api/v4/projects/group%2Fsubgroup%2Fmy-project',
            ),
        )

        result = await self.instance.get_project_by_path(
            'group/subgroup/my-project'
        )

        self.assertIsInstance(result, models.GitLabProject)
        self.assertEqual(result.id, 789)
        self.assertEqual(result.name, 'my-project')
        self.assertEqual(
            result.path_with_namespace, 'group/subgroup/my-project'
        )

    async def test_get_project_by_path_url_encoding(self) -> None:
        """Test that project paths are properly URL encoded."""
        project_data = {
            'id': 999,
            'name': 'special-project',
            'description': 'Project with spaces',
            'name_with_namespace': 'group/special project with spaces',
            'path': 'special-project',
            'path_with_namespace': 'group/special project with spaces',
            'created_at': '2023-03-01T00:00:00.000Z',
            'default_branch': 'main',
            'ssh_url_to_repo': 'git@gitlab.example.com:group/special project with spaces.git',  # noqa: E501
            'http_url_to_repo': 'https://gitlab.example.com/group/special project with spaces.git',  # noqa: E501
            'web_url': 'https://gitlab.example.com/group/special%20project%20with%20spaces',
            'visibility': 'public',
            'namespace': {
                'id': 111,
                'name': 'group',
                'path': 'group',
                'kind': 'group',
                'full_path': 'group',
                'web_url': 'https://gitlab.example.com/group',
            },
        }

        # Expect URL-encoded path in request
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=project_data,
            request=httpx.Request(
                'GET',
                'https://gitlab.example.com/api/v4/projects/group%2Fspecial%20project%20with%20spaces',
            ),
        )

        result = await self.instance.get_project_by_path(
            'group/special project with spaces'
        )

        self.assertIsInstance(result, models.GitLabProject)
        self.assertEqual(result.id, 999)

    async def test_get_project_by_path_not_found(self) -> None:
        """Test project retrieval by path when project doesn't exist."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET',
                'https://gitlab.example.com/api/v4/projects/nonexistent%2Fproject',
            ),
        )

        result = await self.instance.get_project_by_path('nonexistent/project')

        self.assertIsNone(result)

    async def test_get_project_by_path_http_error(self) -> None:
        """Test project retrieval by path with HTTP error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'GET',
                'https://gitlab.example.com/api/v4/projects/private%2Fproject',
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_project_by_path('private/project')

    async def test_gitlab_default_hostname(self) -> None:
        """Test GitLab client with default hostname."""
        config_default = models.GitLabConfiguration(api_key='glpat_test_token')
        client = gitlab.GitLab(config_default)

        self.assertEqual(client.base_url, 'https://gitlab.com')

    async def test_gitlab_custom_hostname(self) -> None:
        """Test GitLab client with custom hostname."""
        config_custom = models.GitLabConfiguration(
            api_key='glpat_test_token', hostname='git.company.com'
        )
        client = gitlab.GitLab(config_custom)

        self.assertEqual(client.base_url, 'https://git.company.com')

    async def test_gitlab_inheritance_from_base_url_client(self) -> None:
        """Test that GitLab inherits properly from BaseURLClient."""
        self.assertIsInstance(self.instance, ia_http.BaseURLClient)
        self.assertTrue(hasattr(self.instance, 'get'))
        self.assertTrue(hasattr(self.instance, 'post'))
        self.assertTrue(hasattr(self.instance, 'put'))
        self.assertTrue(hasattr(self.instance, 'patch'))
        self.assertTrue(hasattr(self.instance, 'delete'))


if __name__ == '__main__':
    unittest.main()
