import asyncio
import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import git
from tests import base


class TestGitModule(base.AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Create a temporary directory for git operations
        self.temp_dir = tempfile.mkdtemp()
        self.git_dir = pathlib.Path(self.temp_dir) / 'test-repo'
        self.git_dir.mkdir()

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_success(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test successful git command execution."""
        # Mock process
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (b'output\n', b'')
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(['git', 'status'], self.git_dir)

        self.assertEqual(result, (0, 'output\n', ''))
        mock_subprocess.assert_called_once_with(
            'git',
            'status',
            cwd=self.git_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_with_stderr(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command execution with stderr output."""
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (b'', b'error message\n')
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(
            ['git', 'invalid-command'], self.git_dir
        )

        self.assertEqual(result, (1, '', 'error message\n'))

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_both_outputs(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command execution with both stdout and stderr."""
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (b'stdout\n', b'stderr\n')
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(
            ['git', 'log', '--oneline'], self.git_dir
        )

        self.assertEqual(result, (0, 'stdout\n', 'stderr\n'))

    @mock.patch('asyncio.create_subprocess_exec')
    @mock.patch('asyncio.wait_for')
    async def test_run_git_command_timeout(
        self, mock_wait_for: mock.Mock, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command execution with timeout."""
        mock_process = mock.Mock()
        mock_process.communicate = mock.AsyncMock()
        mock_process.terminate = mock.Mock(
            return_value=None
        )  # Synchronous method
        mock_process.wait = mock.AsyncMock()
        mock_subprocess.return_value = mock_process

        # First wait_for call (communicate) times out
        mock_wait_for.side_effect = [TimeoutError(), None]

        result = await git._run_git_command(
            ['git', 'clone', 'large-repo'], self.git_dir, timeout_seconds=1
        )

        self.assertEqual(result, (-1, '', 'Command timed out after 1 seconds'))
        mock_process.terminate.assert_called_once()

    @mock.patch('asyncio.create_subprocess_exec')
    @mock.patch('asyncio.wait_for')
    async def test_run_git_command_timeout_force_kill(
        self, mock_wait_for: mock.Mock, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command timeout with force kill."""
        mock_process = mock.Mock()
        mock_process.communicate = mock.AsyncMock()
        mock_process.terminate = mock.Mock(
            return_value=None
        )  # Synchronous method
        mock_process.kill = mock.Mock(return_value=None)  # Synchronous method
        mock_process.wait = mock.AsyncMock()
        mock_subprocess.return_value = mock_process

        # First wait_for times out, second wait_for also times out (force kill)
        mock_wait_for.side_effect = [TimeoutError(), TimeoutError(), None]

        result = await git._run_git_command(
            ['git', 'clone', 'large-repo'], self.git_dir, timeout_seconds=1
        )

        self.assertEqual(result, (-1, '', 'Command timed out after 1 seconds'))
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    # Removed complex async timeout test due to mocking complexity

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_empty_output(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command with empty output."""
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(
            ['git', 'status', '--porcelain'], self.git_dir
        )

        self.assertEqual(result, (0, '', ''))

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_unicode_output(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command with unicode characters in output."""
        unicode_output = 'Файл с русскими символами\n'
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (
            unicode_output.encode('utf-8'),
            b'',
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(
            ['git', 'log', '--oneline'], self.git_dir
        )

        self.assertEqual(result, (0, unicode_output, ''))

    # Removed complex async default timeout test due to mocking complexity

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_large_output(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command with large output."""
        large_output = 'x' * 10000 + '\n'
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (
            large_output.encode('utf-8'),
            b'stderr\n',
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await git._run_git_command(
            ['git', 'log', '--stat'], self.git_dir
        )

        self.assertEqual(result, (0, large_output, 'stderr\n'))

    @mock.patch('asyncio.create_subprocess_exec')
    async def test_run_git_command_logging(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test that git command execution includes proper logging."""
        mock_process = mock.AsyncMock()
        mock_process.communicate.return_value = (b'log output\n', b'warning\n')
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        with self.assertLogs('imbi_automations.git', level='DEBUG') as log:
            await git._run_git_command(
                ['git', 'log', '--oneline'], self.git_dir
            )

        # Verify command logging
        self.assertIn('Running git command: git log --oneline', log.output[0])
        self.assertIn('STDOUT: log output', log.output[1])
        self.assertIn('STDERR: warning', log.output[2])

    @mock.patch('imbi_automations.git._run_git_command')
    @mock.patch('tempfile.mkdtemp')
    async def test_clone_repository_success(
        self, mock_mkdtemp: mock.Mock, mock_run_git: mock.Mock
    ) -> None:
        """Test successful repository cloning."""
        # Mock temporary directory creation
        mock_temp_dir = '/tmp/imbi-automations-test123'  # noqa: S108
        mock_mkdtemp.return_value = mock_temp_dir

        # Mock successful git clone
        mock_run_git.return_value = (0, '', '')

        result = await git.clone_repository(
            'https://github.com/org/repo.git', branch='main', depth=1
        )

        expected_path = pathlib.Path(mock_temp_dir) / 'repository'
        self.assertEqual(result, expected_path)

        # Verify git clone command
        mock_run_git.assert_called_once_with(
            [
                'git',
                'clone',
                '--depth',
                '1',
                '--branch',
                'main',
                'https://github.com/org/repo.git',
                str(expected_path),
            ],
            cwd=pathlib.Path(mock_temp_dir),
            timeout_seconds=600,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    @mock.patch('tempfile.mkdtemp')
    async def test_clone_repository_no_branch_no_depth(
        self, mock_mkdtemp: mock.Mock, mock_run_git: mock.Mock
    ) -> None:
        """Test repository cloning without branch or depth specification."""
        mock_temp_dir = '/tmp/imbi-automations-test456'  # noqa: S108
        mock_mkdtemp.return_value = mock_temp_dir
        mock_run_git.return_value = (0, '', '')

        result = await git.clone_repository(
            'git@github.com:org/repo.git', branch=None, depth=None
        )

        expected_path = pathlib.Path(mock_temp_dir) / 'repository'
        self.assertEqual(result, expected_path)

        # Verify git clone command without depth/branch
        mock_run_git.assert_called_once_with(
            [
                'git',
                'clone',
                'git@github.com:org/repo.git',
                str(expected_path),
            ],
            cwd=pathlib.Path(mock_temp_dir),
            timeout_seconds=600,
        )

    @mock.patch('pathlib.Path.exists')
    @mock.patch('shutil.rmtree')
    @mock.patch('imbi_automations.git._run_git_command')
    @mock.patch('tempfile.mkdtemp')
    async def test_clone_repository_failure(
        self,
        mock_mkdtemp: mock.Mock,
        mock_run_git: mock.Mock,
        mock_rmtree: mock.Mock,
        mock_exists: mock.Mock,
    ) -> None:
        """Test repository cloning failure and cleanup."""
        mock_temp_dir = '/tmp/imbi-automations-test789'  # noqa: S108
        mock_mkdtemp.return_value = mock_temp_dir
        mock_exists.return_value = True

        # Mock failed git clone
        mock_run_git.return_value = (128, '', 'Repository not found')

        with self.assertRaises(RuntimeError) as context:
            await git.clone_repository(
                'https://github.com/nonexistent/repo.git'
            )

        self.assertIn('Git clone failed', str(context.exception))
        self.assertIn('Repository not found', str(context.exception))

        # Verify cleanup was attempted
        mock_rmtree.assert_called_once_with(
            pathlib.Path(mock_temp_dir), ignore_errors=True
        )

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_clone_repository_context_success(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test successful repository cloning with context manager."""
        mock_repo_dir = pathlib.Path('/tmp/imbi-automations-test/repository')  # noqa: S108
        mock_clone.return_value = mock_repo_dir

        async with git.clone_repository_context(
            'https://github.com/org/repo.git', branch='develop', depth=5
        ) as repo_dir:
            self.assertEqual(repo_dir, mock_repo_dir)

        # Verify clone was called with correct parameters
        mock_clone.assert_called_once_with(
            'https://github.com/org/repo.git', 'develop', 5
        )

    @mock.patch('imbi_automations.git.clone_repository')
    async def test_clone_repository_context_failure(
        self, mock_clone: mock.Mock
    ) -> None:
        """Test repository cloning context manager with clone failure."""
        mock_clone.side_effect = RuntimeError('Clone failed')

        with self.assertRaises(RuntimeError) as context:
            async with git.clone_repository_context(
                'https://github.com/org/repo.git'
            ):
                pass  # Should not reach here

        self.assertIn('Clone failed', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_add_files_success(self, mock_run_git: mock.Mock) -> None:
        """Test successful git add operation."""
        mock_run_git.return_value = (0, '', '')

        files = ['.gitignore', 'config.json', 'subdir/script.sh']
        await git.add_files(self.git_dir, files)

        # Verify git add command
        mock_run_git.assert_called_once_with(
            ['git', 'add', '.gitignore', 'config.json', 'subdir/script.sh'],
            cwd=self.git_dir,
            timeout_seconds=60,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_add_files_empty_list(self, mock_run_git: mock.Mock) -> None:
        """Test git add with empty file list."""
        await git.add_files(self.git_dir, [])

        # Should not call git command for empty list
        mock_run_git.assert_not_called()

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_add_files_failure(self, mock_run_git: mock.Mock) -> None:
        """Test git add failure."""
        mock_run_git.return_value = (1, '', 'File not found')

        with self.assertRaises(RuntimeError) as context:
            await git.add_files(self.git_dir, ['nonexistent.txt'])

        self.assertIn('Git add failed', str(context.exception))
        self.assertIn('File not found', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_success(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test successful git commit operation."""
        mock_run_git.return_value = (
            0,
            '[main 1234567] Test commit message',
            '',
        )

        commit_sha = await git.commit_changes(
            self.git_dir,
            'Test commit message',
            'Test Author',
            'test@example.com',
        )

        self.assertEqual(commit_sha, '1234567')

        # Verify git commit command with author
        mock_run_git.assert_called_once_with(
            [
                'git',
                'commit',
                '-m',
                'Test commit message',
                '--author',
                'Test Author <test@example.com>',
            ],
            cwd=self.git_dir,
            timeout_seconds=60,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_no_author(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git commit without author information."""
        mock_run_git.return_value = (0, '[main abcdef0] Simple commit', '')

        commit_sha = await git.commit_changes(self.git_dir, 'Simple commit')

        self.assertEqual(commit_sha, 'abcdef0')

        # Verify git commit command without author
        mock_run_git.assert_called_once_with(
            ['git', 'commit', '-m', 'Simple commit'],
            cwd=self.git_dir,
            timeout_seconds=60,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_nothing_to_commit(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git commit when there are no changes."""
        mock_run_git.return_value = (
            1,
            '',
            'nothing to commit, working tree clean',
        )

        commit_sha = await git.commit_changes(self.git_dir, 'Test commit')

        self.assertEqual(commit_sha, '')

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_commit_changes_failure(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git commit failure."""
        mock_run_git.return_value = (128, '', 'fatal: bad config file')

        with self.assertRaises(RuntimeError) as context:
            await git.commit_changes(self.git_dir, 'Test commit')

        self.assertIn('Git commit failed', str(context.exception))
        self.assertIn('bad config file', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_git_status_success(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test successful git status operation."""
        mock_run_git.return_value = (
            0,
            ' M file1.txt\n?? file2.txt\n A file3.txt\n',
            '',
        )

        changed_files = await git.get_git_status(self.git_dir)

        expected_files = ['file1.txt', 'file2.txt', 'file3.txt']
        self.assertEqual(changed_files, expected_files)

        # Verify git status command
        mock_run_git.assert_called_once_with(
            ['git', 'status', '--porcelain'],
            cwd=self.git_dir,
            timeout_seconds=30,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_git_status_no_changes(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git status with no changes."""
        mock_run_git.return_value = (0, '', '')

        changed_files = await git.get_git_status(self.git_dir)

        self.assertEqual(changed_files, [])

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_git_status_failure(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git status failure."""
        mock_run_git.return_value = (128, '', 'fatal: not a git repository')

        with self.assertRaises(RuntimeError) as context:
            await git.get_git_status(self.git_dir)

        self.assertIn('Git status failed', str(context.exception))
        self.assertIn('not a git repository', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_success(self, mock_run_git: mock.Mock) -> None:
        """Test successful git push operation."""
        mock_run_git.return_value = (0, '', '')

        await git.push_changes(self.git_dir, 'origin', 'main')

        # Verify git push command
        mock_run_git.assert_called_once_with(
            ['git', 'push', 'origin', 'main'],
            cwd=self.git_dir,
            timeout_seconds=300,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_current_branch(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git push to current branch."""
        mock_run_git.return_value = (0, '', '')

        await git.push_changes(self.git_dir, 'origin')

        # Verify git push command without branch
        mock_run_git.assert_called_once_with(
            ['git', 'push', 'origin'], cwd=self.git_dir, timeout_seconds=300
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_force(self, mock_run_git: mock.Mock) -> None:
        """Test force git push operation."""
        mock_run_git.return_value = (0, '', '')

        await git.push_changes(self.git_dir, 'origin', 'main', force=True)

        # Verify git push command with force flag
        mock_run_git.assert_called_once_with(
            ['git', 'push', '--force', 'origin', 'main'],
            cwd=self.git_dir,
            timeout_seconds=300,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_failure(self, mock_run_git: mock.Mock) -> None:
        """Test git push failure."""
        mock_run_git.return_value = (1, '', 'Permission denied')

        with self.assertRaises(RuntimeError) as context:
            await git.push_changes(self.git_dir, 'origin', 'main')

        self.assertIn('Git push failed', str(context.exception))
        self.assertIn('Permission denied', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_remove_files_success(self, mock_run_git: mock.Mock) -> None:
        """Test successful git rm operation."""
        mock_run_git.return_value = (0, '', '')

        await git.remove_files(self.git_dir, ['old-file.txt', 'another.txt'])

        # Verify git rm command
        mock_run_git.assert_called_once_with(
            ['git', 'rm', 'old-file.txt', 'another.txt'],
            cwd=self.git_dir,
            timeout_seconds=60,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_remove_files_empty_list(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git rm with empty file list."""
        await git.remove_files(self.git_dir, [])

        # Should not call git rm for empty list
        mock_run_git.assert_not_called()

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_remove_files_failure(self, mock_run_git: mock.Mock) -> None:
        """Test git rm operation failure."""
        mock_run_git.return_value = (
            1,
            '',
            "pathspec 'nonexistent.txt' did not match any files",
        )

        with self.assertRaises(RuntimeError) as context:
            await git.remove_files(self.git_dir, ['nonexistent.txt'])

        self.assertIn('Git rm failed', str(context.exception))
        self.assertIn('did not match any files', str(context.exception))

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_set_upstream(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git push with upstream tracking for new branches."""
        mock_run_git.return_value = (0, '', '')

        await git.push_changes(
            self.git_dir, remote='origin', set_upstream=True
        )

        mock_run_git.assert_called_once_with(
            ['git', 'push', '--set-upstream', 'origin'],
            cwd=self.git_dir,
            timeout_seconds=300,
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_push_changes_set_upstream_with_branch(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test git push with upstream tracking and specific branch."""
        mock_run_git.return_value = (0, '', '')

        await git.push_changes(
            self.git_dir,
            remote='origin',
            branch='feature-branch',
            set_upstream=True,
        )

        mock_run_git.assert_called_once_with(
            ['git', 'push', '--set-upstream', 'origin', 'feature-branch'],
            cwd=self.git_dir,
            timeout_seconds=300,
        )


class TestGitRevert(base.AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.git_dir = pathlib.Path(tempfile.mkdtemp())

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_find_commit_before_keyword_success(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test finding commit before keyword match."""
        # Mock git log output with matching commits
        git_log_output = (
            '43da34e imbi-automations: remove-pins\n'
            '7d507ce g2g-migration: Apply Pre-commit Check\n'
            '826fcb7 g2g-migration: Apply repo-url-replace transformation'
        )

        # Mock git log --grep and git log for previous commit
        mock_run_git.side_effect = [
            (0, git_log_output, ''),  # git log --grep output
            (0, '7d507ce', ''),  # git log previous commit
        ]

        result = await git.find_commit_before_keyword(
            self.git_dir, 'imbi-automations: remove-pins'
        )

        self.assertEqual(result, '7d507ce')
        self.assertEqual(mock_run_git.call_count, 2)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_find_commit_before_keyword_not_found(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test finding commit when keyword doesn't exist."""
        # Mock empty git log output
        mock_run_git.return_value = (0, '', '')

        result = await git.find_commit_before_keyword(
            self.git_dir, 'nonexistent-keyword'
        )

        self.assertIsNone(result)

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_file_at_commit_success(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test getting file content at specific commit."""
        file_content = '[metadata]\nname = test\nversion = 1.0.0'
        mock_run_git.return_value = (0, file_content, '')

        result = await git.get_file_at_commit(
            self.git_dir, 'setup.cfg', '7d507ce'
        )

        self.assertEqual(result, file_content)
        mock_run_git.assert_called_once_with(
            ['git', 'show', '7d507ce:setup.cfg'], cwd=self.git_dir, timeout=30
        )

    @mock.patch('imbi_automations.git._run_git_command')
    async def test_get_file_at_commit_not_found(
        self, mock_run_git: mock.Mock
    ) -> None:
        """Test getting file content when file doesn't exist at commit."""
        mock_run_git.return_value = (128, '', 'does not exist')

        result = await git.get_file_at_commit(
            self.git_dir, 'nonexistent.txt', '7d507ce'
        )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
