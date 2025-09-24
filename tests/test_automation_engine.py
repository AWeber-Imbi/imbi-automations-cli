import argparse
import pathlib
import tempfile
import typing
import unittest
import unittest.mock

from imbi_automations import engine, models


class TestAutomationIterator(unittest.TestCase):
    def test_automation_iterator_enum_values(self) -> None:
        """Test that AutomationIterator enum has correct values."""
        self.assertEqual(
            engine.AutomationIterator.github_repositories.value, 1
        )
        self.assertEqual(
            engine.AutomationIterator.github_organization.value, 2
        )
        self.assertEqual(engine.AutomationIterator.github_project.value, 3)
        self.assertEqual(
            engine.AutomationIterator.gitlab_repositories.value, 4
        )
        self.assertEqual(engine.AutomationIterator.gitlab_group.value, 5)
        self.assertEqual(engine.AutomationIterator.gitlab_project.value, 6)
        self.assertEqual(engine.AutomationIterator.imbi_project_types.value, 7)
        self.assertEqual(engine.AutomationIterator.imbi_project.value, 8)
        self.assertEqual(engine.AutomationIterator.imbi_projects.value, 9)

    def test_automation_iterator_enum_names(self) -> None:
        """Test that AutomationIterator enum has correct names."""
        self.assertEqual(
            engine.AutomationIterator.github_repositories.name,
            'github_repositories',
        )
        self.assertEqual(
            engine.AutomationIterator.github_organization.name,
            'github_organization',
        )
        self.assertEqual(
            engine.AutomationIterator.github_project.name, 'github_project'
        )
        self.assertEqual(
            engine.AutomationIterator.gitlab_repositories.name,
            'gitlab_repositories',
        )
        self.assertEqual(
            engine.AutomationIterator.gitlab_group.name, 'gitlab_group'
        )
        self.assertEqual(
            engine.AutomationIterator.gitlab_project.name, 'gitlab_project'
        )
        self.assertEqual(
            engine.AutomationIterator.imbi_project_types.name,
            'imbi_project_types',
        )
        self.assertEqual(
            engine.AutomationIterator.imbi_project.name, 'imbi_project'
        )
        self.assertEqual(
            engine.AutomationIterator.imbi_projects.name, 'imbi_projects'
        )

    def test_automation_iterator_count(self) -> None:
        """Test that AutomationIterator has expected number of values."""
        self.assertEqual(len(engine.AutomationIterator), 9)


