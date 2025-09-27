"""Comprehensive tests for the git module."""

import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import git
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

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_success(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test successful commit creation."""
        mock_run_git.return_value = (0, '[main abc1234] Test commit', '')

        await git.commit_changes(
            working_directory=self.working_directory,
            message='Test commit message',
            author_name='Test User',
            author_email='test@example.com',
        )

        mock_run_git.assert_called_once()
        call_args = mock_run_git.call_args
        command = call_args[0][0]

        self.assertEqual(command[0], 'git')
        self.assertEqual(command[1], 'commit')
        self.assertIn('-m', command)
        self.assertIn('imbi-automations: Test commit message', command)
        self.assertIn('--author', command)
        # Check that author format is correct
        author_idx = command.index('--author')
        self.assertIn('Test User <test@example.com>', command[author_idx + 1])

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_nothing_to_commit(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test commit creation with nothing to commit."""
        mock_run_git.return_value = (
            1,
            '',
            'nothing to commit, working tree clean',
        )

        # Should return empty string when nothing to commit
        result = await git.commit_changes(
            self.working_directory, 'Test commit'
        )

        self.assertEqual(result, '')

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_actual_failure(
        self, mock_run_git: mock.AsyncMock
    ) -> None:
        """Test commit creation with actual git failure."""
        mock_run_git.return_value = (1, '', 'fatal: not a git repository')

        with self.assertRaises(RuntimeError) as exc_context:
            await git.commit_changes(self.working_directory, 'Test commit')

        self.assertIn('Git commit failed', str(exc_context.exception))

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


if __name__ == '__main__':
    unittest.main()
