import pathlib
import re
import unittest

from imbi_automations.models.workflow import (
    WorkflowCondition,
    WorkflowDockerAction,
    WorkflowDockerActionCommand,
    WorkflowFileAction,
    WorkflowFileActionCommand,
)


class ModelValidatorsTestCase(unittest.TestCase):
    def test_docker_build_requires_path(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowDockerAction(
                name='d',
                type='docker',
                command=WorkflowDockerActionCommand.build,
                image='x',
            )
        # valid when path is provided
        action = WorkflowDockerAction(
            name='d',
            type='docker',
            command=WorkflowDockerActionCommand.build,
            image='x',
            path=pathlib.Path('Dockerfile'),
        )
        # path is now a ResourceUrl, check string representation
        self.assertEqual(str(action.path), 'file:///Dockerfile')

    def test_docker_pull_forbids_path(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowDockerAction(
                name='d',
                type='docker',
                command=WorkflowDockerActionCommand.pull,
                image='x',
                path=pathlib.Path('.'),
            )

    def test_file_delete_requires_path_or_pattern(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowFileAction(
                name='f', type='file', command=WorkflowFileActionCommand.delete
            )
        # Valid with path
        WorkflowFileAction(
            name='f',
            type='file',
            command=WorkflowFileActionCommand.delete,
            path=pathlib.Path('foo'),
        )
        # Valid with pattern
        WorkflowFileAction(
            name='f',
            type='file',
            command=WorkflowFileActionCommand.delete,
            pattern=re.compile(r'.*'),
        )

    def test_file_append_requires_path_and_content(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowFileAction(
                name='f',
                type='file',
                command=WorkflowFileActionCommand.append,
                path=pathlib.Path('a'),
            )
        with self.assertRaises(ValueError):
            WorkflowFileAction(
                name='f',
                type='file',
                command=WorkflowFileActionCommand.append,
                content='x',
            )
        # valid
        WorkflowFileAction(
            name='f',
            type='file',
            command=WorkflowFileActionCommand.append,
            path=pathlib.Path('a'),
            content='x',
        )

    def test_condition_exactly_one(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowCondition()
        with self.assertRaises(ValueError):
            WorkflowCondition(file_exists='a', remote_file_exists='b')
        # valid: paired
        c = WorkflowCondition(file_contains='x', file=pathlib.Path('f'))
        self.assertIsNotNone(c)

    def test_condition_pairing_errors(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowCondition(file_contains='x')
        with self.assertRaises(ValueError):
            WorkflowCondition(file=pathlib.Path('f'))


if __name__ == '__main__':
    unittest.main()
