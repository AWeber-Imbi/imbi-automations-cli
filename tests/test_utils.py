"""Tests for the utils module."""

import pathlib
import tempfile
import unittest

from imbi_automations import models, utils


class UtilsTestCase(unittest.TestCase):
    """Test cases for utils module functions."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)

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
            working_directory=self.temp_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_extract_image_from_dockerfile_simple(self) -> None:
        """Test extracting simple Docker image from Dockerfile."""
        dockerfile_content = """FROM python:3.12
RUN pip install requirements.txt
COPY . /app
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertEqual(result, 'python:3.12')

    def test_extract_image_from_dockerfile_with_tag(self) -> None:
        """Test extracting Docker image with tag."""
        dockerfile_content = """FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertEqual(result, 'ubuntu:20.04')

    def test_extract_image_from_dockerfile_multi_stage(self) -> None:
        """Test extracting Docker image from multi-stage build."""
        dockerfile_content = """FROM node:18 AS builder
WORKDIR /build
COPY package.json .

FROM nginx:alpine AS runtime
COPY --from=builder /build/dist /usr/share/nginx/html
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        # Should return the first FROM instruction
        self.assertEqual(result, 'node:18')

    def test_extract_image_from_dockerfile_with_comments(self) -> None:
        """Test extracting Docker image with inline comments."""
        dockerfile_content = """# Base image for Python application
FROM python:3.11-slim  # Using slim variant for smaller size
LABEL maintainer="test@example.com"
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertEqual(result, 'python:3.11-slim')

    def test_extract_image_from_dockerfile_case_insensitive(self) -> None:
        """Test extracting Docker image with different case."""
        dockerfile_content = """from alpine:latest
run apk add --no-cache python3
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertEqual(result, 'alpine:latest')

    def test_extract_image_from_dockerfile_with_registry(self) -> None:
        """Test extracting Docker image with custom registry."""
        dockerfile_content = """FROM registry.example.com/myorg/python:3.12
WORKDIR /app
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertEqual(result, 'registry.example.com/myorg/python:3.12')

    def test_extract_image_from_dockerfile_no_from_instruction(self) -> None:
        """Test extracting Docker image from file without FROM instruction."""
        dockerfile_content = """# This is not a valid Dockerfile
RUN echo "hello"
COPY . /app
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertIsNone(result)

    def test_extract_image_from_dockerfile_empty_file(self) -> None:
        """Test extracting Docker image from empty file."""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text('')

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertIsNone(result)

    def test_extract_image_from_dockerfile_comments_only(self) -> None:
        """Test extracting Docker image from file with only comments."""
        dockerfile_content = """# This is a comment
# FROM python:3.12 (commented out)
# Another comment
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertIsNone(result)

    def test_extract_image_from_dockerfile_file_not_found(self) -> None:
        """Test extracting Docker image from non-existent file."""
        nonexistent_path = self.temp_path / 'nonexistent'

        with self.assertRaises(OSError):
            utils.extract_docker_image(nonexistent_path)

    def test_extract_image_from_dockerfile_malformed_from(self) -> None:
        """Test extracting Docker image from malformed FROM instruction."""
        dockerfile_content = """FROM
RUN echo "hello"
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        self.assertIsNone(result)

    def test_extract_image_from_dockerfile_from_with_build_args(self) -> None:
        """Test extracting Docker image with build args in FROM."""
        dockerfile_content = """ARG BASE_IMAGE=python:3.12
FROM ${BASE_IMAGE}
WORKDIR /app
"""
        dockerfile_path = self.temp_path / 'Dockerfile'
        dockerfile_path.write_text(dockerfile_content)

        result = utils.extract_image_from_dockerfile(
            self.context, pathlib.Path('Dockerfile')
        )

        # Should extract the variable reference
        self.assertEqual(result, '${BASE_IMAGE}')


if __name__ == '__main__':
    unittest.main()
