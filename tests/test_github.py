import http
import unittest

import httpx

from imbi_automations import github, models
from imbi_automations import http as ia_http
from tests.base import AsyncTestCase


class TestGitHubClient(AsyncTestCase):
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

    async def test_get_organizations_success(self) -> None:
        """Test successful organizations retrieval."""
        orgs_data = [
            {
                'login': 'org1',
                'id': 123,
                'node_id': 'O_node1',
                'url': 'https://api.github.com/orgs/org1',
                'repos_url': 'https://api.github.com/orgs/org1/repos',
                'events_url': 'https://api.github.com/orgs/org1/events',
                'hooks_url': 'https://api.github.com/orgs/org1/hooks',
                'issues_url': 'https://api.github.com/orgs/org1/issues',
                'members_url': 'https://api.github.com/orgs/org1/members{/member}',
                'public_members_url': 'https://api.github.com/orgs/org1/public_members{/member}',
                'avatar_url': 'https://avatars.githubusercontent.com/u/123?v=4',
                'description': 'Test organization',
            }
        ]

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=orgs_data,
            request=httpx.Request('GET', 'https://api.github.com/user/orgs'),
        )

        result = await self.instance.get_organizations()

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], models.GitHubOrganization)
        self.assertEqual(result[0].login, 'org1')
        self.assertEqual(result[0].id, 123)

    async def test_get_organizations_http_error(self) -> None:
        """Test organizations retrieval with HTTP error."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.UNAUTHORIZED,
            request=httpx.Request('GET', 'https://api.github.com/user/orgs'),
        )

        with self.assertRaises(httpx.HTTPError):
            await self.instance.get_organizations()

    async def test_get_organization_success(self) -> None:
        """Test successful organization retrieval by name."""
        org_data = {
            'login': 'testorg',
            'id': 456,
            'node_id': 'O_node456',
            'url': 'https://api.github.com/orgs/testorg',
            'repos_url': 'https://api.github.com/orgs/testorg/repos',
            'events_url': 'https://api.github.com/orgs/testorg/events',
            'hooks_url': 'https://api.github.com/orgs/testorg/hooks',
            'issues_url': 'https://api.github.com/orgs/testorg/issues',
            'members_url': 'https://api.github.com/orgs/testorg/members{/member}',
            'public_members_url': 'https://api.github.com/orgs/testorg/public_members{/member}',
            'avatar_url': 'https://avatars.githubusercontent.com/u/456?v=4',
            'description': 'Test organization',
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=org_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/orgs/testorg'
            ),
        )

        result = await self.instance.get_organization('testorg')

        self.assertIsInstance(result, models.GitHubOrganization)
        self.assertEqual(result.login, 'testorg')
        self.assertEqual(result.id, 456)

    async def test_get_organization_http_error(self) -> None:
        """Test organization retrieval with HTTP error returns None."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET', 'https://api.github.com/orgs/nonexistent'
            ),
        )

        result = await self.instance.get_organization('nonexistent')

        self.assertIsNone(result)

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

        with self.assertRaises(RuntimeError) as cm:
            await self.instance.get_repository('testorg', 'private-repo')

        self.assertIn('GitHub API access denied', str(cm.exception))
        self.assertIn('Repository access blocked', str(cm.exception))

    async def test_get_repository_forbidden_no_content(self) -> None:
        """Test repository retrieval with 403 Forbidden and no content."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.FORBIDDEN,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/private-repo'
            ),
        )

        with self.assertRaises(RuntimeError) as cm:
            await self.instance.get_repository('testorg', 'private-repo')

        self.assertIn('GitHub API access denied', str(cm.exception))
        self.assertIn('Access forbidden', str(cm.exception))

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
            content=b'Access denied',
            request=httpx.Request(
                'GET', 'https://api.github.com/repositories/12345'
            ),
        )

        result = await self.instance.get_repository_by_id(12345)

        self.assertIsNone(result)

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
        """Test that GitHub inherits properly from BaseURLClient."""
        self.assertIsInstance(self.instance, ia_http.BaseURLClient)
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

    async def test_get_latest_workflow_status_completed_success(self) -> None:
        """Test latest workflow status for completed successful run."""
        workflow_runs_data = {
            'total_count': 1,
            'workflow_runs': [
                {
                    'id': 11111,
                    'name': 'Test',
                    'node_id': 'node11111',
                    'check_suite_id': 22222,
                    'check_suite_node_id': 'node22222',
                    'head_branch': 'main',
                    'head_sha': 'abc123',
                    'path': '.github/workflows/test.yml',
                    'run_number': 5,
                    'event': 'push',
                    'status': 'completed',
                    'conclusion': 'success',
                    'workflow_id': 33333,
                    'url': 'https://api.github.com/repos/org/repo/actions/runs/11111',
                    'html_url': 'https://github.com/org/repo/actions/runs/11111',
                    'created_at': '2023-01-01T10:00:00Z',
                }
            ],
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/org/repo/actions/runs'
            ),
        )

        result = await self.instance.get_latest_workflow_status(
            'org', 'repo', 'main'
        )

        self.assertEqual(
            result, 'success'
        )  # Returns conclusion for completed runs

    async def test_get_latest_workflow_status_in_progress(self) -> None:
        """Test latest workflow status for in-progress run."""
        workflow_runs_data = {
            'total_count': 1,
            'workflow_runs': [
                {
                    'id': 44444,
                    'name': 'Build',
                    'node_id': 'node44444',
                    'check_suite_id': 55555,
                    'check_suite_node_id': 'node55555',
                    'head_branch': 'main',
                    'head_sha': 'def456',
                    'path': '.github/workflows/build.yml',
                    'run_number': 8,
                    'event': 'push',
                    'status': 'in_progress',
                    'conclusion': None,
                    'workflow_id': 66666,
                    'url': 'https://api.github.com/repos/org/repo/actions/runs/44444',
                    'html_url': 'https://github.com/org/repo/actions/runs/44444',
                    'created_at': '2023-01-01T11:00:00Z',
                }
            ],
        }

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/org/repo/actions/runs'
            ),
        )

        result = await self.instance.get_latest_workflow_status('org', 'repo')

        self.assertEqual(
            result, 'in_progress'
        )  # Returns status for non-completed runs

    async def test_get_latest_workflow_status_no_runs(self) -> None:
        """Test latest workflow status with no runs."""
        workflow_runs_data = {'total_count': 0, 'workflow_runs': []}

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=workflow_runs_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/org/repo/actions/runs'
            ),
        )

        result = await self.instance.get_latest_workflow_status(
            'org', 'repo', 'main'
        )

        self.assertIsNone(result)

    async def test_get_repository_identifier_success(self) -> None:
        """Test successful repository identifier retrieval."""
        repo_data = {
            'id': 12345,
            'node_id': 'R_node12345',
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

        result = await self.instance.get_repository_identifier(
            'testorg', 'test-repo', 'main'
        )

        self.assertEqual(result, 12345)

    async def test_get_repository_identifier_not_found(self) -> None:
        """Test repository identifier retrieval when repository not found."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/nonexistent'
            ),
        )

        result = await self.instance.get_repository_identifier(
            'testorg', 'nonexistent'
        )

        self.assertIsNone(result)

    async def test_get_repository_team_permissions_success(self) -> None:
        """Test successful team permissions retrieval."""
        teams_data = [
            {
                'id': 1001,
                'node_id': 'T_node1001',
                'name': 'Core Contributors',
                'slug': 'cc',
                'description': 'Core contributors team',
                'privacy': 'closed',
                'permission': 'maintain',
                'url': 'https://api.github.com/teams/1001',
                'html_url': 'https://github.com/orgs/testorg/teams/cc',
                'members_url': 'https://api.github.com/teams/1001/members{/member}',
                'repositories_url': 'https://api.github.com/teams/1001/repos',
            },
            {
                'id': 1002,
                'node_id': 'T_node1002',
                'name': 'Platform Security Engineering',
                'slug': 'pse',
                'description': 'Security team',
                'privacy': 'closed',
                'permission': 'admin',
                'url': 'https://api.github.com/teams/1002',
                'html_url': 'https://github.com/orgs/testorg/teams/pse',
                'members_url': 'https://api.github.com/teams/1002/members{/member}',
                'repositories_url': 'https://api.github.com/teams/1002/repos',
            },
        ]

        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=teams_data,
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/test-repo/teams'
            ),
        )

        result = await self.instance.get_repository_team_permissions(
            'testorg', 'test-repo'
        )

        expected = {'cc': 'maintain', 'pse': 'admin'}
        self.assertEqual(result, expected)

    async def test_get_repository_team_permissions_empty(self) -> None:
        """Test team permissions retrieval with no teams."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            json=[],
            request=httpx.Request(
                'GET', 'https://api.github.com/repos/testorg/test-repo/teams'
            ),
        )

        result = await self.instance.get_repository_team_permissions(
            'testorg', 'test-repo'
        )

        self.assertEqual(result, {})

    async def test_sync_repository_team_access_no_changes(self) -> None:
        """Test team sync when no changes are needed."""
        current_teams = {'cc': 'maintain', 'pse': 'admin'}
        desired_mappings = {'cc': 'maintain', 'pse': 'admin'}

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'success')

    async def test_sync_repository_team_access_add_team(self) -> None:
        """Test team sync when adding a new team."""
        current_teams = {'cc': 'maintain'}
        desired_mappings = {'cc': 'maintain', 'pse': 'admin'}

        # Mock successful team assignment
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            request=httpx.Request(
                'PUT',
                'https://api.github.com/orgs/testorg/teams/pse/repos/testorg/test-repo',
            ),
        )

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'success')

    async def test_sync_repository_team_access_remove_team(self) -> None:
        """Test team sync when removing a team."""
        current_teams = {'cc': 'maintain', 'old-team': 'push'}
        desired_mappings = {'cc': 'maintain'}

        # Mock successful team removal
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            request=httpx.Request(
                'DELETE',
                'https://api.github.com/orgs/testorg/teams/old-team/repos/testorg/test-repo',
            ),
        )

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'success')

    async def test_sync_repository_team_access_update_permission(self) -> None:
        """Test team sync when updating team permission."""
        current_teams = {'cc': 'push'}
        desired_mappings = {'cc': 'maintain'}

        # Mock successful permission update
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            request=httpx.Request(
                'PUT',
                'https://api.github.com/orgs/testorg/teams/cc/repos/testorg/test-repo',
            ),
        )

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'success')

    async def test_sync_repository_team_access_partial_failure(self) -> None:
        """Test team sync with partial failures."""
        current_teams = {}
        desired_mappings = {'cc': 'maintain', 'pse': 'admin'}

        # Mock responses: first succeeds, second fails
        responses = [
            httpx.Response(http.HTTPStatus.OK),  # cc team assignment succeeds
            httpx.Response(
                http.HTTPStatus.NOT_FOUND
            ),  # pse team assignment fails
        ]

        def side_effect(request):
            return responses.pop(0)

        self.http_client_transport = httpx.MockTransport(side_effect)
        self.instance = github.GitHub(self.config, self.http_client_transport)

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'partial')

    async def test_sync_repository_team_access_complete_failure(self) -> None:
        """Test team sync with complete failure."""
        current_teams = {}
        desired_mappings = {'cc': 'maintain'}

        # Mock failed team assignment
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.NOT_FOUND,
            request=httpx.Request(
                'PUT',
                'https://api.github.com/orgs/testorg/teams/cc/repos/testorg/test-repo',
            ),
        )

        result = await self.instance.sync_repository_team_access(
            'testorg', 'test-repo', current_teams, desired_mappings
        )

        self.assertEqual(result, 'failed')

    async def test_assign_team_to_repository(self) -> None:
        """Test private method for team assignment."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            request=httpx.Request(
                'PUT',
                'https://api.github.com/orgs/testorg/teams/cc/repos/testorg/test-repo',
            ),
        )

        # Should not raise an exception
        await self.instance._assign_team_to_repository(
            'testorg', 'cc', 'test-repo', 'maintain'
        )

    async def test_remove_team_from_repository(self) -> None:
        """Test private method for team removal."""
        self.http_client_side_effect = httpx.Response(
            http.HTTPStatus.OK,
            request=httpx.Request(
                'DELETE',
                'https://api.github.com/orgs/testorg/teams/cc/repos/testorg/test-repo',
            ),
        )

        # Should not raise an exception
        await self.instance._remove_team_from_repository(
            'testorg', 'cc', 'test-repo'
        )


if __name__ == '__main__':
    unittest.main()
