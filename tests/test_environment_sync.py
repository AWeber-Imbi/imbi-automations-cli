import unittest
from unittest import mock

import httpx

from imbi_automations import environment_sync, models
from tests.base import AsyncTestCase


class TestEnvironmentSync(AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()

        # Create mock objects for testing - simpler than complex model creation
        self.imbi_project = mock.Mock()
        self.imbi_project.environments = ['staging', 'production']

        self.github_repo = mock.Mock()
        self.github_repo.full_name = 'testorg/test-project'

        # Use AsyncMock for async methods
        self.github_client = mock.AsyncMock()

    async def test_sync_project_environments_success_create_and_delete(
        self,
    ) -> None:
        """Test successful environment sync with create and delete."""
        # Set up mock GitHub environments (has 'dev' and 'production')
        mock_dev_env = mock.Mock()
        mock_dev_env.name = 'dev'
        mock_production_env = mock.Mock()
        mock_production_env.name = 'production'

        self.github_client.get_repository_environments.return_value = [
            mock_dev_env,
            mock_production_env,
        ]

        # Mock successful operations
        mock_staging_env = mock.Mock()
        mock_staging_env.name = 'staging'
        self.github_client.create_environment.return_value = mock_staging_env
        self.github_client.delete_environment.return_value = True

        # Execute sync with new parameters
        result = await environment_sync.sync_project_environments(
            'testorg',
            'test-project',
            ['staging', 'production'],
            self.github_client,
        )

        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], ['staging'])
        self.assertEqual(result['deleted'], ['dev'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['total_operations'], 2)

        # Verify API calls
        self.github_client.get_repository_environments.assert_called_once_with(
            'testorg', 'test-project'
        )
        self.github_client.create_environment.assert_called_once_with(
            'testorg', 'test-project', 'staging'
        )
        self.github_client.delete_environment.assert_called_once_with(
            'testorg', 'test-project', 'dev'
        )

    async def test_sync_project_environments_no_changes_needed(self) -> None:
        """Test sync when no changes are needed."""
        # Mock GitHub environments that match Imbi exactly
        mock_staging_env = mock.Mock()
        mock_staging_env.name = 'staging'
        mock_production_env = mock.Mock()
        mock_production_env.name = 'production'

        self.github_client.get_repository_environments.return_value = [
            mock_staging_env,
            mock_production_env,
        ]

        # Execute sync
        result = await environment_sync.sync_project_environments(
            'testorg',
            'test-project',
            ['staging', 'production'],
            self.github_client,
        )

        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], [])
        self.assertEqual(result['deleted'], [])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['total_operations'], 0)

        # Verify API calls
        self.github_client.get_repository_environments.assert_called_once_with(
            'testorg', 'test-project'
        )
        self.github_client.create_environment.assert_not_called()
        self.github_client.delete_environment.assert_not_called()

    async def test_sync_project_environments_github_not_found(self) -> None:
        """Test sync when GitHub repository is not found."""
        # Set up mock to raise GitHubNotFoundError
        self.github_client.get_repository_environments.side_effect = (
            models.GitHubNotFoundError('Repository not found')
        )

        # Execute sync
        result = await environment_sync.sync_project_environments(
            'testorg',
            'test-project',
            ['staging', 'production'],
            self.github_client,
        )

        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['created'], [])
        self.assertEqual(result['deleted'], [])
        self.assertIn(
            'Repository testorg/test-project not found', result['errors']
        )
        self.assertEqual(result['total_operations'], 0)

    async def test_sync_project_environments_create_error(self) -> None:
        """Test sync when environment creation fails."""
        # Set up mock with no existing environments
        self.github_client.get_repository_environments.return_value = []
        self.github_client.create_environment.side_effect = httpx.HTTPError(
            'Creation failed'
        )

        # Execute sync
        result = await environment_sync.sync_project_environments(
            'testorg',
            'test-project',
            ['staging', 'production'],
            self.github_client,
        )

        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['created'], [])
        self.assertEqual(result['deleted'], [])
        self.assertEqual(len(result['errors']), 2)  # Two environments failed
        self.assertEqual(result['total_operations'], 2)

    async def test_sync_project_environments_case_insensitive(self) -> None:
        """Test sync with case differences between Imbi and GitHub."""
        # Mock GitHub environments with lowercase names
        mock_staging_env = mock.Mock()
        mock_staging_env.name = 'staging'
        mock_production_env = mock.Mock()
        mock_production_env.name = 'production'

        self.github_client.get_repository_environments.return_value = [
            mock_staging_env,
            mock_production_env,
        ]

        # Execute sync with title case Imbi environments
        result = await environment_sync.sync_project_environments(
            'testorg',
            'test-project',
            ['Staging', 'Production'],
            self.github_client,
        )

        # Verify no changes needed due to case-insensitive matching
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], [])
        self.assertEqual(result['deleted'], [])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['total_operations'], 0)

        # Verify no API calls were made for create/delete
        self.github_client.get_repository_environments.assert_called_once_with(
            'testorg', 'test-project'
        )
        self.github_client.create_environment.assert_not_called()
        self.github_client.delete_environment.assert_not_called()

    def test_should_sync_environments(self) -> None:
        """Test should_sync_environments function."""
        # Project with environments should sync
        project_with_envs = mock.Mock()
        project_with_envs.environments = ['staging', 'production']
        project_with_envs.id = 1
        project_with_envs.name = 'test'
        self.assertTrue(
            environment_sync.should_sync_environments(project_with_envs)
        )

        # Project with empty environments should not sync
        project_empty_envs = mock.Mock()
        project_empty_envs.environments = []
        project_empty_envs.id = 1
        project_empty_envs.name = 'test'
        self.assertFalse(
            environment_sync.should_sync_environments(project_empty_envs)
        )

        # Project with None environments should not sync
        project_no_envs = mock.Mock()
        project_no_envs.environments = None
        project_no_envs.id = 1
        project_no_envs.name = 'test'
        self.assertFalse(
            environment_sync.should_sync_environments(project_no_envs)
        )

    def test_get_environment_sync_summary(self) -> None:
        """Test get_environment_sync_summary function."""
        # Success with no changes
        result_no_changes = {
            'success': True,
            'created': [],
            'deleted': [],
            'errors': [],
            'total_operations': 0,
        }
        summary = environment_sync.get_environment_sync_summary(
            result_no_changes
        )
        self.assertEqual(summary, 'Success: No changes needed')

        # Success with changes
        result_with_changes = {
            'success': True,
            'created': ['staging'],
            'deleted': ['dev'],
            'errors': [],
            'total_operations': 2,
        }
        summary = environment_sync.get_environment_sync_summary(
            result_with_changes
        )
        self.assertEqual(summary, 'Success: Created 1, deleted 1 environments')

        # Failure with errors
        result_with_errors = {
            'success': False,
            'created': [],
            'deleted': [],
            'errors': ['Error 1', 'Error 2'],
            'total_operations': 0,
        }
        summary = environment_sync.get_environment_sync_summary(
            result_with_errors
        )
        self.assertEqual(summary, 'Failed: Error 1; Error 2')

        # Failure without errors
        result_unknown_error = {
            'success': False,
            'created': [],
            'deleted': [],
            'errors': [],
            'total_operations': 0,
        }
        summary = environment_sync.get_environment_sync_summary(
            result_unknown_error
        )
        self.assertEqual(summary, 'Failed: Unknown error')


if __name__ == '__main__':
    unittest.main()
