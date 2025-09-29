import http
import pathlib
import unittest
from unittest import mock

import httpx

from imbi_automations import errors, models
from imbi_automations.clients import github
from imbi_automations.clients import http as ia_http
from tests import base


class TestGitHubClient(base.AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.config = models.GitHubConfiguration(
            api_key='ghp_test_token', hostname='api.github.com'
        )
        self.instance = github.GitHub(self.config, self.http_client_transport)

    async def test_github_init(self) -> None:
        """Test GitHub client initialization."""
        client = github.GitHub(self.config)

        self.assertEqual(client.base_url, 'https://api.github.com')
        # Check that headers are set correctly
        headers = client.http_client.headers
        self.assertIn('Authorization', headers)
        self.assertEqual(headers['Authorization'], 'Bearer ghp_test_token')
        self.assertEqual(headers['X-GitHub-Api-Version'], '2022-11-28')
        self.assertEqual(headers['Accept'], 'application/vnd.github+json')

    async def test_github_init_with_custom_transport(self) -> None:
        """Test GitHub client initialization with custom transport."""
        transport = httpx.MockTransport(lambda request: httpx.Response(200))
        client = github.GitHub(self.config, transport)

        self.assertEqual(client.base_url, 'https://api.github.com')
        self.assertIsInstance(
            client.http_client._transport, httpx.MockTransport
        )

    async def test_get_repository_success(self) -> None:
        """Test successful repository retrieval."""
        repo_data = {
            'id': 789,
            'node_id': 'R_node789',
            'name': 'test-repo',
            'full_name': 'testorg/test-repo',
            'private': False,
            'html_url': 'https://github.com/testorg/test-repo',
            'description': 'Test repository',
            'fork': False,
            'url': 'https://api.github.com/repos/testorg/test-repo',
            'default_branch': 'main',
            'clone_url': 'https://github.com/testorg/test-repo.git',
            'ssh_url': 'git@github.com:testorg/test-repo.git',
            'git_url': 'git://github.com/testorg/test-repo.git',
            'owner': {
                'login': 'testorg',
                'id': 456,
                'node_id': 'O_node456',
                'avatar_url': 'https://avatars.githubusercontent.com/u/456?v=4',
                'url': 'https://api.github.com/users/testorg',
                'html_url': 'https://github.com/testorg',
                'type': 'Organization',
                'site_admin': False,
            },
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=repo_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/test-repo'
            ),
        )

        result = await self.instance.get_repository('testorg', 'test-repo')

        self.assertIsInstance(result, models.GitHubRepository)
        self.assertEqual(result.id, 789)
        self.assertEqual(result.name, 'test-repo')
        self.assertEqual(result.full_name, 'testorg/test-repo')

    async def test_get_repository_not_found(self) -> None:
        """Test repository retrieval when repository doesn't exist."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/nonexistent'
            ),
        )

        result = await self.instance.get_repository('testorg', 'nonexistent')

        self.assertIsNone(result)

    async def test_get_repository_forbidden_error(self) -> None:
        """Test repository retrieval with 403 Forbidden error."""
        error_data = {'message': 'Repository access blocked'}

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            json=error_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/private-repo'
            ),
        )

        with self.assertRaises(errors.GitHubNotFoundError) as cm:
            await self.instance.get_repository('testorg', 'private-repo')

        self.assertIn('Access denied for repository', str(cm.exception))

    async def test_get_repository_forbidden_no_content(self) -> None:
        """Test repository retrieval with 403 Forbidden and no content."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/private-repo'
            ),
        )

        with self.assertRaises(errors.GitHubNotFoundError) as cm:
            await self.instance.get_repository('testorg', 'private-repo')

        self.assertIn('Access denied for repository', str(cm.exception))

    async def test_get_repository_other_http_error(self) -> None:
        """Test repository retrieval with other HTTP errors."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/test-repo'
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_repository('testorg', 'test-repo')

    async def test_get_repository_by_id_success(self) -> None:
        """Test successful repository retrieval by ID."""
        repo_data = {
            'id': 12345,
            'node_id': 'R_node12345',
            'name': 'repo-by-id',
            'full_name': 'myorg/repo-by-id',
            'private': True,
            'html_url': 'https://github.com/myorg/repo-by-id',
            'description': 'Repository retrieved by ID',
            'fork': False,
            'url': 'https://api.github.com/repos/myorg/repo-by-id',
            'default_branch': 'main',
            'clone_url': 'https://github.com/myorg/repo-by-id.git',
            'ssh_url': 'git@github.com:myorg/repo-by-id.git',
            'git_url': 'git://github.com/myorg/repo-by-id.git',
            'owner': {
                'login': 'myorg',
                'id': 999,
                'node_id': 'O_node999',
                'avatar_url': 'https://avatars.githubusercontent.com/u/999?v=4',
                'url': 'https://api.github.com/users/myorg',
                'html_url': 'https://github.com/myorg',
                'type': 'Organization',
                'site_admin': False,
            },
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=repo_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repositories/12345'
            ),
        )

        result = await self.instance.get_repository_by_id(12345)

        self.assertIsInstance(result, models.GitHubRepository)
        self.assertEqual(result.id, 12345)
        self.assertEqual(result.name, 'repo-by-id')
        self.assertEqual(result.full_name, 'myorg/repo-by-id')

    async def test_get_repository_by_id_not_found(self) -> None:
        """Test repository retrieval by ID when repository doesn't exist."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET', 'https://api.github.com/repositories/99999'
            ),
        )

        result = await self.instance.get_repository_by_id(99999)

        self.assertIsNone(result)

    async def test_get_repository_by_id_forbidden_error(self) -> None:
        """Test repository retrieval by ID with 403 Forbidden."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            json={'message': 'Access denied'},
            request=httpx.Request(
                'GET', 'https://api.github.com/repositories/12345'
            ),
        )

        with self.assertRaises(errors.GitHubNotFoundError):
            await self.instance.get_repository_by_id(12345)

    async def test_get_repository_by_id_server_error(self) -> None:
        """Test repository retrieval by ID with server error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            content=b'Server error',
            request=httpx.Request(
                'GET', 'https://api.github.com/repositories/12345'
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_repository_by_id(12345)

    async def test_get_repository_custom_properties_success(self) -> None:
        """Test successful custom properties retrieval."""
        properties_data = [
            {'property_name': 'environment', 'value': 'production'},
            {'property_name': 'team', 'value': ['backend', 'api']},
            {'property_name': 'cost_center', 'value': 'engineering'},
        ]

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=properties_data,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/properties/values',
            ),
        )

        result = await self.instance.get_repository_custom_properties(
            'testorg', 'test-repo'
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result['environment'], 'production')
        self.assertEqual(result['team'], ['backend', 'api'])
        self.assertEqual(result['cost_center'], 'engineering')

    async def test_get_repository_custom_properties_empty(self) -> None:
        """Test custom properties retrieval with empty response."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=[],
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/properties/values',
            ),
        )

        result = await self.instance.get_repository_custom_properties(
            'testorg', 'test-repo'
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    async def test_get_repository_custom_properties_http_error(self) -> None:
        """Test custom properties retrieval with HTTP error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/properties/values',
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_repository_custom_properties(
                'testorg', 'test-repo'
            )

    async def test_update_repository_custom_properties_success(self) -> None:
        """Test successful custom properties update."""
        properties = {
            'environment': 'staging',
            'team': ['frontend', 'ui'],
            'cost_center': 'product',
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NO_CONTENT,
            request=httpx.Request(
                'PATCH',
                'https://api.github.com/repos/testorg/test-repo/properties/values',
            ),
        )

        # Should not raise any exception
        await self.instance.update_repository_custom_properties(
            'testorg', 'test-repo', properties
        )

    async def test_update_repository_custom_properties_http_error(
        self,
    ) -> None:
        """Test custom properties update with HTTP error."""
        properties = {'environment': 'production'}

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'PATCH',
                'https://api.github.com/repos/testorg/test-repo/properties/values',
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.update_repository_custom_properties(
                'testorg', 'test-repo', properties
            )

    async def test_github_default_hostname(self) -> None:
        """Test GitHub client with default hostname."""
        config_default = models.GitHubConfiguration(api_key='ghp_test_token')
        client = github.GitHub(config_default)

        self.assertEqual(client.base_url, 'https://github.com')

    async def test_github_custom_hostname(self) -> None:
        """Test GitHub client with custom hostname."""
        config_custom = models.GitHubConfiguration(
            api_key='ghp_test_token', hostname='github.enterprise.com'
        )
        client = github.GitHub(config_custom)

        self.assertEqual(client.base_url, 'https://github.enterprise.com')

    async def test_github_inheritance_from_base_url_client(self) -> None:
        """Test that GitHub inherits properly from BaseURLHTTPClient."""
        self.assertIsInstance(self.instance, ia_http.BaseURLHTTPClient)
        self.assertTrue(hasattr(self.instance, 'get'))
        self.assertTrue(hasattr(self.instance, 'post'))
        self.assertTrue(hasattr(self.instance, 'put'))
        self.assertTrue(hasattr(self.instance, 'patch'))
        self.assertTrue(hasattr(self.instance, 'delete'))

    async def test_get_latest_workflow_run_success(self) -> None:
        """Test successful latest workflow run retrieval."""
        workflow_runs_data = {
            'total_count': 1,
            'workflow_runs': [
                {
                    'id': 12345,
                    'name': 'CI',
                    'node_id': 'MDEwOldvcmtmbG93IFJ1bjEyMzQ1',
                    'check_suite_id': 67890,
                    'check_suite_node_id': 'MDEwOkNoZWNrU3VpdGU2Nzg5MA==',
                    'head_branch': 'main',
                    'head_sha': 'abc123def456',
                    'path': '.github/workflows/ci.yml',
                    'run_number': 42,
                    'run_attempt': 1,
                    'event': 'push',
                    'status': 'completed',
                    'conclusion': 'success',
                    'workflow_id': 98765,
                    'url': 'https://api.github.com/repos/testorg/test-repo/actions/runs/12345',
                    'html_url': 'https://github.com/testorg/test-repo/actions/runs/12345',
                    'created_at': '2023-01-01T12:00:00Z',
                    'updated_at': '2023-01-01T12:05:00Z',
                }
            ],
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/actions/runs',
            ),
        )

        result = await self.instance.get_latest_workflow_run(
            'testorg', 'test-repo'
        )

        self.assertIsInstance(result, models.GitHubWorkflowRun)
        self.assertEqual(result.id, 12345)
        self.assertEqual(result.name, 'CI')
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.conclusion, 'success')
        self.assertEqual(result.run_number, 42)

    async def test_get_latest_workflow_run_no_runs(self) -> None:
        """Test latest workflow run retrieval with no runs."""
        workflow_runs_data = {'total_count': 0, 'workflow_runs': []}

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/actions/runs',
            ),
        )

        result = await self.instance.get_latest_workflow_run(
            'testorg', 'test-repo'
        )

        self.assertIsNone(result)

    async def test_get_latest_workflow_run_http_error(self) -> None:
        """Test latest workflow run retrieval with HTTP error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/actions/runs',
            ),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_latest_workflow_run('testorg', 'test-repo')

    async def test_get_repository_workflow_status_success(self) -> None:
        """Test repository workflow status retrieval."""
        # Create a mock repository
        repo = models.GitHubRepository(
            id=789,
            node_id='R_node789',
            name='test-repo',
            full_name='testorg/test-repo',
            private=False,
            html_url='https://github.com/testorg/test-repo',
            description='Test repository',
            fork=False,
            url='https://api.github.com/repos/testorg/test-repo',
            default_branch='main',
            clone_url='https://github.com/testorg/test-repo.git',
            ssh_url='git@github.com:testorg/test-repo.git',
            git_url='git://github.com/testorg/test-repo.git',
            owner=models.GitHubUser(
                login='testorg',
                id=456,
                node_id='O_node456',
                avatar_url='https://avatars.githubusercontent.com/u/456?v=4',
                url='https://api.github.com/users/testorg',
                html_url='https://github.com/testorg',
                type='Organization',
                site_admin=False,
            ),
        )

        workflow_runs_data = {
            'total_count': 1,
            'workflow_runs': [
                {
                    'id': 54321,
                    'name': 'Build',
                    'node_id': 'MDEwOldvcmtmbG93IFJ1bjU0MzIx',
                    'check_suite_id': 11111,
                    'check_suite_node_id': 'MDEwOkNoZWNrU3VpdGUxMTExMQ==',
                    'head_branch': 'main',
                    'head_sha': 'def456abc789',
                    'path': '.github/workflows/build.yml',
                    'run_number': 15,
                    'event': 'push',
                    'status': 'in_progress',
                    'conclusion': None,
                    'workflow_id': 22222,
                    'url': 'https://api.github.com/repos/testorg/test-repo/actions/runs/54321',
                    'html_url': 'https://github.com/testorg/test-repo/actions/runs/54321',
                    'created_at': '2023-01-02T10:00:00Z',
                }
            ],
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/actions/runs',
            ),
        )

        result = await self.instance.get_repository_workflow_status(repo)

        self.assertEqual(result, 'in_progress')

    async def test_get_repository_workflow_status_no_runs(self) -> None:
        """Test repository workflow status with no runs."""
        repo = models.GitHubRepository(
            id=789,
            node_id='R_node789',
            name='test-repo',
            full_name='testorg/test-repo',
            private=False,
            html_url='https://github.com/testorg/test-repo',
            description='Test repository',
            fork=False,
            url='https://api.github.com/repos/testorg/test-repo',
            default_branch='main',
            clone_url='https://github.com/testorg/test-repo.git',
            ssh_url='git@github.com:testorg/test-repo.git',
            git_url='git://github.com/testorg/test-repo.git',
            owner=models.GitHubUser(
                login='testorg',
                id=456,
                node_id='O_node456',
                avatar_url='https://avatars.githubusercontent.com/u/456?v=4',
                url='https://api.github.com/users/testorg',
                html_url='https://github.com/testorg',
                type='Organization',
                site_admin=False,
            ),
        )

        workflow_runs_data = {'total_count': 0, 'workflow_runs': []}

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/actions/runs',
            ),
        )

        result = await self.instance.get_repository_workflow_status(repo)

        self.assertIsNone(result)

    async def test_check_workflow_file_exists_pattern_no_workflows_dir(
        self,
    ) -> None:
        """Test workflow pattern check when workflows dir doesn't exist."""
        self.http_client_side_effect = httpx.Response(
            404,
            request=httpx.Request(
                'GET',
                'https://api.github.com/repos/testorg/test-repo/contents/.github/workflows',
            ),
        )

        result = await self.instance._check_workflow_file_exists(
            'testorg', 'test-repo', '.github/workflows/python-.*-ci.yml'
        )

        self.assertFalse(result)

    async def test_create_pull_request_success(self) -> None:
        """Test successful pull request creation."""
        self.http_mock_transport_alt_file = pathlib.Path(
            'repos/testorg/testrepo/pulls.json'
        )

        # Create mock context with minimal GitHub repository info
        mock_org = mock.MagicMock()
        mock_org.login = 'testorg'

        mock_repo = mock.MagicMock()
        mock_repo.name = 'testrepo'
        mock_repo.owner = mock_org

        context = mock.MagicMock()
        context.github_repository = mock_repo

        pr_url = await self.instance.create_pull_request(
            context=context,
            title='Test Pull Request',
            body='This is a test PR\n\n- Add new feature\n- Fix existing bug',
            head_branch='imbi-automations/test-workflow',
            base_branch='main',
        )

        self.assertEqual(
            pr_url, 'https://github.com/testorg/testrepo/pull/123'
        )

    async def test_create_pull_request_no_github_repository(self) -> None:
        """Test pull request creation without GitHub repository in context."""
        context = mock.MagicMock()
        context.github_repository = None

        with self.assertRaises(ValueError) as exc_context:
            await self.instance.create_pull_request(
                context=context,
                title='Test Pull Request',
                body='Test body',
                head_branch='feature/test',
                base_branch='main',
            )

        self.assertIn(
            'No GitHub repository in workflow context',
            str(exc_context.exception),
        )

    async def test_create_pull_request_api_failure(self) -> None:
        """Test pull request creation with API failure."""
        self.http_client_side_effect = httpx.Response(
            status_code=422,
            request=httpx.Request('POST', 'http://example.com'),
            json={'message': 'Validation Failed'},
        )

        # Create mock context with GitHub repository
        mock_org = mock.MagicMock()
        mock_org.login = 'testorg'

        mock_repo = mock.MagicMock()
        mock_repo.name = 'testrepo'
        mock_repo.owner = mock_org

        context = mock.MagicMock()
        context.github_repository = mock_repo

        with self.assertRaises(httpx.HTTPError):
            await self.instance.create_pull_request(
                context=context,
                title='Test Pull Request',
                body='Test body',
                head_branch='feature/test',
                base_branch='main',
            )

    async def test_get_file_contents_success(self) -> None:
        """Test successful file contents retrieval."""
        # HTTP mock uses URL path to find test data file

        # Create mock context with GitHub repository
        mock_org = mock.MagicMock()
        mock_org.login = 'testorg'

        mock_repo = mock.MagicMock()
        mock_repo.name = 'testrepo'
        mock_repo.owner = mock_org

        context = mock.MagicMock()
        context.github_repository = mock_repo

        result = await self.instance.get_file_contents(
            context=context, file_path='package.json'
        )

        # The base64 content decodes to package.json content
        expected_content = (
            '{\n  "name": "test-project",\n  "version": "1.0.0"\n}\n'
        )
        self.assertEqual(result, expected_content)

    async def test_get_file_contents_not_found(self) -> None:
        """Test file contents retrieval for non-existent file."""
        self.http_client_side_effect = httpx.Response(
            status_code=404,
            request=httpx.Request('GET', 'http://example.com'),
            json={'message': 'Not Found'},
        )

        mock_org = mock.MagicMock()
        mock_org.login = 'testorg'

        mock_repo = mock.MagicMock()
        mock_repo.name = 'testrepo'
        mock_repo.owner = mock_org

        context = mock.MagicMock()
        context.github_repository = mock_repo

        result = await self.instance.get_file_contents(
            context=context, file_path='nonexistent.txt'
        )

        self.assertIsNone(result)

    async def test_get_file_contents_no_github_repository(self) -> None:
        """Test file contents retrieval without GitHub repository."""
        context = mock.MagicMock()
        context.github_repository = None

        with self.assertRaises(ValueError) as exc_context:
            await self.instance.get_file_contents(
                context=context, file_path='test.txt'
            )

        self.assertIn(
            'No GitHub repository in workflow context',
            str(exc_context.exception),
        )

    async def test_get_file_contents_api_error(self) -> None:
        """Test file contents retrieval with API error."""
        self.http_client_side_effect = httpx.Response(
            status_code=500,
            request=httpx.Request('GET', 'http://example.com'),
            json={'message': 'Internal Server Error'},
        )

        mock_org = mock.MagicMock()
        mock_org.login = 'testorg'

        mock_repo = mock.MagicMock()
        mock_repo.name = 'testrepo'
        mock_repo.owner = mock_org

        context = mock.MagicMock()
        context.github_repository = mock_repo

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_file_contents(
                context=context, file_path='test.txt'
            )


if __name__ == '__main__':
    unittest.main()
