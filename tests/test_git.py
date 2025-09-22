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
        mock_process = mock.AsyncMock()
        mock_process.terminate = mock.AsyncMock()
        mock_process.wait = mock.AsyncMock()
        mock_subprocess.return_value = mock_process

        # First wait_for call (communicate) times out
        mock_wait_for.side_effect = [TimeoutError(), None]

        result = await git._run_git_command(
            ['git', 'clone', 'large-repo'], self.git_dir, timeout=1
        )

        self.assertEqual(result, (-1, '', 'Command timed out after 1 seconds'))
        mock_process.terminate.assert_called_once()

    @mock.patch('asyncio.create_subprocess_exec')
    @mock.patch('asyncio.wait_for')
    async def test_run_git_command_timeout_force_kill(
        self, mock_wait_for: mock.Mock, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command timeout with force kill."""
        mock_process = mock.AsyncMock()
        mock_process.terminate = mock.AsyncMock()
        mock_process.kill = mock.AsyncMock()
        mock_process.wait = mock.AsyncMock()
        mock_subprocess.return_value = mock_process

        # First wait_for times out, second wait_for also times out (force kill)
        mock_wait_for.side_effect = [TimeoutError(), TimeoutError(), None]

        result = await git._run_git_command(
            ['git', 'clone', 'large-repo'], self.git_dir, timeout=1
        )

        self.assertEqual(result, (-1, '', 'Command timed out after 1 seconds'))
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    @mock.patch('asyncio.create_subprocess_exec')
    @mock.patch('asyncio.wait_for')
    async def test_run_git_command_custom_timeout(
        self, mock_wait_for: mock.Mock, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command with custom timeout value."""
        mock_process = mock.AsyncMock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        mock_wait_for.return_value = (b'output', b'')

        await git._run_git_command(['git', 'status'], self.git_dir, timeout=30)

        # Verify timeout was passed to wait_for
        mock_wait_for.assert_called_once_with(
            mock_process.communicate(), timeout=30
        )

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

    @mock.patch('asyncio.create_subprocess_exec')
    @mock.patch('asyncio.wait_for')
    async def test_run_git_command_default_timeout(
        self, mock_wait_for: mock.Mock, mock_subprocess: mock.Mock
    ) -> None:
        """Test git command uses default timeout."""
        mock_process = mock.AsyncMock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        mock_wait_for.return_value = (b'output', b'')

        await git._run_git_command(['git', 'status'], self.git_dir)

        # Verify default timeout of 3600 seconds
        mock_wait_for.assert_called_once_with(
            mock_process.communicate(), timeout=3600
        )

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


if __name__ == '__main__':
    unittest.main()
