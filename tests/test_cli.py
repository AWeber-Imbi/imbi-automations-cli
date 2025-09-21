import argparse
import logging
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from imbi_automations import cli, engine, models


class TestWorkflowFunction(unittest.TestCase):
    def test_workflow_valid_directory(self) -> None:
        """Test workflow function with valid directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a workflow directory with config.toml
            workflow_dir = Path(tmp_dir) / 'test-workflow'
            workflow_dir.mkdir()
            (workflow_dir / 'config.toml').write_text('[workflow]\nname = "test"')

            result = cli.workflow(str(workflow_dir))
            self.assertEqual(result, workflow_dir)
            self.assertTrue(result.is_dir())

    def test_workflow_nonexistent_directory(self) -> None:
        """Test workflow function with non-existent directory."""
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            cli.workflow('/nonexistent/path')

        self.assertIn('Invalid workflow path', str(cm.exception))

    def test_workflow_missing_config_toml(self) -> None:
        """Test workflow function with directory missing config.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(argparse.ArgumentTypeError) as cm:
                cli.workflow(tmp_dir)

            self.assertIn('Invalid workflow path', str(cm.exception))

    def test_workflow_file_instead_of_directory(self) -> None:
        """Test workflow function with file instead of directory."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            with self.assertRaises(argparse.ArgumentTypeError) as cm:
                cli.workflow(tmp_file.name)

            self.assertIn('Invalid workflow path', str(cm.exception))


class TestParseArgs(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary config file and workflow directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / 'config.toml'
        self.config_file.write_text('[imbi]\nhostname = "test.com"')

        self.workflow_dir = Path(self.temp_dir) / 'workflow'
        self.workflow_dir.mkdir()
        (self.workflow_dir / 'config.toml').write_text('[workflow]\nname = "test"')

    def tearDown(self) -> None:
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_parse_args_imbi_project_id(self) -> None:
        """Test parsing args with Imbi project ID target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--imbi-project-id', '123'
        ])

        self.assertEqual(len(args.config), 1)
        self.assertEqual(args.config[0].name, str(self.config_file))
        self.assertEqual(args.workflow, self.workflow_dir)
        self.assertEqual(args.imbi_project_id, 123)
        self.assertFalse(args.verbose)

    def test_parse_args_imbi_project_type(self) -> None:
        """Test parsing args with Imbi project type target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--imbi-project-type', 'api'
        ])

        self.assertEqual(args.imbi_project_type, 'api')

    def test_parse_args_all_imbi_projects(self) -> None:
        """Test parsing args with all Imbi projects target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--all-imbi-projects'
        ])

        self.assertTrue(args.all_imbi_projects)

    def test_parse_args_github_repository(self) -> None:
        """Test parsing args with GitHub repository target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--github-repository', 'https://github.com/org/repo'
        ])

        self.assertEqual(args.github_repository, 'https://github.com/org/repo')

    def test_parse_args_github_organization(self) -> None:
        """Test parsing args with GitHub organization target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--github-organization', 'myorg'
        ])

        self.assertEqual(args.github_organization, 'myorg')

    def test_parse_args_all_github_repositories(self) -> None:
        """Test parsing args with all GitHub repositories target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--all-github-repositories'
        ])

        self.assertTrue(args.all_github_repositories)

    def test_parse_args_gitlab_repository(self) -> None:
        """Test parsing args with GitLab repository target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--gitlab-repository', 'https://gitlab.com/org/repo'
        ])

        self.assertEqual(args.gitlab_repository, 'https://gitlab.com/org/repo')

    def test_parse_args_gitlab_organization(self) -> None:
        """Test parsing args with GitLab organization target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--gitlab-organization', 'myorg'
        ])

        self.assertEqual(args.gitlab_organization, 'myorg')

    def test_parse_args_all_gitlab_repositories(self) -> None:
        """Test parsing args with all GitLab repositories target."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--all-gitlab-repositories'
        ])

        self.assertTrue(args.all_gitlab_repositories)

    def test_parse_args_verbose(self) -> None:
        """Test parsing args with verbose flag."""
        args = cli.parse_args([
            str(self.config_file), str(self.workflow_dir),
            '--imbi-project-id', '123', '--verbose'
        ])

        self.assertTrue(args.verbose)

    def test_parse_args_no_target_required(self) -> None:
        """Test that target argument is required."""
        with self.assertRaises(SystemExit):
            cli.parse_args([str(self.config_file), str(self.workflow_dir)])

    def test_parse_args_mutually_exclusive(self) -> None:
        """Test that target arguments are mutually exclusive."""
        with self.assertRaises(SystemExit):
            cli.parse_args([
                str(self.config_file), str(self.workflow_dir),
                '--imbi-project-id', '123',
                '--github-repository', 'https://github.com/org/repo'
            ])

    def test_parse_args_invalid_config_file(self) -> None:
        """Test parsing args with non-existent config file."""
        with self.assertRaises(SystemExit):
            cli.parse_args([
                '/nonexistent/config.toml', str(self.workflow_dir),
                '--imbi-project-id', '123'
            ])

    def test_parse_args_invalid_workflow_dir(self) -> None:
        """Test parsing args with invalid workflow directory."""
        with self.assertRaises(SystemExit):
            cli.parse_args([
                str(self.config_file), '/nonexistent/workflow',
                '--imbi-project-id', '123'
            ])


