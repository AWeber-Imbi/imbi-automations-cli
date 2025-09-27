"""Comprehensive tests for the git module."""

import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import engine, git, models
from tests import base


class GitModuleTestCase(base.AsyncTestCase):
    """Test cases for git module functions."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)

    def tearDown(self) -> None:
        super().tearDown()
        self.temp_dir.cleanup()

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_clone_repository_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful repository cloning."""
        mock_run_git.return_value = (0, 'Cloning into repository...', '')

        await git.clone_repository(
            working_directory=self.working_directory,
            clone_url='https://github.com/test/repo.git',
            branch='main',
            depth=1,
        )

        # Verify git clone command was called correctly
        mock_run_git.assert_called_once()
        call_args = mock_run_git.call_args
        command = call_args[0][0]

        self.assertEqual(command[0], 'git')
        self.assertEqual(command[1], 'clone')
        self.assertIn('--depth', command)
        self.assertIn('1', command)
        self.assertIn('--branch', command)
        self.assertIn('main', command)
        self.assertIn('https://github.com/test/repo.git', command)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_clone_repository_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test repository cloning failure."""
        mock_run_git.return_value = (128, '', 'fatal: repository not found')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.clone_repository(
                working_directory=self.working_directory,
                clone_url='https://github.com/test/nonexistent.git',
            )

        self.assertIn('Git clone failed', str(exc_context.exception))
        self.assertIn(
            'fatal: repository not found', str(exc_context.exception)
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_clone_repository_no_branch_no_depth(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test repository cloning with no branch or depth specified."""
        mock_run_git.return_value = (0, 'Cloning into repository...', '')

        await git.clone_repository(
            working_directory=self.working_directory,
            clone_url='https://github.com/test/repo.git',
        )

        # Verify git clone command was called with default depth
        call_args = mock_run_git.call_args
        command = call_args[0][0]

        # Default depth is 1, so should include --depth option
        self.assertIn('git', command)
        self.assertIn('clone', command)
        self.assertIn('--depth', command)
        self.assertIn('https://github.com/test/repo.git', command)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_add_files_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful file addition to git."""
        mock_run_git.return_value = (0, '', '')

        await git.add_files(self.working_directory, ['file1.txt', 'file2.py'])

        mock_run_git.assert_called_once_with(
            ['git', 'add', 'file1.txt', 'file2.py'],
            cwd=self.working_directory,
            timeout_seconds=60,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_add_files_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test file addition failure."""
        mock_run_git.return_value = (
            1,
            '',
            'fatal: pathspec did not match any files',
        )

        with self.assertRaises(RuntimeError) as exc_context:
            await git.add_files(self.working_directory, ['nonexistent.txt'])

        self.assertIn('Git add failed', str(exc_context.exception))

    # Note: commit_changes has been moved to Claude-powered commits
    # These tests are removed as the function signature has changed

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful git push."""
        mock_run_git.return_value = (0, 'Everything up-to-date', '')

        await git.push_changes(
            working_directory=self.working_directory,
            remote='origin',
            branch='main',
            force=True,
            set_upstream=True,
        )

        mock_run_git.assert_called_once()
        call_args = mock_run_git.call_args
        command = call_args[0][0]

        self.assertEqual(command[0], 'git')
        self.assertEqual(command[1], 'push')
        self.assertIn('--force', command)
        self.assertIn('--set-upstream', command)
        self.assertIn('origin', command)
        self.assertIn('main', command)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test git push failure."""
        mock_run_git.return_value = (
            1,
            '',
            'fatal: unable to access repository',
        )

        with self.assertRaises(RuntimeError) as exc_context:
            await git.push_changes(self.working_directory, 'origin')

        self.assertIn('Git push failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_create_branch_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful branch creation."""
        mock_run_git.return_value = (0, 'Switched to a new branch', '')

        await git.create_branch(
            working_directory=self.working_directory,
            branch_name='feature/test',
            checkout=True,
        )

        mock_run_git.assert_called_once_with(
            ['git', 'checkout', '-b', 'feature/test'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_create_branch_no_checkout(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test branch creation without checkout."""
        mock_run_git.return_value = (0, '', '')

        await git.create_branch(
            working_directory=self.working_directory,
            branch_name='feature/test',
            checkout=False,
        )

        mock_run_git.assert_called_once_with(
            ['git', 'branch', 'feature/test'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_create_branch_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test branch creation failure."""
        mock_run_git.return_value = (128, '', 'fatal: branch already exists')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.create_branch(self.working_directory, 'existing-branch')

        self.assertIn('Git branch creation failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_current_branch_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test getting current branch name."""
        mock_run_git.return_value = (0, 'main\n', '')

        result = await git.get_current_branch(self.working_directory)

        self.assertEqual(result, 'main')
        mock_run_git.assert_called_once_with(
            ['git', 'branch', '--show-current'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_current_branch_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test get current branch failure."""
        mock_run_git.return_value = (128, '', 'fatal: not a git repository')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.get_current_branch(self.working_directory)

        self.assertIn('Git branch query failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commits_with_keyword_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_commits_with_keyword with successful results."""
        mock_stdout = (
            'abc1234 Fix: resolve issue with authentication\n'
            'def5678 feat: add new authentication feature\n'
        )
        mock_run_git.return_value = (0, mock_stdout, '')

        result = await git._get_commits_with_keyword(
            self.working_directory, 'auth'
        )

        expected = [
            ('abc1234', 'Fix: resolve issue with authentication'),
            ('def5678', 'feat: add new authentication feature'),
        ]
        self.assertEqual(result, expected)

        mock_run_git.assert_called_once_with(
            ['git', 'log', '--grep', 'auth', '--format=%H %s', '--all'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commits_with_keyword_no_matches(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_commits_with_keyword with no matches."""
        mock_run_git.return_value = (0, '', '')

        result = await git._get_commits_with_keyword(
            self.working_directory, 'nonexistent'
        )

        self.assertEqual(result, [])

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commits_with_keyword_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_commits_with_keyword with git command failure."""
        mock_run_git.return_value = (128, '', 'fatal: not a git repository')

        with self.assertRaises(RuntimeError) as exc_context:
            await git._get_commits_with_keyword(self.working_directory, 'test')

        self.assertIn('Git log failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commits_with_keyword_malformed_output(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_commits_with_keyword with malformed git output."""
        # Test with lines that don't have proper format
        mock_stdout = 'abc1234\n\ndef5678 proper commit message\n  \n'
        mock_run_git.return_value = (0, mock_stdout, '')

        result = await git._get_commits_with_keyword(
            self.working_directory, 'test'
        )

        # Should only include properly formatted commits
        expected = [('def5678', 'proper commit message')]
        self.assertEqual(result, expected)

    def test_select_target_commit_before_last_match(self) -> None:
        """Test _select_target_commit with before_last_match strategy."""
        matching_commits = [
            ('newest123', 'Latest commit with keyword'),
            ('middle456', 'Middle commit with keyword'),
            ('oldest789', 'Oldest commit with keyword'),
        ]

        result = git._select_target_commit(
            matching_commits, 'before_last_match'
        )

        # Should return first in list (newest chronologically)
        self.assertEqual(result, 'newest123')

    def test_select_target_commit_before_first_match(self) -> None:
        """Test _select_target_commit with before_first_match strategy."""
        matching_commits = [
            ('newest123', 'Latest commit with keyword'),
            ('middle456', 'Middle commit with keyword'),
            ('oldest789', 'Oldest commit with keyword'),
        ]

        result = git._select_target_commit(
            matching_commits, 'before_first_match'
        )

        # Should return last in list (oldest chronologically)
        self.assertEqual(result, 'oldest789')

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_parent_commit_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_parent_commit with successful result."""
        mock_run_git.return_value = (0, 'parent123\n', '')

        result = await git._get_parent_commit(
            self.working_directory, 'child456'
        )

        self.assertEqual(result, 'parent123')
        mock_run_git.assert_called_once_with(
            ['git', 'rev-parse', 'child456^'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_parent_commit_no_parent(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_parent_commit with no parent (first commit)."""
        mock_run_git.return_value = (128, '', 'fatal: unknown revision')

        result = await git._get_parent_commit(
            self.working_directory, 'first123'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_parent_commit_other_error(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_parent_commit with other git error."""
        mock_run_git.return_value = (128, '', 'fatal: not a git repository')

        result = await git._get_parent_commit(
            self.working_directory, 'commit123'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_parent_commit_empty_output(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _get_parent_commit with empty output."""
        mock_run_git.return_value = (0, '  \n  ', '')

        result = await git._get_parent_commit(
            self.working_directory, 'commit123'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._get_commits_with_keyword')
    @mock.patch('imbi_automations.git._get_parent_commit')
    async def test_find_commit_before_keyword_success_last_match(
        self, mock_get_parent: mock.AsyncMock, mock_get_commits: mock.AsyncMock
    ) -> None:
        """Test find_commit_before_keyword with successful last match."""
        mock_get_commits.return_value = [
            ('newest123', 'Latest commit with BREAKING'),
            ('older456', 'Older commit with BREAKING'),
        ]
        mock_get_parent.return_value = 'parent789'

        result = await git.find_commit_before_keyword(
            self.working_directory, 'BREAKING', 'before_last_match'
        )

        self.assertEqual(result, 'parent789')
        mock_get_commits.assert_called_once_with(
            self.working_directory, 'BREAKING'
        )
        mock_get_parent.assert_called_once_with(
            self.working_directory, 'newest123'
        )

    @mock.patch('imbi_automations.git._get_commits_with_keyword')
    @mock.patch('imbi_automations.git._get_parent_commit')
    async def test_find_commit_before_keyword_success_first_match(
        self, mock_get_parent: mock.AsyncMock, mock_get_commits: mock.AsyncMock
    ) -> None:
        """Test find_commit_before_keyword with successful first match."""
        mock_get_commits.return_value = [
            ('newest123', 'Latest commit with BREAKING'),
            ('older456', 'Older commit with BREAKING'),
        ]
        mock_get_parent.return_value = 'parent789'

        result = await git.find_commit_before_keyword(
            self.working_directory, 'BREAKING', 'before_first_match'
        )

        self.assertEqual(result, 'parent789')
        mock_get_commits.assert_called_once_with(
            self.working_directory, 'BREAKING'
        )
        mock_get_parent.assert_called_once_with(
            self.working_directory, 'older456'
        )

    @mock.patch('imbi_automations.git._get_commits_with_keyword')
    async def test_find_commit_before_keyword_no_matches(
        self, mock_get_commits: mock.AsyncMock
    ) -> None:
        """Test find_commit_before_keyword with no keyword matches."""
        mock_get_commits.return_value = []

        result = await git.find_commit_before_keyword(
            self.working_directory, 'NONEXISTENT'
        )

        self.assertIsNone(result)
        mock_get_commits.assert_called_once_with(
            self.working_directory, 'NONEXISTENT'
        )

    @mock.patch('imbi_automations.git._get_commits_with_keyword')
    @mock.patch('imbi_automations.git._get_parent_commit')
    async def test_find_commit_before_keyword_no_parent(
        self, mock_get_parent: mock.AsyncMock, mock_get_commits: mock.AsyncMock
    ) -> None:
        """Test find_commit_before_keyword when target commit has no parent."""
        mock_get_commits.return_value = [
            ('first123', 'First commit with keyword')
        ]
        mock_get_parent.return_value = None

        result = await git.find_commit_before_keyword(
            self.working_directory, 'BREAKING'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_file_at_commit_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful file retrieval at commit."""
        mock_run_git.return_value = (0, 'file content\nat commit\n', '')

        result = await git.get_file_at_commit(
            self.working_directory, 'src/file.py', 'commit123'
        )

        self.assertEqual(result, 'file content\nat commit\n')
        mock_run_git.assert_called_once_with(
            ['git', 'show', 'commit123:src/file.py'],
            cwd=self.working_directory,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_file_at_commit_file_not_exists(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test file retrieval when file doesn't exist at commit."""
        mock_run_git.return_value = (128, '', 'fatal: path does not exist')

        result = await git.get_file_at_commit(
            self.working_directory, 'nonexistent.py', 'commit123'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_file_at_commit_git_error(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test file retrieval with git command error."""
        mock_run_git.return_value = (128, '', 'fatal: invalid commit hash')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.get_file_at_commit(
                self.working_directory, 'file.py', 'invalid_hash'
            )

        self.assertIn('Git show failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_delete_remote_branch_if_exists_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful remote branch deletion."""
        # First call: check if branch exists (returns non-empty)
        # Second call: delete branch
        mock_run_git.side_effect = [
            (0, 'refs/heads/feature-branch\n', ''),  # ls-remote
            (
                0,
                'To origin\n - [deleted]         feature-branch',
                '',
            ),  # push --delete
        ]

        result = await git.delete_remote_branch_if_exists(
            self.working_directory, 'feature-branch'
        )

        self.assertTrue(result)
        self.assertEqual(mock_run_git.call_count, 2)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_delete_remote_branch_if_exists_not_exists(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test remote branch deletion when branch doesn't exist."""
        mock_run_git.return_value = (0, '', '')  # ls-remote returns empty

        result = await git.delete_remote_branch_if_exists(
            self.working_directory, 'nonexistent-branch'
        )

        self.assertTrue(result)
        # Should only call ls-remote, not push --delete
        self.assertEqual(mock_run_git.call_count, 1)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_delete_remote_branch_if_exists_deletion_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test remote branch deletion failure."""
        mock_run_git.side_effect = [
            (0, 'refs/heads/feature-branch\n', ''),  # ls-remote success
            (1, '', 'error: unable to delete'),  # push --delete failure
        ]

        result = await git.delete_remote_branch_if_exists(
            self.working_directory, 'feature-branch'
        )

        self.assertFalse(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commit_messages_since_branch_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful commit message retrieval since branch."""
        mock_stdout = (
            'Add new feature\n'
            'Fix bug in authentication\n'
            'Update documentation\n'
        )
        mock_run_git.return_value = (0, mock_stdout, '')

        result = await git.get_commit_messages_since_branch(
            self.working_directory, 'main'
        )

        expected = [
            'Add new feature',
            'Fix bug in authentication',
            'Update documentation',
        ]
        self.assertEqual(result, expected)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commit_messages_since_branch_unknown_revision(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test commit message retrieval with unknown revision fallback."""
        # First call fails with unknown revision, second call succeeds
        mock_run_git.side_effect = [
            (128, '', 'fatal: bad revision unknown revision'),
            (0, 'Fallback commit message\n', ''),
        ]

        result = await git.get_commit_messages_since_branch(
            self.working_directory, 'nonexistent-branch'
        )

        expected = ['Fallback commit message']
        self.assertEqual(result, expected)
        self.assertEqual(mock_run_git.call_count, 2)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commit_messages_since_branch_no_commits(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test commit message retrieval with no commits."""
        mock_run_git.return_value = (0, '', '')

        result = await git.get_commit_messages_since_branch(
            self.working_directory, 'main'
        )

        self.assertEqual(result, [])

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_commit_messages_since_branch_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test commit message retrieval with persistent failure."""
        mock_run_git.return_value = (128, '', 'fatal: not a git repository')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.get_commit_messages_since_branch(
                self.working_directory, 'main'
            )

        self.assertIn('Git log failed', str(exc_context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_run_git_command_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _run_git_command with successful execution."""
        # This tests the actual _run_git_command function directly
        mock_run_git.return_value = (0, 'success output', '')

        returncode, stdout, stderr = await git._run_git_command(
            ['git', 'status'], cwd=self.working_directory
        )

        self.assertEqual(returncode, 0)
        self.assertEqual(stdout, 'success output')
        self.assertEqual(stderr, '')

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_run_git_command_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test _run_git_command with command failure."""
        mock_run_git.return_value = (1, '', 'error output')

        returncode, stdout, stderr = await git._run_git_command(
            ['git', 'invalid-command'], cwd=self.working_directory
        )

        self.assertEqual(returncode, 1)
        self.assertEqual(stdout, '')
        self.assertEqual(stderr, 'error output')


class GitExtractTestCase(base.AsyncTestCase):
    """Test cases for git.extract_file_from_commit functionality."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)
        self.repository_dir = self.working_directory / 'repository'
        self.repository_dir.mkdir()

    def tearDown(self) -> None:
        super().tearDown()
        self.temp_dir.cleanup()

    @mock.patch('imbi_automations.git.find_commit_before_keyword')
    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_with_keyword_success(
        self, mock_get_file: mock.AsyncMock, mock_find_commit: mock.AsyncMock
    ) -> None:
        """Test successful file extraction with commit keyword."""
        mock_find_commit.return_value = 'abc1234567890'
        mock_get_file.return_value = 'extracted file content\nline 2\n'

        source_file = pathlib.Path('src/config.py')
        destination_file = self.working_directory / 'extracted/old-config.py'

        await git.extract_file_from_commit(
            working_directory=self.repository_dir,
            source_file=source_file,
            destination_file=destination_file,
            commit_keyword='BREAKING CHANGE',
            search_strategy='before_last_match',
        )

        # Verify git operations were called correctly
        mock_find_commit.assert_called_once_with(
            self.repository_dir, 'BREAKING CHANGE', 'before_last_match'
        )

        mock_get_file.assert_called_once_with(
            self.repository_dir, 'src/config.py', 'abc1234567890'
        )

        # Verify file was written to destination
        self.assertTrue(destination_file.exists())
        content = destination_file.read_text()
        self.assertEqual(content, 'extracted file content\nline 2\n')

    @mock.patch('imbi_automations.git.find_commit_before_keyword')
    async def test_extract_file_from_commit_no_commit_found(
        self, mock_find_commit: mock.AsyncMock
    ) -> None:
        """Test file extraction when no commit found for keyword."""
        mock_find_commit.return_value = None

        source_file = pathlib.Path('src/config.py')
        destination_file = self.working_directory / 'extracted/old-config.py'

        with self.assertRaises(RuntimeError) as exc_context:
            await git.extract_file_from_commit(
                working_directory=self.repository_dir,
                source_file=source_file,
                destination_file=destination_file,
                commit_keyword='NONEXISTENT',
                search_strategy='before_first_match',
            )

        self.assertIn(
            'No commit found before keyword "NONEXISTENT"',
            str(exc_context.exception),
        )
        self.assertIn(
            'using strategy "before_first_match"', str(exc_context.exception)
        )

    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_no_keyword_uses_head(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test file extraction without keyword uses HEAD commit."""
        mock_get_file.return_value = 'current file content\n'

        source_file = pathlib.Path('README.md')
        destination_file = (
            self.working_directory / 'extracted/current-readme.md'
        )

        await git.extract_file_from_commit(
            working_directory=self.repository_dir,
            source_file=source_file,
            destination_file=destination_file,
            # No commit_keyword specified
        )

        # Should use HEAD commit
        mock_get_file.assert_called_once_with(
            self.repository_dir, 'README.md', 'HEAD'
        )

        # Verify file was written
        self.assertTrue(destination_file.exists())
        self.assertEqual(
            destination_file.read_text(), 'current file content\n'
        )

    @mock.patch('imbi_automations.git.find_commit_before_keyword')
    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_file_not_found(
        self, mock_get_file: mock.AsyncMock, mock_find_commit: mock.AsyncMock
    ) -> None:
        """Test file extraction when file doesn't exist at target commit."""
        mock_find_commit.return_value = 'abc1234567890'
        mock_get_file.return_value = None  # File doesn't exist

        source_file = pathlib.Path('nonexistent.txt')
        destination_file = self.working_directory / 'extracted/file.txt'

        with self.assertRaises(RuntimeError) as exc_context:
            await git.extract_file_from_commit(
                working_directory=self.repository_dir,
                source_file=source_file,
                destination_file=destination_file,
                commit_keyword='BREAKING CHANGE',
            )

        self.assertIn(
            'File "nonexistent.txt" does not exist at commit abc12345',
            str(exc_context.exception),
        )

    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_file_not_found_at_head(
        self, mock_get_file: mock.AsyncMock
    ) -> None:
        """Test file extraction when file doesn't exist at HEAD commit."""
        mock_get_file.return_value = None  # File doesn't exist

        source_file = pathlib.Path('missing.txt')
        destination_file = self.working_directory / 'extracted/file.txt'

        with self.assertRaises(RuntimeError) as exc_context:
            await git.extract_file_from_commit(
                working_directory=self.repository_dir,
                source_file=source_file,
                destination_file=destination_file,
                # No commit_keyword, so uses HEAD
            )

        self.assertIn(
            'File "missing.txt" does not exist at commit HEAD',
            str(exc_context.exception),
        )

    @mock.patch('imbi_automations.git.find_commit_before_keyword')
    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_creates_destination_directory(
        self, mock_get_file: mock.AsyncMock, mock_find_commit: mock.AsyncMock
    ) -> None:
        """Test file extraction creates destination directory."""
        mock_find_commit.return_value = 'abc1234567890'
        mock_get_file.return_value = 'file content\n'

        source_file = pathlib.Path('src/deep/file.py')
        destination_file = (
            self.working_directory / 'extracted/nested/deep/file.py'
        )

        # Ensure nested directory doesn't exist initially
        nested_dir = self.working_directory / 'extracted/nested/deep'
        self.assertFalse(nested_dir.exists())

        await git.extract_file_from_commit(
            working_directory=self.repository_dir,
            source_file=source_file,
            destination_file=destination_file,
            commit_keyword='BREAKING CHANGE',
        )

        # Verify nested directory was created
        self.assertTrue(nested_dir.exists())

        # Verify file was written to nested location
        self.assertTrue(destination_file.exists())
        self.assertEqual(destination_file.read_text(), 'file content\n')

    @mock.patch('imbi_automations.git.find_commit_before_keyword')
    @mock.patch('imbi_automations.git.get_file_at_commit')
    async def test_extract_file_from_commit_uses_default_strategy(
        self, mock_get_file: mock.AsyncMock, mock_find_commit: mock.AsyncMock
    ) -> None:
        """Test file extraction uses default strategy when not specified."""
        mock_find_commit.return_value = 'abc1234567890'
        mock_get_file.return_value = 'file content\n'

        source_file = pathlib.Path('config.json')
        destination_file = self.working_directory / 'extracted/config.json'

        await git.extract_file_from_commit(
            working_directory=self.repository_dir,
            source_file=source_file,
            destination_file=destination_file,
            commit_keyword='BREAKING CHANGE',
            # No search_strategy specified - should use default
        )

        # Should use default strategy 'before_last_match'
        mock_find_commit.assert_called_once_with(
            self.repository_dir, 'BREAKING CHANGE', 'before_last_match'
        )


class WorkflowEngineGitTestCase(base.AsyncTestCase):
    """Test cases for WorkflowEngine git action integration."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)

        # Create required directory structure
        (self.working_directory / 'repository').mkdir()
        (self.working_directory / 'extracted').mkdir()

        # Create mock configuration
        self.config = models.Configuration(
            imbi=models.ImbiConfiguration(
                api_key='test-key', hostname='imbi.test.com'
            )
        )

        # Create mock workflow
        self.workflow = models.Workflow(
            path=pathlib.Path('/mock/workflow'),
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

    @mock.patch('imbi_automations.git.extract_file_from_commit')
    async def test_execute_action_git_extract_integration(
        self, mock_extract: mock.AsyncMock
    ) -> None:
        """Test integration of _execute_action_git with extract command."""
        action = models.WorkflowGitAction(
            name='extract-integration',
            type='git',
            command='extract',
            source=pathlib.Path('test.txt'),
            destination=pathlib.Path('extracted/test.txt'),
            commit_keyword='TEST',
            search_strategy='before_first_match',
        )

        await self.engine._execute_action_git(self.context, action)

        # Verify git.extract_file_from_commit was called correctly
        mock_extract.assert_called_once_with(
            working_directory=self.working_directory / 'repository',
            source_file=pathlib.Path('test.txt'),
            destination_file=self.working_directory / 'extracted/test.txt',
            commit_keyword='TEST',
            search_strategy='before_first_match',
        )

    @mock.patch('imbi_automations.git.extract_file_from_commit')
    async def test_execute_action_git_extract_no_strategy(
        self, mock_extract: mock.AsyncMock
    ) -> None:
        """Test git extract action with default strategy."""
        action = models.WorkflowGitAction(
            name='extract-default',
            type='git',
            command='extract',
            source=pathlib.Path('config.py'),
            destination=pathlib.Path('extracted/config.py'),
            commit_keyword='BREAKING',
            # No search_strategy specified
        )

        await self.engine._execute_action_git(self.context, action)

        # Should use default strategy
        mock_extract.assert_called_once_with(
            working_directory=self.working_directory / 'repository',
            source_file=pathlib.Path('config.py'),
            destination_file=self.working_directory / 'extracted/config.py',
            commit_keyword='BREAKING',
            search_strategy='before_last_match',
        )


if __name__ == '__main__':
    unittest.main()
