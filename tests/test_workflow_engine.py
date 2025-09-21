import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import engine, models
from tests import base


class TestWorkflowEngine(base.AsyncTestCase):
    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create mock clients
        self.mock_github = mock.AsyncMock()
        self.mock_gitlab = mock.AsyncMock()
        self.mock_imbi = mock.AsyncMock()

        # Create workflow engine instance
        self.workflow_engine = engine.WorkflowEngine(
            github_client=self.mock_github,
            gitlab_client=self.mock_gitlab,
            imbi_client=self.mock_imbi,
        )

        # Create test workflow
        self.temp_dir = tempfile.mkdtemp()
        self.workflow_dir = pathlib.Path(self.temp_dir) / 'test-workflow'
        self.workflow_dir.mkdir()

        # Create workflow configuration
        self.workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            actions=[
                models.WorkflowAction(
                    name='get-status',
                    value=models.WorkflowActionValue(
                        client='github',
                        method='get_latest_workflow_status',
                        kwargs=models.WorkflowActionKwargs.model_validate(
                            {
                                'org': '{{ github_repository.owner.login }}',
                                'repo_name': '{{ github_repository.name }}',
                                'branch': 'main',
                            }
                        ),
                    ),
                    target=models.WorkflowActionTarget(
                        client='imbi',
                        method='update_project_fact',
                        kwargs=models.WorkflowActionKwargs.model_validate(
                            {
                                'project_id': '{{ imbi_project.id }}',
                                'fact_name': 'CI Pipeline Status',
                                'value': '{{ actions["get-status"].result }}',
                            }
                        ),
                    ),
                    value_mapping={
                        'success': 'pass',
                        'failure': 'fail',
                        'null': 'null',
                    },
                )
            ],
        )

        self.workflow = models.Workflow(
            path=self.workflow_dir, configuration=self.workflow_config
        )

        # Create test GitHub repository
        self.github_repo = models.GitHubRepository(
            id=123,
            node_id='R_123',
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
                node_id='O_456',
                avatar_url='https://avatars.githubusercontent.com/u/456?v=4',
                url='https://api.github.com/users/testorg',
                html_url='https://github.com/testorg',
                type='Organization',
                site_admin=False,
            ),
        )

        # Create test Imbi project
        self.imbi_project = models.ImbiProject(
            id=789,
            name='Test Project',
            description='Test project',
            namespace='Test Org',
            namespace_slug='test-org',
            project_type='API',
            project_type_slug='api',
            slug='test-project',
            imbi_url='https://imbi.example.com/ui/projects/789',
            dependencies=None,
            environments=None,
            facts=None,
            identifiers=None,
            links=None,
            project_score=None,
            urls=None,
        )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_workflow_engine_init(self) -> None:
        """Test WorkflowEngine initialization."""
        engine_instance = engine.WorkflowEngine(
            github_client=self.mock_github,
            gitlab_client=self.mock_gitlab,
            imbi_client=self.mock_imbi,
        )

        self.assertEqual(engine_instance.github, self.mock_github)
        self.assertEqual(engine_instance.gitlab, self.mock_gitlab)
        self.assertEqual(engine_instance.imbi, self.mock_imbi)
        self.assertIsInstance(
            engine_instance.action_results, engine.ActionResults
        )

    def test_create_template_context(self) -> None:
        """Test template context creation."""
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        context = self.workflow_engine._create_template_context(workflow_run)

        self.assertIn('workflow', context)
        self.assertIn('github_repository', context)
        self.assertIn('imbi_project', context)
        self.assertIn('actions', context)
        self.assertEqual(context['github_repository'], self.github_repo)
        self.assertEqual(context['imbi_project'], self.imbi_project)

    def test_render_template_kwargs(self) -> None:
        """Test template rendering in kwargs."""
        kwargs = models.WorkflowActionKwargs.model_validate(
            {
                'org': '{{ github_repository.owner.login }}',
                'repo_name': '{{ github_repository.name }}',
                'static_value': 'main',
            }
        )

        context = {
            'github_repository': self.github_repo,
            'imbi_project': self.imbi_project,
        }

        result = self.workflow_engine._render_template_kwargs(kwargs, context)

        self.assertEqual(result['org'], 'testorg')
        self.assertEqual(result['repo_name'], 'test-repo')
        self.assertEqual(result['static_value'], 'main')

    def test_get_client_success(self) -> None:
        """Test successful client retrieval."""
        github_client = self.workflow_engine._get_client('github')
        imbi_client = self.workflow_engine._get_client('imbi')

        self.assertEqual(github_client, self.mock_github)
        self.assertEqual(imbi_client, self.mock_imbi)

    def test_get_client_not_available(self) -> None:
        """Test client retrieval for unavailable client."""
        with self.assertRaises(ValueError) as cm:
            self.workflow_engine._get_client('nonexistent')

        self.assertIn('Client not available', str(cm.exception))

    def test_apply_value_mapping(self) -> None:
        """Test value mapping application."""
        mapping = {'success': 'pass', 'failure': 'fail', 'null': 'null'}

        # Test mapping
        self.assertEqual(
            self.workflow_engine._apply_value_mapping('success', mapping),
            'pass',
        )
        self.assertEqual(
            self.workflow_engine._apply_value_mapping('failure', mapping),
            'fail',
        )

        # Test no mapping
        self.assertEqual(
            self.workflow_engine._apply_value_mapping('success', None),
            'success',
        )

        # Test unmapped value
        self.assertEqual(
            self.workflow_engine._apply_value_mapping('unknown', mapping),
            'unknown',
        )

        # Test None value
        self.assertEqual(
            self.workflow_engine._apply_value_mapping(None, mapping), 'null'
        )

    async def test_execute_action_complete_flow(self) -> None:
        """Test complete action execution flow."""
        # Setup mock return values
        self.mock_github.get_latest_workflow_status.return_value = 'success'

        action = self.workflow_config.actions[0]  # get-status action
        context = {
            'github_repository': self.github_repo,
            'imbi_project': self.imbi_project,
            'actions': {},
        }

        result = await self.workflow_engine._execute_action(action, context)

        # Verify value method was called correctly
        self.mock_github.get_latest_workflow_status.assert_called_once_with(
            org='testorg', repo_name='test-repo', branch='main'
        )

        # Verify value mapping was applied
        self.assertEqual(result, 'pass')  # 'success' mapped to 'pass'

        # Verify target method was called correctly
        self.mock_imbi.update_project_fact.assert_called_once_with(
            project_id=789, fact_name='CI Pipeline Status', value='pass'
        )

        # Verify result was stored
        self.assertEqual(
            self.workflow_engine.action_results['get-status']['result'], 'pass'
        )

    async def test_execute_action_no_target(self) -> None:
        """Test action execution without target."""
        # Create action without target
        action = models.WorkflowAction(
            name='get-only',
            value=models.WorkflowActionValue(
                client='github',
                method='get_latest_workflow_status',
                kwargs=models.WorkflowActionKwargs.model_validate(
                    {'org': 'testorg', 'repo_name': 'test-repo'}
                ),
            ),
        )

        self.mock_github.get_latest_workflow_status.return_value = 'completed'

        context = {'actions': {}}
        result = await self.workflow_engine._execute_action(action, context)

        self.assertEqual(result, 'completed')
        self.mock_github.get_latest_workflow_status.assert_called_once()
        # Target should not be called
        self.mock_imbi.update_project_fact.assert_not_called()

    async def test_execute_action_client_error(self) -> None:
        """Test action execution with client method error."""
        self.mock_github.get_latest_workflow_status.side_effect = RuntimeError(
            'API Error'
        )

        action = self.workflow_config.actions[0]
        context = {
            'github_repository': self.github_repo,
            'imbi_project': self.imbi_project,
            'actions': {},
        }

        with self.assertRaises(RuntimeError) as cm:
            await self.workflow_engine._execute_action(action, context)

        self.assertIn('API Error', str(cm.exception))

    async def test_execute_workflow_complete(self) -> None:
        """Test complete workflow execution."""
        self.mock_github.get_latest_workflow_status.return_value = 'failure'

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine.execute(workflow_run)

        # Verify all actions were executed
        self.mock_github.get_latest_workflow_status.assert_called_once_with(
            org='testorg', repo_name='test-repo', branch='main'
        )

        self.mock_imbi.update_project_fact.assert_called_once_with(
            project_id=789,
            fact_name='CI Pipeline Status',
            value='fail',  # 'failure' mapped to 'fail'
        )

    async def test_execute_workflow_action_failure(self) -> None:
        """Test workflow execution with action failure."""
        self.mock_github.get_latest_workflow_status.side_effect = Exception(
            'Network error'
        )

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        with self.assertRaises(Exception) as cm:
            await self.workflow_engine.execute(workflow_run)

        self.assertIn('Network error', str(cm.exception))

    def test_workflow_engine_no_clients(self) -> None:
        """Test workflow engine with no clients initialized."""
        engine_instance = engine.WorkflowEngine()

        self.assertIsNone(engine_instance.github)
        self.assertIsNone(engine_instance.gitlab)
        self.assertIsNone(engine_instance.imbi)


if __name__ == '__main__':
    unittest.main()