class TestLoadConfiguration(unittest.TestCase):
    def test_load_configuration_success(self) -> None:
        """Test successful configuration loading."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write('[imbi]\nhostname = "test.com"\napi_key = "test-key"')
            f.flush()

            try:
                with open(f.name, 'r') as config_file:
                    config = cli.load_configuration(config_file)

                self.assertIsInstance(config, models.Configuration)
                self.assertIsNotNone(config.imbi)
                self.assertEqual(config.imbi.hostname, 'test.com')
            finally:
                import os
                os.unlink(f.name)

    def test_load_configuration_invalid_toml(self) -> None:
        """Test configuration loading with invalid TOML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml') as f:
            f.write('invalid toml content [')
            f.flush()

            with open(f.name, 'r') as config_file:
                with self.assertRaises(Exception):  # TOMLDecodeError
                    cli.load_configuration(config_file)

    def test_load_configuration_invalid_model(self) -> None:
        """Test configuration loading with invalid model data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml') as f:
            f.write('[imbi]\n# missing required fields')
            f.flush()

            with open(f.name, 'r') as config_file:
                with self.assertRaises(Exception):  # ValidationError
                    cli.load_configuration(config_file)


class TestConfigureLogging(unittest.TestCase):
    def setUp(self) -> None:
        # Clear any existing handlers to avoid interference
        logging.getLogger().handlers.clear()
        logging.getLogger('imbi_automations.cli').handlers.clear()

    def test_configure_logging_debug(self) -> None:
        """Test logging configuration with debug enabled."""
        cli.configure_logging(True)

        # Check that root logger level is set to DEBUG
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

        # Check that HTTP library loggers are set to WARNING
        for logger_name in ('anthropic', 'httpcore', 'httpx'):
            logger = logging.getLogger(logger_name)
            self.assertEqual(logger.level, logging.WARNING)

    def test_configure_logging_info(self) -> None:
        """Test logging configuration with debug disabled."""
        cli.configure_logging(False)

        # Check that root logger level is set to INFO
        self.assertEqual(logging.getLogger().level, logging.INFO)


class TestDetermineIteratorType(unittest.TestCase):
    def test_determine_iterator_type_imbi_project_id(self) -> None:
        """Test iterator type for Imbi project ID."""
        args = argparse.Namespace(
            imbi_project_id=123,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.imbi_project)

    def test_determine_iterator_type_imbi_project_type(self) -> None:
        """Test iterator type for Imbi project type."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type='api',
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.imbi_project_types)

    def test_determine_iterator_type_all_imbi_projects(self) -> None:
        """Test iterator type for all Imbi projects."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=True,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.imbi_projects)

    def test_determine_iterator_type_github_repository(self) -> None:
        """Test iterator type for GitHub repository."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository='https://github.com/org/repo',
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.github_project)

    def test_determine_iterator_type_github_organization(self) -> None:
        """Test iterator type for GitHub organization."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization='myorg',
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.github_organization)

    def test_determine_iterator_type_all_github_repositories(self) -> None:
        """Test iterator type for all GitHub repositories."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=True,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.github_repositories)

    def test_determine_iterator_type_gitlab_repository(self) -> None:
        """Test iterator type for GitLab repository."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository='https://gitlab.com/org/repo',
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.gitlab_project)

    def test_determine_iterator_type_gitlab_organization(self) -> None:
        """Test iterator type for GitLab organization."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization='myorg',
            all_gitlab_repositories=False
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.gitlab_organization)

    def test_determine_iterator_type_all_gitlab_repositories(self) -> None:
        """Test iterator type for all GitLab repositories."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=True
        )

        result = cli.determine_iterator_type(args)
        self.assertEqual(result, engine.AutomationIterator.gitlab_repositories)

    def test_determine_iterator_type_no_valid_target(self) -> None:
        """Test that ValueError is raised when no valid target is provided."""
        args = argparse.Namespace(
            imbi_project_id=None,
            imbi_project_type=None,
            all_imbi_projects=False,
            github_repository=None,
            github_organization=None,
            all_github_repositories=False,
            gitlab_repository=None,
            gitlab_organization=None,
            all_gitlab_repositories=False
        )

        with self.assertRaises(ValueError) as cm:
            cli.determine_iterator_type(args)

        self.assertEqual(str(cm.exception), 'No valid target argument provided')


class TestMain(unittest.TestCase):
    def setUp(self) -> None:
        # Clear any existing handlers to avoid interference
        logging.getLogger().handlers.clear()
        logging.getLogger('imbi_automations.cli').handlers.clear()

    @mock.patch('imbi_automations.cli.parse_args')
    @mock.patch('imbi_automations.cli.configure_logging')
    @mock.patch('imbi_automations.cli.load_configuration')
    @mock.patch('imbi_automations.cli.determine_iterator_type')
    @mock.patch('imbi_automations.engine.AutomationEngine')
    def test_main_success(
        self,
        mock_automation_engine: mock.Mock,
        mock_determine_iterator_type: mock.Mock,
        mock_load_configuration: mock.Mock,
        mock_configure_logging: mock.Mock,
        mock_parse_args: mock.Mock
    ) -> None:
        """Test successful execution of main function."""
        # Setup mocks
        mock_args = mock.Mock()
        mock_args.verbose = True
        mock_config_file = mock.Mock()
        mock_config_file.close = mock.Mock()
        mock_args.config = [mock_config_file]
        mock_parse_args.return_value = mock_args

        mock_config = models.Configuration()
        mock_load_configuration.return_value = mock_config

        mock_iterator_type = engine.AutomationIterator.imbi_project
        mock_determine_iterator_type.return_value = mock_iterator_type

        mock_engine_instance = mock.Mock()
        mock_automation_engine.return_value = mock_engine_instance

        # Run main
        cli.main()

        # Verify calls
        mock_parse_args.assert_called_once()
        mock_configure_logging.assert_called_once_with(True)
        mock_load_configuration.assert_called_once_with(mock_config_file)
        mock_config_file.close.assert_called_once()
        mock_determine_iterator_type.assert_called_once_with(mock_args)
        mock_automation_engine.assert_called_once_with(mock_config, mock_iterator_type)
        mock_engine_instance.run.assert_called_once()

    @mock.patch('imbi_automations.cli.parse_args')
    @mock.patch('imbi_automations.cli.configure_logging')
    @mock.patch('imbi_automations.cli.load_configuration')
    @mock.patch('imbi_automations.cli.determine_iterator_type')
    @mock.patch('imbi_automations.engine.AutomationEngine')
    def test_main_keyboard_interrupt(
        self,
        mock_automation_engine: mock.Mock,
        mock_determine_iterator_type: mock.Mock,
        mock_load_configuration: mock.Mock,
        mock_configure_logging: mock.Mock,
        mock_parse_args: mock.Mock
    ) -> None:
        """Test main function handles KeyboardInterrupt gracefully."""
        # Setup mocks
        mock_args = mock.Mock()
        mock_args.verbose = False
        mock_config_file = mock.Mock()
        mock_config_file.close = mock.Mock()
        mock_args.config = [mock_config_file]
        mock_parse_args.return_value = mock_args

        mock_config = models.Configuration()
        mock_load_configuration.return_value = mock_config

        mock_iterator_type = engine.AutomationIterator.imbi_project
        mock_determine_iterator_type.return_value = mock_iterator_type

        mock_engine_instance = mock.Mock()
        mock_engine_instance.run.side_effect = KeyboardInterrupt()
        mock_automation_engine.return_value = mock_engine_instance

        # Run main - should not raise exception
        cli.main()

        # Verify calls
        mock_parse_args.assert_called_once()
        mock_configure_logging.assert_called_once_with(False)
        mock_load_configuration.assert_called_once_with(mock_config_file)
        mock_config_file.close.assert_called_once()
        mock_determine_iterator_type.assert_called_once_with(mock_args)
        mock_automation_engine.assert_called_once_with(mock_config, mock_iterator_type)
        mock_engine_instance.run.assert_called_once()

    @mock.patch('imbi_automations.cli.parse_args')
    @mock.patch('imbi_automations.cli.configure_logging')
    @mock.patch('imbi_automations.cli.load_configuration')
    @mock.patch('imbi_automations.cli.determine_iterator_type')
    @mock.patch('imbi_automations.engine.AutomationEngine')
    def test_main_engine_exception_propagates(
        self,
        mock_automation_engine: mock.Mock,
        mock_determine_iterator_type: mock.Mock,
        mock_load_configuration: mock.Mock,
        mock_configure_logging: mock.Mock,
        mock_parse_args: mock.Mock
    ) -> None:
        """Test that non-KeyboardInterrupt exceptions from engine are propagated."""
        # Setup mocks
        mock_args = mock.Mock()
        mock_args.verbose = False
        mock_config_file = mock.Mock()
        mock_config_file.close = mock.Mock()
        mock_args.config = [mock_config_file]
        mock_parse_args.return_value = mock_args

        mock_config = models.Configuration()
        mock_load_configuration.return_value = mock_config

        mock_iterator_type = engine.AutomationIterator.imbi_project
        mock_determine_iterator_type.return_value = mock_iterator_type

        mock_engine_instance = mock.Mock()
        mock_engine_instance.run.side_effect = RuntimeError('Engine error')
        mock_automation_engine.return_value = mock_engine_instance

        # Run main - should raise RuntimeError
        with self.assertRaises(RuntimeError) as cm:
            cli.main()

        self.assertEqual(str(cm.exception), 'Engine error')

        # Verify calls
        mock_parse_args.assert_called_once()
        mock_configure_logging.assert_called_once_with(False)
        mock_load_configuration.assert_called_once_with(mock_config_file)
        mock_config_file.close.assert_called_once()
        mock_determine_iterator_type.assert_called_once_with(mock_args)
        mock_automation_engine.assert_called_once_with(mock_config, mock_iterator_type)
        mock_engine_instance.run.assert_called_once()


if __name__ == '__main__':
    unittest.main()