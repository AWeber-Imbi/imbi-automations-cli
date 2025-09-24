import pathlib
import tempfile
import unittest
from unittest import mock

from imbi_automations import docker
from tests.base import AsyncTestCase


class TestDockerOperations(AsyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = pathlib.Path(tempfile.mkdtemp())

    def test_extract_docker_image_from_dockerfile_success(self) -> None:
        """Test extracting Docker image from Dockerfile."""
        dockerfile_content = """
FROM python3-service:3.12.10-5

COPY . /app
WORKDIR /app
"""
        dockerfile_path = self.temp_dir / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        import asyncio

        image_name = asyncio.run(
            docker.extract_docker_image_from_dockerfile(dockerfile_path)
        )

        self.assertEqual(image_name, 'python3-service:3.12.10-5')

    def test_extract_docker_image_from_dockerfile_not_found(self) -> None:
        """Test extracting Docker image when no FROM line exists."""
        dockerfile_content = """
# This is a Dockerfile without FROM
COPY . /app
"""
        dockerfile_path = self.temp_dir / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        import asyncio

        image_name = asyncio.run(
            docker.extract_docker_image_from_dockerfile(dockerfile_path)
        )

        self.assertIsNone(image_name)

    def test_extract_docker_image_from_dockerfile_missing_file(self) -> None:
        """Test extracting Docker image when Dockerfile doesn't exist."""
        nonexistent_path = self.temp_dir / 'nonexistent-Dockerfile'

        import asyncio

        image_name = asyncio.run(
            docker.extract_docker_image_from_dockerfile(nonexistent_path)
        )

        self.assertIsNone(image_name)

    @mock.patch('subprocess.run')
    async def test_extract_file_from_docker_image_success(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test successful file extraction from Docker image."""
        constraints_content = 'requests==2.28.1\npydantic==1.10.0\n'

        # Mock successful subprocess result
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = constraints_content
        mock_result.stderr = ''
        mock_subprocess.return_value = mock_result

        result = await docker.extract_file_from_docker_image(
            'python3-service:3.12.10-5',
            '/tmp/constraints.txt',  # noqa: S108
        )

        self.assertEqual(result, constraints_content)
        mock_subprocess.assert_called_once_with(
            [
                'docker',
                'run',
                '--rm',
                '--entrypoint=cat',
                'python3-service:3.12.10-5',
                '/tmp/constraints.txt',  # noqa: S108
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    @mock.patch('subprocess.run')
    async def test_extract_file_from_docker_image_file_not_found(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test file extraction when file doesn't exist in image."""
        # Mock file not found result
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = (
            'cat: /tmp/nonexistent.txt: No such file or directory'
        )
        mock_subprocess.return_value = mock_result

        result = await docker.extract_file_from_docker_image(
            'python3-service:3.12.10-5',
            '/tmp/nonexistent.txt',  # noqa: S108
        )

        self.assertIsNone(result)

    @mock.patch('subprocess.run')
    async def test_extract_file_from_docker_image_docker_error(
        self, mock_subprocess: mock.Mock
    ) -> None:
        """Test file extraction when Docker command fails."""
        # Mock Docker error result
        mock_result = mock.Mock()
        mock_result.returncode = 125
        mock_result.stdout = ''
        mock_result.stderr = 'Unable to find image'
        mock_subprocess.return_value = mock_result

        with self.assertRaises(RuntimeError) as cm:
            await docker.extract_file_from_docker_image(
                'nonexistent-image:latest',
                '/tmp/file.txt',  # noqa: S108
            )

        self.assertIn('Docker extraction failed', str(cm.exception))

    def test_parse_constraints_file_success(self) -> None:
        """Test parsing constraints file content."""
        constraints_content = """
# This is a constraints file
requests==2.28.1
pydantic>=1.10.0,<2.0.0
httpx[http2]==0.24.1

# Comment line
urllib3==1.26.12
# Another comment
"""
        packages = docker.parse_constraints_file(constraints_content)

        expected_packages = ['requests', 'pydantic', 'httpx', 'urllib3']
        self.assertEqual(packages, expected_packages)

    def test_parse_constraints_file_empty(self) -> None:
        """Test parsing empty or comment-only constraints file."""
        constraints_content = """
# Only comments here
# No actual packages
"""
        packages = docker.parse_constraints_file(constraints_content)

        self.assertEqual(packages, [])


if __name__ == '__main__':
    unittest.main()