class TestAutomationEngine(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary workflow directory
        self.temp_dir = tempfile.mkdtemp()
        self.workflow_dir = pathlib.Path(self.temp_dir) / 'workflow'
        self.workflow_dir.mkdir()
        (self.workflow_dir / 'config.toml').write_text(
            '[workflow]\nname = "test"'
        )

        # Create test workflow and args
        self.workflow = models.Workflow(
            path=self.workflow_dir,
            configuration=models.WorkflowConfiguration(name='test'),
        )
        self.args = argparse.Namespace(
            config=['config.toml'], workflow=self.workflow_dir, verbose=False
        )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_automation_engine_init(self) -> None:
        """Test AutomationEngine initialization."""
        config = models.Configuration()
        iterator = engine.AutomationIterator.imbi_project

        ae = engine.AutomationEngine(
            args=self.args,
            configuration=config,
            iterator=iterator,
            workflow=self.workflow,
        )

        self.assertEqual(ae.configuration, config)
        self.assertEqual(ae.iterator, iterator)
        self.assertEqual(ae.workflow, self.workflow)

    def test_automation_engine_init_all_iterator_types(self) -> None:
        """Test AutomationEngine initialization with all iterator types."""
        config = models.Configuration()

        for iterator in engine.AutomationIterator:
            ae = engine.AutomationEngine(
                args=self.args,
                configuration=config,
                iterator=iterator,
                workflow=self.workflow,
            )
            self.assertEqual(ae.configuration, config)
            self.assertEqual(ae.iterator, iterator)

    def test_automation_engine_run_method_exists(self) -> None:
        """Test that AutomationEngine has run method."""
        config = models.Configuration()
        iterator = engine.AutomationIterator.imbi_project

        ae = engine.AutomationEngine(
            args=self.args,
            configuration=config,
            iterator=iterator,
            workflow=self.workflow,
        )

        # Test that run method exists and is callable
        self.assertTrue(hasattr(ae, 'run'))
        self.assertTrue(callable(ae.run))

    def test_automation_engine_run_method_calls_correct_processor(
        self,
    ) -> None:
        """Test that run method calls the correct processor method."""
        config = models.Configuration()

        test_cases = [
            (
                engine.AutomationIterator.github_repositories,
                '_process_github_repositories',
            ),
            (
                engine.AutomationIterator.github_organization,
                '_process_github_organization',
            ),
            (
                engine.AutomationIterator.github_project,
                '_process_github_project',
            ),
            (
                engine.AutomationIterator.gitlab_repositories,
                '_process_gitlab_repositories',
            ),
            (engine.AutomationIterator.gitlab_group, '_process_gitlab_group'),
            (
                engine.AutomationIterator.gitlab_project,
                '_process_gitlab_project',
            ),
            (
                engine.AutomationIterator.imbi_project_types,
                '_process_imbi_project_types',
            ),
            (engine.AutomationIterator.imbi_project, '_process_imbi_project'),
            (
                engine.AutomationIterator.imbi_projects,
                '_process_imbi_projects',
            ),
        ]

        for iterator_type, expected_method in test_cases:
            with self.subTest(iterator=iterator_type):
                ae = engine.AutomationEngine(
                    args=self.args,
                    configuration=config,
                    iterator=iterator_type,
                    workflow=self.workflow,
                )

                # Mock the expected method to verify it gets called
                with unittest.mock.patch.object(
                    ae, expected_method
                ) as mock_method:
                    import asyncio

                    asyncio.run(ae.run())
                    mock_method.assert_called_once()


class TestAutomationEngineImbiProjectTypes(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary workflow directory
        self.temp_dir = tempfile.mkdtemp()
        self.workflow_dir = pathlib.Path(self.temp_dir) / 'workflow'
        self.workflow_dir.mkdir()
        (self.workflow_dir / 'config.toml').write_text(
            '[workflow]\nname = "test"'
        )

        # Create test workflow and args
        self.workflow = models.Workflow(
            path=self.workflow_dir,
            configuration=models.WorkflowConfiguration(name='test'),
        )
        self.args = argparse.Namespace(
            config=['config.toml'],
            workflow=self.workflow_dir,
            verbose=False,
            project_type='frontend-applications',
        )

        # Mock configuration with Imbi client
        self.config = models.Configuration(
            imbi=models.ImbiConfiguration(
                api_key='test-key', hostname='imbi.example.com'
            )
        )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @unittest.mock.patch('imbi_automations.imbi.Imbi')
    def test_process_imbi_project_types_success(
        self, mock_imbi_class: typing.Any
    ) -> None:
        """Test successful processing of projects by type."""
        # Create mock projects
        mock_projects = [
            models.ImbiProject(
                id=1,
                name='Frontend App 1',
                description='Test frontend app',
                namespace='frontend',
                namespace_slug='frontend',
                project_type='Frontend Application',
                project_type_slug='frontend-applications',
                slug='frontend-app-1',
                imbi_url='https://imbi.example.com/ui/projects/1',
                dependencies=None,
                environments=None,
                facts=None,
                identifiers=None,
                links=None,
                project_score=None,
                urls=None,
            ),
            models.ImbiProject(
                id=2,
                name='Frontend App 2',
                description='Another frontend app',
                namespace='frontend',
                namespace_slug='frontend',
                project_type='Frontend Application',
                project_type_slug='frontend-applications',
                slug='frontend-app-2',
                imbi_url='https://imbi.example.com/ui/projects/2',
                dependencies=None,
                environments=None,
                facts=None,
                identifiers=None,
                links=None,
                project_score=None,
                urls=None,
            ),
        ]

        # Setup mock Imbi client
        mock_imbi_instance = unittest.mock.AsyncMock()
        mock_imbi_instance.get_projects_by_type.return_value = mock_projects
        mock_imbi_class.return_value = mock_imbi_instance

        # Create automation engine
        ae = engine.AutomationEngine(
            args=self.args,
            configuration=self.config,
            iterator=engine.AutomationIterator.imbi_project_types,
            workflow=self.workflow,
        )

        # Mock _execute_workflow_run to track calls
        ae._execute_workflow_run = unittest.mock.AsyncMock()

        # Run the test
        import asyncio

        asyncio.run(ae._process_imbi_project_types())

        # Verify the Imbi client was called correctly
        mock_imbi_instance.get_projects_by_type.assert_called_once_with(
            'frontend-applications'
        )

        # Verify _execute_workflow_run was called for each project
        self.assertEqual(ae._execute_workflow_run.call_count, 2)
        ae._execute_workflow_run.assert_any_call(imbi_project=mock_projects[0])
        ae._execute_workflow_run.assert_any_call(imbi_project=mock_projects[1])

    def test_process_imbi_project_types_no_imbi_client(self) -> None:
        """Test error when no Imbi client is configured."""
        # Create automation engine without Imbi configuration
        config_no_imbi = models.Configuration()
        ae = engine.AutomationEngine(
            args=self.args,
            configuration=config_no_imbi,
            iterator=engine.AutomationIterator.imbi_project_types,
            workflow=self.workflow,
        )

        # Should raise RuntimeError when trying to process
        import asyncio

        with self.assertRaises(RuntimeError) as context:
            asyncio.run(ae._process_imbi_project_types())

        self.assertIn('Imbi client is required', str(context.exception))

    @unittest.mock.patch('imbi_automations.imbi.Imbi')
    def test_process_imbi_project_types_empty_results(
        self, mock_imbi_class: typing.Any
    ) -> None:
        """Test processing when no projects match the type."""
        # Setup mock Imbi client with empty results
        mock_imbi_instance = unittest.mock.AsyncMock()
        mock_imbi_instance.get_projects_by_type.return_value = []
        mock_imbi_class.return_value = mock_imbi_instance

        # Create automation engine
        ae = engine.AutomationEngine(
            args=self.args,
            configuration=self.config,
            iterator=engine.AutomationIterator.imbi_project_types,
            workflow=self.workflow,
        )

        # Mock _execute_workflow_run to track calls
        ae._execute_workflow_run = unittest.mock.AsyncMock()

        # Run the test
        import asyncio

        asyncio.run(ae._process_imbi_project_types())

        # Verify the Imbi client was called correctly
        mock_imbi_instance.get_projects_by_type.assert_called_once_with(
            'frontend-applications'
        )

        # Verify _execute_workflow_run was not called
        ae._execute_workflow_run.assert_not_called()

    @unittest.mock.patch('imbi_automations.imbi.Imbi')
    def test_process_imbi_project_types_api_error(
        self, mock_imbi_class: typing.Any
    ) -> None:
        """Test handling of API errors when fetching projects by type."""
        # Setup mock Imbi client to raise an exception
        mock_imbi_instance = unittest.mock.AsyncMock()
        mock_imbi_instance.get_projects_by_type.side_effect = Exception(
            'API Error'
        )
        mock_imbi_class.return_value = mock_imbi_instance

        # Create automation engine
        ae = engine.AutomationEngine(
            args=self.args,
            configuration=self.config,
            iterator=engine.AutomationIterator.imbi_project_types,
            workflow=self.workflow,
        )

        # Should propagate the exception
        import asyncio

        with self.assertRaises(Exception) as context:
            asyncio.run(ae._process_imbi_project_types())

        self.assertIn('API Error', str(context.exception))

        # Verify the Imbi client was called
        mock_imbi_instance.get_projects_by_type.assert_called_once_with(
            'frontend-applications'
        )


class TestAutomationEngineFiltering(unittest.TestCase):
    def test_filter_projects_from_start_found(self) -> None:
        """Test filtering projects when start project is found."""
        # Create mock projects
        project1 = unittest.mock.Mock()
        project1.slug = 'project-a'
        project1.id = 1
        project1.name = 'Project A'

        project2 = unittest.mock.Mock()
        project2.slug = 'project-b'
        project2.id = 2
        project2.name = 'Project B'

        project3 = unittest.mock.Mock()
        project3.slug = 'project-c'
        project3.id = 3
        project3.name = 'Project C'

        projects = [project1, project2, project3]

        # Create minimal engine instance
        args = argparse.Namespace(start_from_project='project-a')
        config = models.Configuration()
        workflow = models.Workflow(
            path=pathlib.Path(tempfile.mkdtemp()),
            configuration=models.WorkflowConfiguration(
                name='test', description='test'
            ),
        )
        ae = engine.AutomationEngine(
            args, config, engine.AutomationIterator.imbi_projects, workflow
        )

        # Test filtering
        result = ae._filter_projects_from_start(projects, 'project-a')

        # Should return projects after 'project-a' (project-b and project-c)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].slug, 'project-b')
        self.assertEqual(result[1].slug, 'project-c')

    def test_filter_projects_from_start_not_found(self) -> None:
        """Test filtering projects when start project is not found."""
        # Create mock projects
        project1 = unittest.mock.Mock()
        project1.slug = 'project-a'
        project1.id = 1

        project2 = unittest.mock.Mock()
        project2.slug = 'project-b'
        project2.id = 2

        projects = [project1, project2]

        # Create minimal engine instance
        args = argparse.Namespace(start_from_project='nonexistent')
        config = models.Configuration()
        workflow = models.Workflow(
            path=pathlib.Path(tempfile.mkdtemp()),
            configuration=models.WorkflowConfiguration(
                name='test', description='test'
            ),
        )
        ae = engine.AutomationEngine(
            args, config, engine.AutomationIterator.imbi_projects, workflow
        )

        # Test filtering with non-existent project
        result = ae._filter_projects_from_start(projects, 'nonexistent')

        # Should return all projects since start project wasn't found
        self.assertEqual(len(result), 2)
        self.assertEqual(result, projects)

    def test_filter_projects_from_start_empty_list(self) -> None:
        """Test filtering projects with empty project list."""
        # Create minimal engine instance
        args = argparse.Namespace(start_from_project='project-a')
        config = models.Configuration()
        workflow = models.Workflow(
            path=pathlib.Path(tempfile.mkdtemp()),
            configuration=models.WorkflowConfiguration(
                name='test', description='test'
            ),
        )
        ae = engine.AutomationEngine(
            args, config, engine.AutomationIterator.imbi_projects, workflow
        )

        # Test filtering with empty list
        result = ae._filter_projects_from_start([], 'project-a')

        # Should return empty list
        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
