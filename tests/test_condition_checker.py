"""Comprehensive tests for the condition_checker module."""

import pathlib
import re
import tempfile
import unittest
from unittest import mock

from imbi_automations import condition_checker, models
from tests import base


class ConditionCheckerTestCase(base.AsyncTestCase):
    """Test cases for ConditionChecker functionality."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)
        self.repository_dir = self.working_directory / 'repository'
        self.repository_dir.mkdir()

        # Create test files
        (self.repository_dir / 'package.json').write_text(
            '{"name": "test-project", "version": "1.0.0"}'
        )
        (self.repository_dir / 'requirements.txt').write_text(
            'fastapi==0.68.0\nuvicorn==0.15.0'
        )
        (self.repository_dir / 'src').mkdir()
        (self.repository_dir / 'src' / 'main.py').write_text('print("hello")')
        (self.repository_dir / 'tests').mkdir()
        (self.repository_dir / 'tests' / 'test_main.py').write_text(
            'def test(): pass'
        )

        # Create configuration and checker
        self.config = models.Configuration(
            imbi=models.ImbiConfiguration(
                api_key='test-key', hostname='imbi.test.com'
            ),
            github=models.GitHubConfiguration(
                api_key='test-github-key', hostname='github.com'
            ),
        )
        self.checker = condition_checker.ConditionChecker(
            self.config, verbose=True
        )

        # Create workflow context
        self.workflow = models.Workflow(
            path=pathlib.Path('/workflows/test'),
            configuration=models.WorkflowConfiguration(
                name='test-workflow', actions=[]
            ),
        )

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

    def tearDown(self) -> None:
        super().tearDown()
        self.temp_dir.cleanup()

    def test_check_no_conditions(self) -> None:
        """Test check method with no conditions."""
        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, []
        )
        self.assertTrue(result)

    def test_check_file_exists_success(self) -> None:
        """Test file_exists condition with existing file."""
        condition = models.WorkflowCondition(file_exists='package.json')

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    def test_check_file_exists_failure(self) -> None:
        """Test file_exists condition with non-existent file."""
        condition = models.WorkflowCondition(file_exists='nonexistent.txt')

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    def test_check_file_not_exists_success(self) -> None:
        """Test file_not_exists condition with non-existent file."""
        condition = models.WorkflowCondition(file_not_exists='nonexistent.txt')

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    def test_check_file_not_exists_failure(self) -> None:
        """Test file_not_exists condition with existing file."""
        condition = models.WorkflowCondition(file_not_exists='package.json')

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    def test_check_file_contains_success(self) -> None:
        """Test file_contains condition with matching content."""
        condition = models.WorkflowCondition(
            file_contains='test-project', file=pathlib.Path('package.json')
        )

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    def test_check_file_contains_failure(self) -> None:
        """Test file_contains condition with non-matching content."""
        condition = models.WorkflowCondition(
            file_contains='nonexistent-content',
            file=pathlib.Path('package.json'),
        )

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    def test_check_file_contains_missing_file(self) -> None:
        """Test file_contains condition with missing file."""
        condition = models.WorkflowCondition(
            file_contains='test', file=pathlib.Path('missing.txt')
        )

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    def test_check_regex_pattern_exists_success(self) -> None:
        """Test file_exists with regex pattern that matches."""
        pattern = re.compile(r'.*\.py$')
        condition = models.WorkflowCondition(file_exists=pattern)

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(
            result
        )  # Should find src/main.py or tests/test_main.py

    def test_check_regex_pattern_exists_failure(self) -> None:
        """Test file_exists with regex pattern that doesn't match."""
        pattern = re.compile(r'.*\.go$')
        condition = models.WorkflowCondition(file_exists=pattern)

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)  # No .go files

    def test_check_regex_pattern_not_exists_success(self) -> None:
        """Test file_not_exists with regex pattern that doesn't match."""
        pattern = re.compile(r'.*\.go$')
        condition = models.WorkflowCondition(file_not_exists=pattern)

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)  # No .go files, so condition passes

    def test_check_regex_pattern_not_exists_failure(self) -> None:
        """Test file_not_exists with regex pattern that matches."""
        pattern = re.compile(r'.*\.py$')
        condition = models.WorkflowCondition(file_not_exists=pattern)

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)  # .py files exist, so condition fails

    def test_check_condition_type_any_success(self) -> None:
        """Test condition_type 'any' with mixed conditions."""
        conditions = [
            models.WorkflowCondition(file_exists='nonexistent.txt'),  # False
            models.WorkflowCondition(file_exists='package.json'),  # True
        ]

        result = self.checker.check(
            self.context, models.WorkflowConditionType.any, conditions
        )

        self.assertTrue(result)  # One condition passes, any() returns True

    def test_check_condition_type_any_failure(self) -> None:
        """Test condition_type 'any' with all failing conditions."""
        conditions = [
            models.WorkflowCondition(file_exists='nonexistent1.txt'),  # False
            models.WorkflowCondition(file_exists='nonexistent2.txt'),  # False
        ]

        result = self.checker.check(
            self.context, models.WorkflowConditionType.any, conditions
        )

        self.assertFalse(result)  # All conditions fail, any() returns False

    def test_check_condition_type_all_success(self) -> None:
        """Test condition_type 'all' with all passing conditions."""
        conditions = [
            models.WorkflowCondition(file_exists='package.json'),  # True
            models.WorkflowCondition(file_exists='requirements.txt'),  # True
        ]

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, conditions
        )

        self.assertTrue(result)  # All conditions pass, all() returns True

    def test_check_condition_type_all_failure(self) -> None:
        """Test condition_type 'all' with mixed conditions."""
        conditions = [
            models.WorkflowCondition(file_exists='package.json'),  # True
            models.WorkflowCondition(file_exists='nonexistent.txt'),  # False
        ]

        result = self.checker.check(
            self.context, models.WorkflowConditionType.all, conditions
        )

        self.assertFalse(result)  # One condition fails, all() returns False

    def test_check_file_pattern_exists_string_success(self) -> None:
        """Test _check_file_pattern_exists with string path."""
        result = condition_checker.ConditionChecker._check_file_pattern_exists(
            self.repository_dir, 'package.json'
        )
        self.assertTrue(result)

    def test_check_file_pattern_exists_string_failure(self) -> None:
        """Test _check_file_pattern_exists with non-existent string path."""
        result = condition_checker.ConditionChecker._check_file_pattern_exists(
            self.repository_dir, 'nonexistent.txt'
        )
        self.assertFalse(result)

    def test_check_file_pattern_exists_regex_success(self) -> None:
        """Test _check_file_pattern_exists with matching regex pattern."""
        pattern = re.compile(r'.*\.json$')
        result = condition_checker.ConditionChecker._check_file_pattern_exists(
            self.repository_dir, pattern
        )
        self.assertTrue(result)  # Should find package.json

    def test_check_file_pattern_exists_regex_failure(self) -> None:
        """Test _check_file_pattern_exists with non-matching regex pattern."""
        pattern = re.compile(r'.*\.go$')
        result = condition_checker.ConditionChecker._check_file_pattern_exists(
            self.repository_dir, pattern
        )
        self.assertFalse(result)  # No .go files

    def test_check_file_pattern_exists_invalid_regex(self) -> None:
        """Test _check_file_pattern_exists with invalid regex pattern."""
        # Test that invalid regex patterns can be created and cause errors
        with self.assertRaises(re.error):
            re.compile(r'[')  # Invalid regex - unmatched bracket

        # The current implementation handles string patterns as exact paths,
        # so test with an invalid regex pattern object
        try:
            # '[' is treated as a file path, not regex
            result = (
                condition_checker.ConditionChecker._check_file_pattern_exists(
                    self.repository_dir, r'['
                )
            )
            self.assertFalse(result)  # File named '[' doesn't exist
        except RuntimeError:
            # If it does raise an exception, that's also acceptable behavior
            pass

    @mock.patch('imbi_automations.clients.GitHub.get_instance')
    async def test_check_remote_no_conditions(
        self, mock_github: mock.MagicMock
    ) -> None:
        """Test check_remote method with no conditions."""
        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, []
        )
        self.assertTrue(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_exists_success(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_exists condition with existing file."""
        mock_get_file.return_value = 'file content'

        condition = models.WorkflowCondition(remote_file_exists='package.json')

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_exists_failure(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_exists condition with non-existent file."""
        mock_get_file.return_value = None

        condition = models.WorkflowCondition(
            remote_file_exists='nonexistent.txt'
        )

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_not_exists_success(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_not_exists condition with non-existent file."""
        mock_get_file.return_value = None

        condition = models.WorkflowCondition(
            remote_file_not_exists='nonexistent.txt'
        )

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_not_exists_failure(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_not_exists condition with existing file."""
        mock_get_file.return_value = 'file content'

        condition = models.WorkflowCondition(
            remote_file_not_exists='package.json'
        )

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_contains_success(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_contains condition with matching content."""
        mock_get_file.return_value = '{"name": "test-project"}'

        condition = models.WorkflowCondition(
            remote_file_contains='test-project',
            remote_file=pathlib.Path('package.json'),
        )

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertTrue(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_file_contains_failure(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote_file_contains condition with non-matching content."""
        mock_get_file.return_value = '{"name": "other-project"}'

        condition = models.WorkflowCondition(
            remote_file_contains='test-project',
            remote_file=pathlib.Path('package.json'),
        )

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.all, [condition]
        )

        self.assertFalse(result)

    @mock.patch('imbi_automations.clients.GitHub.get_file_contents')
    async def test_check_remote_condition_type_any(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test remote conditions with 'any' condition type."""
        mock_get_file.side_effect = [
            None,
            'file content',
        ]  # First call: None, Second call: content

        conditions = [
            models.WorkflowCondition(
                remote_file_exists='nonexistent.txt'
            ),  # False
            models.WorkflowCondition(
                remote_file_exists='existing.txt'
            ),  # True
        ]

        result = await self.checker.check_remote(
            self.context, models.WorkflowConditionType.any, conditions
        )

        self.assertTrue(result)  # One condition passes

    async def test_check_remote_client_github_missing(self) -> None:
        """Test _check_remote_client with missing GitHub configuration."""
        # Create checker without GitHub config
        config_no_github = models.Configuration(
            imbi=models.ImbiConfiguration(
                api_key='test-key', hostname='imbi.test.com'
            )
        )
        checker_no_github = condition_checker.ConditionChecker(
            config_no_github, verbose=True
        )

        condition = models.WorkflowCondition(
            remote_file_exists='test.txt',
            remote_client=models.WorkflowConditionRemoteClient.github,
        )

        with self.assertRaises(RuntimeError) as exc_context:
            await checker_no_github._check_remote_client(condition)

        self.assertIn('GitHub is not configured', str(exc_context.exception))

    async def test_check_remote_client_gitlab_missing(self) -> None:
        """Test _check_remote_client with missing GitLab configuration."""
        condition = models.WorkflowCondition(
            remote_file_exists='test.txt',
            remote_client=models.WorkflowConditionRemoteClient.gitlab,
        )

        with self.assertRaises(RuntimeError) as exc_context:
            await self.checker._check_remote_client(condition)

        self.assertIn('GitLab is not configured', str(exc_context.exception))

    def test_check_file_contains_helper_success(self) -> None:
        """Test _check_file_contains helper method."""
        condition = models.WorkflowCondition(
            file_contains='test-project', file=pathlib.Path('package.json')
        )

        result = self.checker._check_file_contains(
            self.repository_dir, condition
        )

        self.assertTrue(result)

    def test_check_file_contains_helper_failure(self) -> None:
        """Test _check_file_contains helper with non-matching content."""
        condition = models.WorkflowCondition(
            file_contains='nonexistent', file=pathlib.Path('package.json')
        )

        result = self.checker._check_file_contains(
            self.repository_dir, condition
        )

        self.assertFalse(result)

    def test_check_file_contains_helper_missing_file(self) -> None:
        """Test _check_file_contains helper method with missing file."""
        condition = models.WorkflowCondition(
            file_contains='test', file=pathlib.Path('missing.txt')
        )

        result = self.checker._check_file_contains(
            self.repository_dir, condition
        )

        self.assertFalse(result)

    def test_check_file_contains_helper_read_error(self) -> None:
        """Test _check_file_contains helper method with file read error."""
        # Create a directory instead of file to cause read error
        (self.repository_dir / 'directory_not_file').mkdir()

        condition = models.WorkflowCondition(
            file_contains='test', file=pathlib.Path('directory_not_file')
        )

        result = self.checker._check_file_contains(
            self.repository_dir, condition
        )

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
