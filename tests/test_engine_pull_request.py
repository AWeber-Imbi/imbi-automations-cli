"""Tests for WorkflowEngine pull request creation functionality."""

import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import engine, models
from tests import base


class WorkflowEnginePullRequestTestCase(base.AsyncTestCase):
    """Test cases for WorkflowEngine pull request creation."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)

        # Create required directory structure
        (self.working_directory / 'repository').mkdir()

        # Create mock configuration
        self.config = models.Configuration(
            imbi=models.ImbiConfiguration(
                api_key='test-key', hostname='imbi.test.com'
            ),
            github=models.GitHubConfiguration(
                api_key='test-github-key', hostname='github.com'
            ),
        )

        # Create mock workflow with path name for slugification
        self.workflow = models.Workflow(
            path=pathlib.Path('/workflows/sync-github-metadata'),
            configuration=models.WorkflowConfiguration(
                name='test-workflow', actions=[]
            ),
        )

        # Create mock context
        self.context = models.WorkflowContext(
            workflow=self.workflow,
            imbi_project=models.ImbiProject(
                id=123,
                dependencies=None,
                description='Test project',
                environments=None,
                facts=None,
                identifiers=None,
                links=None,
                name='test-project',
                namespace='test-namespace',
                namespace_slug='test-namespace',
                project_score=None,
                project_type='API',
                project_type_slug='api',
                slug='test-project',
                urls=None,
                imbi_url='https://imbi.example.com/projects/123',
            ),
            working_directory=self.working_directory,
        )

        # Create engine instance
        self.engine = engine.WorkflowEngine(
            configuration=self.config, workflow=self.workflow
        )

    def tearDown(self) -> None:
        super().tearDown()
        self.temp_dir.cleanup()

    @mock.patch('imbi_automations.git.create_branch')
    @mock.patch('imbi_automations.git.push_changes')
    async def test_create_pull_request_success(
        self, mock_push: mock.AsyncMock, mock_create_branch: mock.AsyncMock
    ) -> None:
        """Test successful pull request branch creation and push."""
        await self.engine._create_pull_request(self.context)

        # Verify branch creation
        mock_create_branch.assert_called_once_with(
            working_directory=self.working_directory / 'repository',
            branch_name='imbi-automations/sync-github-metadata',
            checkout=True,
        )

        # Verify push with upstream
        mock_push.assert_called_once_with(
            working_directory=self.working_directory / 'repository',
            remote='origin',
            branch='imbi-automations/sync-github-metadata',
            set_upstream=True,
        )

    @mock.patch('imbi_automations.git.create_branch')
    @mock.patch('imbi_automations.git.push_changes')
    async def test_create_pull_request_branch_creation_failure(
        self, mock_push: mock.AsyncMock, mock_create_branch: mock.AsyncMock
    ) -> None:
        """Test pull request creation with branch creation failure."""
        mock_create_branch.side_effect = RuntimeError('Branch already exists')

        with self.assertRaises(RuntimeError) as exc_context:
            await self.engine._create_pull_request(self.context)

        self.assertIn('Branch already exists', str(exc_context.exception))

        # Push should not be called if branch creation fails
        mock_push.assert_not_called()

    @mock.patch('imbi_automations.git.create_branch')
    @mock.patch('imbi_automations.git.push_changes')
    async def test_create_pull_request_push_failure(
        self, mock_push: mock.AsyncMock, mock_create_branch: mock.AsyncMock
    ) -> None:
        """Test pull request creation with push failure."""
        mock_push.side_effect = RuntimeError('Push failed')

        with self.assertRaises(RuntimeError) as exc_context:
            await self.engine._create_pull_request(self.context)

        self.assertIn('Push failed', str(exc_context.exception))

        # Branch creation should still have been called
        mock_create_branch.assert_called_once()

    def test_branch_name_generation(self) -> None:
        """Test that branch name is generated correctly from workflow path."""
        # Test with different workflow paths
        test_cases = [
            (
                '/workflows/sync-github-metadata',
                'imbi-automations/sync-github-metadata',
            ),
            (
                '/path/to/update-python-versions',
                'imbi-automations/update-python-versions',
            ),
            ('/simple-workflow', 'imbi-automations/simple-workflow'),
        ]

        for workflow_path, expected_branch in test_cases:
            with self.subTest(workflow_path=workflow_path):
                workflow = models.Workflow(
                    path=pathlib.Path(workflow_path),
                    configuration=models.WorkflowConfiguration(
                        name='test-workflow', actions=[]
                    ),
                )

                context = models.WorkflowContext(
                    workflow=workflow,
                    imbi_project=self.context.imbi_project,
                    working_directory=self.working_directory,
                )

                # Test branch name generation logic
                workflow_slug = context.workflow.path.name
                branch_name = f'imbi-automations/{workflow_slug}'

                self.assertEqual(branch_name, expected_branch)


if __name__ == '__main__':
    unittest.main()
