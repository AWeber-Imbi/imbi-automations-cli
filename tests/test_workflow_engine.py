import datetime
import pathlib
import tempfile
import typing
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
            clone_repository=False,  # Disable cloning for basic tests
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

    def test_render_template_kwargs_action_result(self) -> None:
        """Test template rendering for action results."""
        kwargs = models.WorkflowActionKwargs.model_validate(
            {
                'org': '{{ github_repository.owner.login }}',
                'current_teams': "{{ actions['get-teams'].result }}",
                'static_value': 'test',
            }
        )

        # Set up action results with a dictionary
        self.workflow_engine.action_results['get-teams'] = {
            'result': {'team1': 'admin', 'team2': 'maintain'}
        }

        context = {
            'github_repository': self.github_repo,
            'imbi_project': self.imbi_project,
            'actions': self.workflow_engine.action_results,
        }

        result = self.workflow_engine._render_template_kwargs(kwargs, context)

        self.assertEqual(result['org'], 'testorg')
        self.assertEqual(
            result['current_teams'], {'team1': 'admin', 'team2': 'maintain'}
        )
        self.assertEqual(result['static_value'], 'test')
        self.assertIsInstance(result['current_teams'], dict)

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

    def test_project_matches_filter_no_filter(self) -> None:
        """Test project matching when no filter is configured."""
        # Create workflow with no filter
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=None,  # No filter
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should match any project when no filter
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertTrue(result)

    def test_project_matches_filter_project_ids_match(self) -> None:
        """Test project matching with project_ids filter - match."""
        # Create workflow with project_ids filter that includes test project
        workflow_filter = models.WorkflowFilter(project_ids=[789, 999])
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should match because project ID 789 is in filter
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertTrue(result)

    def test_project_matches_filter_project_ids_no_match(self) -> None:
        """Test project matching with project_ids filter - no match."""
        # Create workflow with project_ids filter that excludes test project
        workflow_filter = models.WorkflowFilter(project_ids=[111, 222])
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should not match because project ID 789 is not in filter
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertFalse(result)

    def test_project_matches_filter_project_types_match(self) -> None:
        """Test project matching with project_types filter - match."""
        # Create workflow with project_types filter including test project type
        workflow_filter = models.WorkflowFilter(project_types=['api', 'web'])
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should match because project type 'api' is in filter
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertTrue(result)

    def test_project_matches_filter_project_types_no_match(self) -> None:
        """Test project matching with project_types filter - no match."""
        # Create workflow with project_types filter excluding test project type
        workflow_filter = models.WorkflowFilter(
            project_types=['web', 'daemon']
        )
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should not match because project type 'api' is not in filter
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertFalse(result)

    def test_project_matches_filter_combined_filters_match(self) -> None:
        """Test project matching with both filters - match."""
        # Create workflow with both filters that include our test project
        workflow_filter = models.WorkflowFilter(
            project_ids=[789, 999], project_types=['api', 'web']
        )
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should match because both project ID and type are in filters
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertTrue(result)

    def test_project_matches_filter_combined_filters_no_match_id(self) -> None:
        """Test combined filters - no match on project_ids."""
        # Create workflow with filters where project_ids excludes test project
        workflow_filter = models.WorkflowFilter(
            project_ids=[111, 222], project_types=['api', 'web']
        )
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should not match - project ID not in filter despite type match
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertFalse(result)

    def test_project_matches_filter_combined_filters_no_match_type(
        self,
    ) -> None:
        """Test combined filters - no match on project_types."""
        # Create workflow with filters excluding test project
        workflow_filter = models.WorkflowFilter(
            project_ids=[789, 999], project_types=['web', 'daemon']
        )
        workflow_config = models.WorkflowConfiguration(
            name='test-workflow',
            description='Test workflow',
            filter=workflow_filter,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        automation_engine = engine.AutomationEngine(
            args=mock.MagicMock(),
            configuration=models.Configuration(),
            iterator=engine.AutomationIterator.imbi_projects,
            workflow=workflow,
        )

        # Should not match - project type not in filter despite ID match
        result = automation_engine._project_matches_filter(self.imbi_project)
        self.assertFalse(result)

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_setup_repository_clone_github(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test repository cloning setup with GitHub repository."""
        mock_working_dir = pathlib.Path('/tmp/test-clone/repository')  # noqa: S108
        mock_clone.return_value = mock_working_dir

        # Create workflow run with GitHub repository
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._setup_repository_clone(workflow_run)

        # Verify clone was called with GitHub repository details (SSH)
        mock_clone.assert_called_once_with(
            clone_url='git@github.com:testorg/test-repo.git',
            branch='main',
            depth=1,
        )

        # Verify working directory was set
        self.assertEqual(workflow_run.working_directory, mock_working_dir)

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_setup_repository_clone_gitlab(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test repository cloning setup with GitLab project."""
        mock_working_dir = pathlib.Path('/tmp/test-clone/repository')  # noqa: S108
        mock_clone.return_value = mock_working_dir

        # Create GitLab project
        gitlab_project = models.GitLabProject(
            id=123,
            name='test-project',
            path='test-project',
            path_with_namespace='group/test-project',
            name_with_namespace='Group / Test Project',
            created_at=datetime.datetime.now(datetime.UTC),
            default_branch='develop',
            ssh_url_to_repo='git@gitlab.com:group/test-project.git',
            http_url_to_repo='https://gitlab.com/group/test-project.git',
            web_url='https://gitlab.com/group/test-project',
            visibility='private',
            namespace=models.GitLabNamespace(
                id=456,
                name='Group',
                path='group',
                kind='group',
                full_path='group',
                web_url='https://gitlab.com/group',
            ),
        )

        # Create workflow run with GitLab project
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            gitlab_project=gitlab_project,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._setup_repository_clone(workflow_run)

        # Verify clone was called with GitLab project details (SSH)
        mock_clone.assert_called_once_with(
            clone_url='git@gitlab.com:group/test-project.git',
            branch='develop',
            depth=1,
        )

        # Verify working directory was set
        self.assertEqual(workflow_run.working_directory, mock_working_dir)

    async def test_setup_repository_clone_no_repository(self) -> None:
        """Test repository cloning setup with no repository available."""
        # Create workflow run with no GitHub or GitLab repository
        workflow_run = models.WorkflowRun(
            workflow=self.workflow, imbi_project=self.imbi_project
        )

        with self.assertRaises(RuntimeError) as context:
            await self.workflow_engine._setup_repository_clone(workflow_run)

        self.assertIn(
            'No repository available for cloning', str(context.exception)
        )

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_execute_workflow_with_cloning(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test complete workflow execution with repository cloning."""
        mock_working_dir = pathlib.Path('/tmp/test-clone/repository')  # noqa: S108
        mock_clone.return_value = mock_working_dir

        # Create workflow configuration with cloning enabled
        workflow_config = models.WorkflowConfiguration(
            name='test-clone-workflow',
            clone_repository=True,
            create_pull_request=False,
            actions=[
                models.WorkflowAction(
                    name='test-action',
                    value=models.WorkflowActionValue(
                        client='github',
                        method='get_latest_workflow_status',
                        kwargs=models.WorkflowActionKwargs.model_validate(
                            {
                                'org': '{{ github_repository.owner.login }}',
                                'repo_name': '{{ github_repository.name }}',
                            }
                        ),
                    ),
                )
            ],
        )

        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        workflow_run = models.WorkflowRun(
            workflow=workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        # Mock the GitHub method
        mock_github = mock.AsyncMock()
        mock_github.get_latest_workflow_status.return_value = 'success'
        self.workflow_engine.github = mock_github

        await self.workflow_engine.execute(workflow_run)

        # Verify clone was called with SSH URL
        mock_clone.assert_called_once_with(
            clone_url='git@github.com:testorg/test-repo.git',
            branch='main',
            depth=1,
        )

        # Verify working directory was set
        self.assertEqual(workflow_run.working_directory, mock_working_dir)

        # Verify action was executed
        mock_github.get_latest_workflow_status.assert_called_once()

    def test_create_template_context_with_working_directory(self) -> None:
        """Test template context creation includes working directory."""
        mock_working_dir = pathlib.Path('/mock/working/dir')

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        context = self.workflow_engine._create_template_context(workflow_run)

        self.assertIn('working_directory', context)
        self.assertEqual(context['working_directory'], mock_working_dir)

    async def test_execute_action_callable_type(self) -> None:
        """Test action execution with explicit callable type."""
        # Create action with explicit callable type
        action = models.WorkflowAction(
            name='test-callable',
            type=models.WorkflowActionTypes.callable,
            value=models.WorkflowActionValue(
                client='github',
                method='get_latest_workflow_status',
                kwargs=models.WorkflowActionKwargs.model_validate(
                    {'org': 'testorg', 'repo_name': 'test-repo'}
                ),
            ),
        )

        self.mock_github.get_latest_workflow_status.return_value = 'success'

        context = {'actions': {}}
        result = await self.workflow_engine._execute_action(action, context)

        self.assertEqual(result, 'success')
        self.mock_github.get_latest_workflow_status.assert_called_once()

    async def test_execute_action_templates_type(self) -> None:
        """Test action execution with templates type."""
        # Create action with templates type
        action = models.WorkflowAction(
            name='test-templates',
            type=models.WorkflowActionTypes.templates,
            value=models.WorkflowActionValue(
                client='github',  # Not used for templates actions
                method='unused',  # Not used for templates actions
            ),
        )

        # Create mock workflow run with working directory
        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {
            'workflow': workflow_run.workflow,
            'workflow_run': workflow_run,
            'actions': {},
        }

        # Templates directory doesn't exist, expect 'no_templates' result
        result = await self.workflow_engine._execute_action(action, context)

        self.assertEqual(result, 'no_templates')
        self.assertIn('test-templates', self.workflow_engine.action_results)
        self.assertEqual(
            self.workflow_engine.action_results['test-templates']['result'],
            'no_templates',
        )

    async def test_execute_action_unsupported_type(self) -> None:
        """Test action execution with unsupported type."""
        # Create action with invalid type (manually set)
        action = models.WorkflowAction(
            name='test-invalid',
            value=models.WorkflowActionValue(
                client='github', method='get_latest_workflow_status'
            ),
        )
        # Manually override the type to an invalid value
        action.type = 'invalid_type'

        context = {'actions': {}}

        with self.assertRaises(ValueError) as cm:
            await self.workflow_engine._execute_action(action, context)

        self.assertIn(
            'Unsupported action type: invalid_type', str(cm.exception)
        )

    async def test_execute_callable_action_direct(self) -> None:
        """Test direct callable action execution."""
        action = models.WorkflowAction(
            name='direct-callable',
            type=models.WorkflowActionTypes.callable,
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
        result = await self.workflow_engine._execute_callable_action(
            action, context
        )

        self.assertEqual(result, 'completed')
        self.assertEqual(
            self.workflow_engine.action_results['direct-callable']['result'],
            'completed',
        )

    async def test_execute_templates_action_direct(self) -> None:
        """Test direct templates action execution."""
        action = models.WorkflowAction(
            name='direct-templates',
            type=models.WorkflowActionTypes.templates,
            value=models.WorkflowActionValue(client='unused', method='unused'),
        )

        # Create mock workflow run with working directory
        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {
            'workflow': workflow_run.workflow,
            'workflow_run': workflow_run,
            'actions': {},
        }
        result = await self.workflow_engine._execute_templates_action(
            action, context
        )

        self.assertEqual(result, 'no_templates')
        self.assertIn('direct-templates', self.workflow_engine.action_results)

    @mock.patch('pathlib.Path.exists')
    @mock.patch('pathlib.Path.is_dir')
    @mock.patch('pathlib.Path.write_text')
    @mock.patch('pathlib.Path.read_text')
    @mock.patch('pathlib.Path.stat')
    @mock.patch('pathlib.Path.chmod')
    @mock.patch('pathlib.Path.mkdir')
    @mock.patch('os.walk')
    async def test_execute_templates_action_with_files(
        self,
        mock_walk: mock.Mock,
        mock_mkdir: mock.Mock,
        mock_chmod: mock.Mock,
        mock_stat: mock.Mock,
        mock_read_text: mock.Mock,
        mock_write_text: mock.Mock,
        mock_is_dir: mock.Mock,
        mock_exists: mock.Mock,
    ) -> None:
        """Test templates action with actual template files."""
        # Set up mock working directory and workflow
        mock_working_dir = pathlib.Path('/mock/working/dir')
        templates_dir = self.workflow_dir / 'templates'

        # Mock templates directory existence
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Create mock workflow run with working directory
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        # Mock templates directory structure
        mock_walk.return_value = [
            (str(templates_dir), [], ['.gitignore', 'config.json.j2']),
            (str(templates_dir / 'subdir'), [], ['script.sh']),
        ]

        # Mock template file content
        mock_read_text.return_value = 'Project: {{ imbi_project.name }}\nRepo: {{ github_repository.name }}'  # noqa: E501

        # Mock file stats for permission copying
        mock_file_stat = mock.Mock()
        mock_file_stat.st_mode = 0o644
        mock_stat.return_value = mock_file_stat

        action = models.WorkflowAction(
            name='copy-templates',
            type=models.WorkflowActionTypes.templates,
            value=models.WorkflowActionValue(client='unused', method='unused'),
        )

        context = {
            'workflow': workflow_run.workflow,
            'workflow_run': workflow_run,
            'actions': {},
            'imbi_project': self.imbi_project,
            'github_repository': self.github_repo,
            'working_directory': mock_working_dir,
        }

        with mock.patch('shutil.copy2') as mock_copy2:
            result = await self.workflow_engine._execute_templates_action(
                action, context
            )

            # Should be successful
            self.assertIsInstance(result, dict)
            self.assertEqual(result['status'], 'success')
            self.assertEqual(len(result['copied_files']), 3)
            self.assertIn('.gitignore', result['copied_files'])
            self.assertIn(
                'config.json', result['copied_files']
            )  # .j2 extension removed
            self.assertIn('subdir/script.sh', result['copied_files'])
            # commit_sha should not be in individual action results anymore
            self.assertNotIn('commit_sha', result)

        # Verify Jinja2 rendering was called for .j2 file
        mock_read_text.assert_called()
        mock_write_text.assert_called()

        # Verify regular file copying was called
        mock_copy2.assert_called()

    async def test_execute_templates_action_no_working_directory(self) -> None:
        """Test templates action without working directory (should fail)."""
        action = models.WorkflowAction(
            name='test-templates-no-wd',
            type=models.WorkflowActionTypes.templates,
            value=models.WorkflowActionValue(client='unused', method='unused'),
        )

        # Create workflow run without working directory
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=None,
            imbi_project=self.imbi_project,
        )

        context = {
            'workflow': workflow_run.workflow,
            'workflow_run': workflow_run,
            'actions': {},
        }

        with self.assertRaises(RuntimeError) as cm:
            await self.workflow_engine._execute_templates_action(
                action, context
            )

        self.assertIn('requires cloned repository', str(cm.exception))

    @mock.patch('pathlib.Path.write_text')
    @mock.patch('pathlib.Path.read_text')
    @mock.patch('pathlib.Path.stat')
    @mock.patch('pathlib.Path.chmod')
    async def test_render_template_file(
        self,
        mock_chmod: mock.Mock,
        mock_stat: mock.Mock,
        mock_read_text: mock.Mock,
        mock_write_text: mock.Mock,
    ) -> None:
        """Test Jinja2 template file rendering."""
        template_file = pathlib.Path('/templates/test.txt.j2')
        target_file = pathlib.Path('/working/test.txt')

        # Mock template content
        mock_read_text.return_value = 'Hello {{ imbi_project.name }}!'

        # Mock file permissions
        mock_file_stat = mock.Mock()
        mock_file_stat.st_mode = 0o755
        mock_stat.return_value = mock_file_stat

        context = {
            'imbi_project': self.imbi_project,
            'github_repository': self.github_repo,
        }

        await self.workflow_engine._render_template_file(
            template_file, target_file, context
        )

        # Verify template was read
        mock_read_text.assert_called_once_with(encoding='utf-8')

        # Verify rendered content was written
        mock_write_text.assert_called_once_with(
            'Hello Test Project!', encoding='utf-8'
        )

        # Verify permissions were copied
        mock_chmod.assert_called_once_with(0o755)

    @mock.patch('imbi_automations.git.push_changes')
    @mock.patch('imbi_automations.git.add_files')
    @mock.patch('imbi_automations.git.commit_changes')
    async def test_commit_workflow_changes_single_action(
        self,
        mock_commit: mock.Mock,
        mock_add_files: mock.Mock,
        mock_push: mock.Mock,
    ) -> None:
        """Test workflow-level commit with single template action."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_commit.return_value = 'def456'

        # Set up action results with copied files
        self.workflow_engine.action_results['copy-templates'] = {
            'result': {
                'status': 'success',
                'copied_files': ['.gitignore', 'package.json'],
                'errors': [],
            }
        }

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._commit_workflow_changes(
            workflow_run, 'test-project'
        )

        # Verify git operations
        mock_add_files.assert_called_once_with(
            mock_working_dir, ['.gitignore', 'package.json']
        )
        mock_commit.assert_called_once()
        mock_push.assert_called_once_with(
            working_directory=mock_working_dir, remote='origin', branch=None
        )

        # Check commit message format
        call_args = mock_commit.call_args
        commit_message = call_args.kwargs['message']
        self.assertIn('imbi-automations: test-workflow', commit_message)
        self.assertIn('Test workflow', commit_message)  # Description

    @mock.patch('imbi_automations.git.push_changes')
    @mock.patch('imbi_automations.git.add_files')
    @mock.patch('imbi_automations.git.commit_changes')
    async def test_commit_workflow_changes_multiple_actions(
        self,
        mock_commit: mock.Mock,
        mock_add_files: mock.Mock,
        mock_push: mock.Mock,
    ) -> None:
        """Test workflow-level commit with multiple template actions."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_commit.return_value = 'ghi789'

        # Set up action results with multiple template actions
        self.workflow_engine.action_results = {
            'copy-gitignore': {
                'result': {
                    'status': 'success',
                    'copied_files': ['.gitignore'],
                    'errors': [],
                }
            },
            'copy-config': {
                'result': {
                    'status': 'success',
                    'copied_files': ['config.json', 'settings.yml'],
                    'errors': [],
                }
            },
            'other-action': {'result': 'not-a-template-action'},
        }

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._commit_workflow_changes(
            workflow_run, 'test-project'
        )

        # Verify git operations with all files
        expected_files = ['.gitignore', 'config.json', 'settings.yml']
        mock_add_files.assert_called_once_with(
            mock_working_dir, expected_files
        )
        mock_commit.assert_called_once()
        mock_push.assert_called_once_with(
            working_directory=mock_working_dir, remote='origin', branch=None
        )

        # Check commit message format
        call_args = mock_commit.call_args
        commit_message = call_args.kwargs['message']
        self.assertIn('imbi-automations: test-workflow', commit_message)
        self.assertIn('Test workflow', commit_message)  # Description

    async def test_commit_workflow_changes_no_template_files(self) -> None:
        """Test workflow-level commit with no template files to commit."""
        mock_working_dir = pathlib.Path('/mock/working/dir')

        # Set up action results with no template actions
        self.workflow_engine.action_results = {
            'callable-action': {'result': 'success'}
        }

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        # Should complete without error and without calling git operations
        with (
            mock.patch('imbi_automations.git.add_files') as mock_add_files,
            mock.patch('imbi_automations.git.commit_changes') as mock_commit,
        ):
            await self.workflow_engine._commit_workflow_changes(
                workflow_run, 'test-project'
            )

            # No git operations should be called
            mock_add_files.assert_not_called()
            mock_commit.assert_not_called()

    @mock.patch('imbi_automations.git.push_changes')
    @mock.patch('imbi_automations.git.add_files')
    @mock.patch('imbi_automations.git.commit_changes')
    async def test_execute_workflow_with_templates_and_commit(
        self,
        mock_commit: mock.Mock,
        mock_add_files: mock.Mock,
        mock_push: mock.Mock,
    ) -> None:
        """Test complete workflow execution with templates and commit."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_commit.return_value = 'workflow123'

        # Create workflow with templates action
        workflow_config = models.WorkflowConfiguration(
            name='test-templates-workflow',
            clone_repository=True,
            create_pull_request=False,
            actions=[
                models.WorkflowAction(
                    name='apply-templates',
                    type=models.WorkflowActionTypes.templates,
                    value=models.WorkflowActionValue(
                        client='unused', method='unused'
                    ),
                )
            ],
        )

        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        workflow_run = models.WorkflowRun(
            workflow=workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        # Mock the templates action to store results properly
        async def mock_templates_action(
            action: models.WorkflowAction, context: dict[str, typing.Any]
        ) -> dict[str, typing.Any]:
            result = {
                'status': 'success',
                'copied_files': ['.gitignore'],
                'errors': [],
            }
            self.workflow_engine.action_results[action.name] = {
                'result': result
            }
            context['actions'] = self.workflow_engine.action_results
            return result

        with (
            mock.patch('imbi_automations.git.clone_repository') as mock_clone,
            mock.patch.object(
                self.workflow_engine,
                '_execute_templates_action',
                side_effect=mock_templates_action,
            ),
        ):
            # Set the clone mock to return the expected working directory
            mock_clone.return_value = mock_working_dir

            await self.workflow_engine.execute(workflow_run)

            # Verify clone was called with SSH URL
            mock_clone.assert_called_once_with(
                clone_url='git@github.com:testorg/test-repo.git',
                branch='main',
                depth=1,
            )

            # Verify workflow-level git operations were called
            mock_add_files.assert_called_once_with(
                mock_working_dir, ['.gitignore']
            )
            mock_commit.assert_called_once()
            mock_push.assert_called_once_with(
                working_directory=mock_working_dir,
                remote='origin',
                branch=None,
            )

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_condition_file_exists_true(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test condition evaluation for file_exists when file exists."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = True

        condition = models.WorkflowCondition(file_exists='.gitignore')
        result = await self.workflow_engine._evaluate_condition(
            condition, mock_working_dir
        )

        self.assertTrue(result)
        mock_exists.assert_called_once()

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_condition_file_exists_false(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test file_exists condition when file doesn't exist."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = False

        condition = models.WorkflowCondition(file_exists='package.json')
        result = await self.workflow_engine._evaluate_condition(
            condition, mock_working_dir
        )

        self.assertFalse(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_condition_file_not_exists_true(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test file_not_exists condition when file doesn't exist."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = False

        condition = models.WorkflowCondition(file_not_exists='.env')
        result = await self.workflow_engine._evaluate_condition(
            condition, mock_working_dir
        )

        self.assertTrue(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_condition_file_not_exists_false(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test condition evaluation for file_not_exists when file exists."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = True

        condition = models.WorkflowCondition(file_not_exists='README.md')
        result = await self.workflow_engine._evaluate_condition(
            condition, mock_working_dir
        )

        self.assertFalse(result)

    async def test_evaluate_condition_empty(self) -> None:
        """Test condition evaluation for empty condition."""
        mock_working_dir = pathlib.Path('/mock/working/dir')

        condition = models.WorkflowCondition()
        result = await self.workflow_engine._evaluate_condition(
            condition, mock_working_dir
        )

        self.assertTrue(result)

    async def test_evaluate_conditions_no_conditions(self) -> None:
        """Test conditions evaluation when no conditions are specified."""
        workflow_run = models.WorkflowRun(
            workflow=self.workflow, imbi_project=self.imbi_project
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        self.assertTrue(result)

    async def test_evaluate_conditions_no_working_directory(self) -> None:
        """Test conditions evaluation without working directory."""
        workflow_config = models.WorkflowConfiguration(
            name='test-conditions',
            conditions=[models.WorkflowCondition(file_exists='.gitignore')],
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )
        workflow_run = models.WorkflowRun(
            workflow=workflow,
            imbi_project=self.imbi_project,
            working_directory=None,
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        # Should return True when no working directory
        self.assertTrue(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_conditions_all_type_pass(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test conditions evaluation with 'all' type - all conditions pass."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = True  # All files exist

        workflow_config = models.WorkflowConfiguration(
            name='test-all-conditions',
            condition_type=models.WorkflowConditionType.all,
            conditions=[
                models.WorkflowCondition(file_exists='.gitignore'),
                models.WorkflowCondition(file_exists='package.json'),
            ],
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )
        workflow_run = models.WorkflowRun(
            workflow=workflow,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        self.assertTrue(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_conditions_all_type_fail(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test conditions evaluation with 'all' type - one condition fails."""
        mock_working_dir = pathlib.Path('/mock/working/dir')

        # Mock different return values for different files
        def side_effect() -> bool:
            # Simplified approach - track which path is being checked
            # Make first call return True, second False
            if not hasattr(side_effect, 'call_count'):
                side_effect.call_count = 0
            side_effect.call_count += 1
            return (
                side_effect.call_count == 1
            )  # First call (gitignore) True, second call (package.json) False

        mock_exists.side_effect = side_effect

        workflow_config = models.WorkflowConfiguration(
            name='test-all-conditions-fail',
            condition_type=models.WorkflowConditionType.all,
            conditions=[
                models.WorkflowCondition(file_exists='.gitignore'),
                models.WorkflowCondition(
                    file_exists='package.json'
                ),  # This will fail
            ],
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )
        workflow_run = models.WorkflowRun(
            workflow=workflow,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        self.assertFalse(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_conditions_any_type_pass(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test 'any' type conditions - one condition passes."""
        mock_working_dir = pathlib.Path('/mock/working/dir')

        # Mock different return values for different files
        def side_effect() -> bool:
            # For any test, we want first call to fail, second to pass
            if not hasattr(side_effect, 'call_count'):
                side_effect.call_count = 0
            side_effect.call_count += 1
            return (
                side_effect.call_count == 2
            )  # First call (gitignore) False, second call (package.json) True

        mock_exists.side_effect = side_effect

        workflow_config = models.WorkflowConfiguration(
            name='test-any-conditions',
            condition_type=models.WorkflowConditionType.any,
            conditions=[
                models.WorkflowCondition(
                    file_exists='.gitignore'
                ),  # This will fail
                models.WorkflowCondition(
                    file_exists='package.json'
                ),  # This will pass
            ],
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )
        workflow_run = models.WorkflowRun(
            workflow=workflow,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        self.assertTrue(result)

    @mock.patch('pathlib.Path.exists')
    async def test_evaluate_conditions_any_type_fail(
        self, mock_exists: mock.Mock
    ) -> None:
        """Test conditions evaluation with 'any' type - all conditions fail."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_exists.return_value = False  # No files exist

        workflow_config = models.WorkflowConfiguration(
            name='test-any-conditions-fail',
            condition_type=models.WorkflowConditionType.any,
            conditions=[
                models.WorkflowCondition(file_exists='.gitignore'),
                models.WorkflowCondition(file_exists='package.json'),
            ],
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )
        workflow_run = models.WorkflowRun(
            workflow=workflow,
            imbi_project=self.imbi_project,
            working_directory=mock_working_dir,
        )

        result = await self.workflow_engine._evaluate_conditions(workflow_run)

        self.assertFalse(result)

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_execute_workflow_with_conditions_skip(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test workflow execution skipped due to conditions."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_clone.return_value = mock_working_dir

        # Create workflow with condition that will fail
        workflow_config = models.WorkflowConfiguration(
            name='test-conditions-skip',
            clone_repository=True,
            conditions=[
                models.WorkflowCondition(file_exists='nonexistent.file')
            ],
            actions=[
                models.WorkflowAction(
                    name='test-action',
                    value=models.WorkflowActionValue(
                        client='github', method='get_latest_workflow_status'
                    ),
                )
            ],
        )

        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        workflow_run = models.WorkflowRun(
            workflow=workflow,
            github_repository=self.github_repo,
            imbi_project=self.imbi_project,
        )

        with mock.patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False  # File doesn't exist

            await self.workflow_engine.execute(workflow_run)

            # Verify clone was called (conditions evaluated after cloning)
            mock_clone.assert_called_once()

            # Verify no actions were executed
            self.mock_github.get_latest_workflow_status.assert_not_called()

    async def test_execute_file_action_rename_success(self) -> None:
        """Test successful file rename action."""
        action = models.WorkflowAction(
            name='rename-file',
            type=models.WorkflowActionTypes.file,
            command='rename',
            source='compose.yml',
            destination='compose.yaml',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {
            'workflow': workflow_run.workflow,
            'workflow_run': workflow_run,
            'actions': {},
        }

        # Mock source file exists, destination doesn't exist
        with mock.patch('pathlib.Path.exists') as mock_exists:
            # Set up exists behavior: source=True, destination=False
            def exists_side_effect(path_obj: pathlib.Path) -> bool:
                if str(path_obj).endswith('compose.yml'):
                    return True
                elif str(path_obj).endswith('compose.yaml'):
                    return False
                return False

            mock_exists.side_effect = lambda: exists_side_effect(
                mock_exists.call_args[0][0] if mock_exists.call_args else None
            )

            # Mock the path objects
            source_path = mock.MagicMock()
            source_path.exists.return_value = True
            dest_path = mock.MagicMock()
            dest_path.exists.return_value = False

            with mock.patch.object(
                pathlib.Path,
                '__truediv__',
                side_effect=[source_path, dest_path],
            ):
                result = await self.workflow_engine._execute_file_action(
                    action, context
                )

                # Verify rename was called
                source_path.rename.assert_called_once_with(dest_path)

                # Verify result
                expected_result = {
                    'operation': 'rename',
                    'source': 'compose.yml',
                    'destination': 'compose.yaml',
                    'status': 'success',
                }
                self.assertEqual(result, expected_result)
                self.assertIn(
                    'rename-file', self.workflow_engine.action_results
                )

    async def test_execute_file_action_rename_missing_source(self) -> None:
        """Test file rename action with missing source file."""
        action = models.WorkflowAction(
            name='rename-file',
            type=models.WorkflowActionTypes.file,
            command='rename',
            source='nonexistent.yml',
            destination='compose.yaml',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        # Mock source file doesn't exist
        source_path = mock.MagicMock()
        source_path.exists.return_value = False

        with mock.patch.object(
            pathlib.Path, '__truediv__', return_value=source_path
        ):
            with self.assertRaises(FileNotFoundError) as cm:
                await self.workflow_engine._execute_file_action(
                    action, context
                )

            self.assertIn(
                'Source file not found: nonexistent.yml', str(cm.exception)
            )

    async def test_execute_file_action_rename_destination_exists(self) -> None:
        """Test file rename action when destination already exists."""
        action = models.WorkflowAction(
            name='rename-file',
            type=models.WorkflowActionTypes.file,
            command='rename',
            source='compose.yml',
            destination='compose.yaml',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        # Mock both source and destination exist
        source_path = mock.MagicMock()
        source_path.exists.return_value = True
        dest_path = mock.MagicMock()
        dest_path.exists.return_value = True

        with mock.patch.object(
            pathlib.Path, '__truediv__', side_effect=[source_path, dest_path]
        ):
            with self.assertRaises(FileExistsError) as cm:
                await self.workflow_engine._execute_file_action(
                    action, context
                )

            self.assertIn(
                'Destination file already exists: compose.yaml',
                str(cm.exception),
            )

    async def test_execute_file_action_remove_success(self) -> None:
        """Test successful file remove action."""
        action = models.WorkflowAction(
            name='remove-file',
            type=models.WorkflowActionTypes.file,
            command='remove',
            source='old-file.txt',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        # Mock source file exists
        source_path = mock.MagicMock()
        source_path.exists.return_value = True

        with mock.patch.object(
            pathlib.Path, '__truediv__', return_value=source_path
        ):
            result = await self.workflow_engine._execute_file_action(
                action, context
            )

            # Verify unlink was called
            source_path.unlink.assert_called_once()

            # Verify result
            expected_result = {
                'operation': 'remove',
                'source': 'old-file.txt',
                'status': 'success',
            }
            self.assertEqual(result, expected_result)

    async def test_execute_file_action_remove_missing_file(self) -> None:
        """Test file remove action with missing source file."""
        action = models.WorkflowAction(
            name='remove-file',
            type=models.WorkflowActionTypes.file,
            command='remove',
            source='nonexistent.txt',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        # Mock source file doesn't exist
        source_path = mock.MagicMock()
        source_path.exists.return_value = False

        with mock.patch.object(
            pathlib.Path, '__truediv__', return_value=source_path
        ):
            with self.assertRaises(FileNotFoundError) as cm:
                await self.workflow_engine._execute_file_action(
                    action, context
                )

            self.assertIn(
                'Source file not found: nonexistent.txt', str(cm.exception)
            )

    async def test_execute_file_action_missing_command(self) -> None:
        """Test file action with missing command."""
        action = models.WorkflowAction(
            name='bad-file-action',
            type=models.WorkflowActionTypes.file,
            source='some-file.txt',
        )

        context = {'workflow_run': mock.MagicMock()}

        with self.assertRaises(ValueError) as cm:
            await self.workflow_engine._execute_file_action(action, context)

        self.assertIn('missing required command', str(cm.exception))

    async def test_execute_file_action_missing_source(self) -> None:
        """Test file action with missing source."""
        action = models.WorkflowAction(
            name='bad-file-action',
            type=models.WorkflowActionTypes.file,
            command='rename',
        )

        context = {'workflow_run': mock.MagicMock()}

        with self.assertRaises(ValueError) as cm:
            await self.workflow_engine._execute_file_action(action, context)

        self.assertIn('missing required source', str(cm.exception))

    async def test_execute_file_action_missing_working_directory(self) -> None:
        """Test file action without working directory."""
        action = models.WorkflowAction(
            name='file-action',
            type=models.WorkflowActionTypes.file,
            command='rename',
            source='file.txt',
        )

        context = {'workflow_run': None}

        with self.assertRaises(RuntimeError) as cm:
            await self.workflow_engine._execute_file_action(action, context)

        self.assertIn('requires working directory', str(cm.exception))

    async def test_execute_file_action_unsupported_command(self) -> None:
        """Test file action with unsupported command."""
        action = models.WorkflowAction(
            name='file-action',
            type=models.WorkflowActionTypes.file,
            command='unsupported',
            source='file.txt',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        with self.assertRaises(ValueError) as cm:
            await self.workflow_engine._execute_file_action(action, context)

        self.assertIn(
            'Unsupported file command: unsupported', str(cm.exception)
        )

    async def test_execute_file_action_regex_not_implemented(self) -> None:
        """Test file action regex command is not yet implemented."""
        action = models.WorkflowAction(
            name='regex-action',
            type=models.WorkflowActionTypes.file,
            command='regex',
            source='file.txt',
            pattern='old',
            replacement='new',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        with self.assertRaises(NotImplementedError) as cm:
            await self.workflow_engine._execute_file_action(action, context)

        self.assertIn(
            'Regex file operations not yet implemented', str(cm.exception)
        )

    async def test_execute_action_file_type(self) -> None:
        """Test dispatching to file action handler."""
        action = models.WorkflowAction(
            name='test-file',
            type=models.WorkflowActionTypes.file,
            command='rename',
            source='old.txt',
            destination='new.txt',
        )

        mock_working_dir = pathlib.Path('/mock/working/dir')
        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        context = {'workflow_run': workflow_run}

        # Mock successful file operation
        source_path = mock.MagicMock()
        source_path.exists.return_value = True
        dest_path = mock.MagicMock()
        dest_path.exists.return_value = False

        with mock.patch.object(
            pathlib.Path, '__truediv__', side_effect=[source_path, dest_path]
        ):
            result = await self.workflow_engine._execute_action(
                action, context
            )

            self.assertEqual(result['operation'], 'rename')
            self.assertEqual(result['status'], 'success')

    @mock.patch('imbi_automations.git.push_changes')
    @mock.patch('imbi_automations.git.add_files')
    @mock.patch('imbi_automations.git.commit_changes')
    async def test_commit_workflow_changes_with_ci_skip_checks(
        self,
        mock_commit: mock.Mock,
        mock_add_files: mock.Mock,
        mock_push: mock.Mock,
    ) -> None:
        """Test workflow commit with ci_skip_checks enabled."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_commit.return_value = 'abc123'

        # Create workflow configuration with ci_skip_checks enabled
        workflow_config = models.WorkflowConfiguration(
            name='test-ci-skip',
            description='Test workflow with CI skip',
            ci_skip_checks=True,
        )
        workflow = models.Workflow(
            path=self.workflow_dir, configuration=workflow_config
        )

        # Set up action results with copied files
        self.workflow_engine.action_results['test-action'] = {
            'result': {
                'status': 'success',
                'copied_files': ['test.txt'],
                'errors': [],
            }
        }

        workflow_run = models.WorkflowRun(
            workflow=workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._commit_workflow_changes(
            workflow_run, 'test-project'
        )

        # Verify commit was called
        mock_commit.assert_called_once()

        # Check commit message includes skip-checks trailer
        call_args = mock_commit.call_args
        commit_message = call_args.kwargs['message']
        self.assertIn('imbi-automations: test-ci-skip', commit_message)
        self.assertIn('Test workflow with CI skip', commit_message)
        self.assertIn('[ci skip]', commit_message)

        # Verify the trailer is properly formatted (on its own line)
        lines = commit_message.split('\n')
        self.assertIn('[ci skip]', lines)

    @mock.patch('imbi_automations.git.push_changes')
    @mock.patch('imbi_automations.git.add_files')
    @mock.patch('imbi_automations.git.remove_files')
    @mock.patch('imbi_automations.git.commit_changes')
    async def test_commit_workflow_changes_with_file_operations(
        self,
        mock_commit: mock.Mock,
        mock_remove_files: mock.Mock,
        mock_add_files: mock.Mock,
        mock_push: mock.Mock,
    ) -> None:
        """Test workflow commit with file operations (rename and remove)."""
        mock_working_dir = pathlib.Path('/mock/working/dir')
        mock_commit.return_value = 'file123'

        # Set up action results with file operations
        self.workflow_engine.action_results = {
            'rename-action': {
                'result': {
                    'operation': 'rename',
                    'source': 'old.txt',
                    'destination': 'new.txt',
                    'status': 'success',
                }
            },
            'remove-action': {
                'result': {
                    'operation': 'remove',
                    'source': 'unwanted.txt',
                    'status': 'success',
                }
            },
        }

        workflow_run = models.WorkflowRun(
            workflow=self.workflow,
            working_directory=mock_working_dir,
            imbi_project=self.imbi_project,
        )

        await self.workflow_engine._commit_workflow_changes(
            workflow_run, 'test-project'
        )

        # Verify git operations for file operations
        # Should remove both the renamed source file and the removed file
        expected_remove_calls = [
            mock.call(mock_working_dir, ['old.txt']),  # From rename operation
            mock.call(
                mock_working_dir, ['unwanted.txt']
            ),  # From remove operation
        ]
        mock_remove_files.assert_has_calls(expected_remove_calls)

        # Should add the renamed destination file
        mock_add_files.assert_called_once_with(mock_working_dir, ['new.txt'])

        # Should commit the changes
        mock_commit.assert_called_once()
        mock_push.assert_called_once()


if __name__ == '__main__':
    unittest.main()
