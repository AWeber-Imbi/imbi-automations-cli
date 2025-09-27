"""Comprehensive tests for the claude module."""

import json
import pathlib
import tempfile
import typing
import unittest
from unittest import mock

import claude_code_sdk
import pydantic

from imbi_automations import claude, models
from tests import base


def _test_response_validator(message: str) -> str:
    """Test helper function that replicates response_validator logic."""
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return 'Payload not validate as JSON'
    try:
        models.AgentRun.model_validate(payload)
    except pydantic.ValidationError as exc:
        return str(exc)
    return 'Response is valid'


class ResponseValidatorTestCase(unittest.TestCase):
    """Test cases for the response_validator function logic."""

    def test_response_validator_valid_json(self) -> None:
        """Test response_validator with valid JSON."""
        valid_payload = {
            'result': 'success',
            'message': 'Test successful',
            'errors': [],
        }
        json_message = json.dumps(valid_payload)

        result = _test_response_validator(json_message)

        self.assertEqual(result, 'Response is valid')

    def test_response_validator_invalid_json(self) -> None:
        """Test response_validator with invalid JSON."""
        invalid_json = '{"invalid": json syntax'

        result = _test_response_validator(invalid_json)

        self.assertEqual(result, 'Payload not validate as JSON')

    def test_response_validator_invalid_schema(self) -> None:
        """Test response_validator with invalid AgentRun schema."""
        invalid_payload = {'wrong_field': 'invalid', 'missing_result': True}
        json_message = json.dumps(invalid_payload)

        result = _test_response_validator(json_message)

        self.assertIn('validation error', result)


class ClaudeTestCase(base.AsyncTestCase):
    """Test cases for the Claude class."""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.working_directory = pathlib.Path(self.temp_dir.name)
        self.config = models.ClaudeCodeConfiguration(executable='claude')

        # Create required directory structure
        (self.working_directory / 'workflow').mkdir()
        (self.working_directory / 'extracted').mkdir()
        (self.working_directory / 'repository').mkdir()

        # Create mock workflow and context
        self.workflow = models.Workflow(
            path=pathlib.Path('/mock/workflow'),
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

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    def test_claude_init(
        self,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test Claude initialization."""
        mock_server = mock.MagicMock()
        mock_create_server.return_value = mock_server
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
            verbose=True,
        )

        # Verify initialization
        self.assertEqual(claude_instance.config, self.config)
        self.assertEqual(
            claude_instance.working_directory, self.working_directory
        )
        self.assertTrue(claude_instance.verbose)
        self.assertIsNone(claude_instance.session_id)

        # Verify client creation was called
        mock_client_class.assert_called_once()
        mock_create_server.assert_called_once()

    def test_get_prompt_generator_with_jinja2(self) -> None:
        """Test _get_prompt method for generator with Jinja2 template."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        action = models.WorkflowClaudeAction(
            name='test-action', type='claude', prompt='test-prompt.j2'
        )

        # Create Jinja2 template file
        template_content = 'Hello {{ imbi_project.name }}!'
        (self.working_directory / 'workflow' / 'test-prompt.j2').write_text(
            template_content
        )

        with mock.patch(
            'imbi_automations.prompts.render',
            return_value='Hello test-project!',
        ) as mock_render:
            prompt = claude_instance._get_prompt(
                self.context, action, claude.AgentType.generator
            )

        self.assertIn('/generator', prompt)
        self.assertIn('Hello test-project!', prompt)
        self.assertIn('# Context Data:', prompt)
        mock_render.assert_called_once()

    def test_get_prompt_validator_with_plain_text(self) -> None:
        """Test _get_prompt method for validator with plain text."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
        )

        # Create plain text prompt file
        validation_content = 'Validate the generated code'
        (
            self.working_directory / 'workflow' / 'test-validation.md'
        ).write_text(validation_content)

        prompt = claude_instance._get_prompt(
            self.context, action, claude.AgentType.validator
        )

        self.assertIn('/validator', prompt)
        self.assertIn('Validate the generated code', prompt)
        self.assertIn('# Context Data:', prompt)

    def test_parse_message_result_message_success(self) -> None:
        """Test _parse_message with successful ResultMessage."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Test with plain JSON
        valid_result = {'result': 'success', 'message': 'Operation completed'}

        # Create mock ResultMessage
        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'test-session'
        message.result = json.dumps(valid_result)
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.success)
        self.assertEqual(result.message, 'Operation completed')
        self.assertEqual(claude_instance.session_id, 'test-session')

    def test_parse_message_result_message_with_json_code_blocks(self) -> None:
        """Test _parse_message with JSON code blocks."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        valid_result = {'result': 'success', 'message': 'Operation completed'}

        # Test with ```json wrapper
        json_with_wrapper = f'```json\n{json.dumps(valid_result)}\n```'

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'test-session'
        message.result = json_with_wrapper
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.success)
        self.assertEqual(result.message, 'Operation completed')

    def test_parse_message_result_message_error(self) -> None:
        """Test _parse_message with error ResultMessage."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'test-session'
        message.result = 'Error occurred'
        message.is_error = True

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.failure)
        self.assertEqual(result.message, 'Claude Error')
        self.assertEqual(result.errors, ['Error occurred'])

    def test_parse_message_result_message_invalid_json(self) -> None:
        """Test _parse_message with ResultMessage containing invalid JSON."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'test-session'
        message.result = '{"invalid": json syntax'
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.failure)
        self.assertEqual(result.message, 'Agent Contract Failure')
        self.assertTrue(
            any(
                'Failed to parse JSON result' in error
                for error in result.errors
            )
        )

    def test_parse_message_assistant_message(self) -> None:
        """Test _parse_message with AssistantMessage."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        message = mock.MagicMock(spec=claude_code_sdk.AssistantMessage)
        message.content = [mock.MagicMock(spec=claude_code_sdk.TextBlock)]

        with mock.patch.object(claude_instance, '_log_message') as mock_log:
            result = claude_instance._parse_message(message)

        self.assertIsNone(result)
        mock_log.assert_called_once_with('Claude Assistant', message.content)

    def test_parse_message_system_message(self) -> None:
        """Test _parse_message with SystemMessage."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        message = mock.MagicMock(spec=claude_code_sdk.SystemMessage)
        message.data = 'System message'

        result = claude_instance._parse_message(message)

        self.assertIsNone(result)

    def test_parse_message_user_message(self) -> None:
        """Test _parse_message with UserMessage."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        message = mock.MagicMock(spec=claude_code_sdk.UserMessage)
        message.content = [mock.MagicMock(spec=claude_code_sdk.TextBlock)]

        with mock.patch.object(claude_instance, '_log_message') as mock_log:
            result = claude_instance._parse_message(message)

        self.assertIsNone(result)
        mock_log.assert_called_once_with('Claude User', message.content)

    def test_log_message_with_text_list(self) -> None:
        """Test _log_message method with list of text blocks."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        text_block1 = mock.MagicMock(spec=claude_code_sdk.TextBlock)
        text_block1.text = 'First message'
        text_block2 = mock.MagicMock(spec=claude_code_sdk.TextBlock)
        text_block2.text = 'Second message'
        tool_block = mock.MagicMock(spec=claude_code_sdk.ToolUseBlock)

        content = [text_block1, text_block2, tool_block]

        with mock.patch.object(claude_instance.logger, 'debug') as mock_debug:
            claude_instance._log_message('Test Type', content)

        # Verify only text blocks were logged
        self.assertEqual(mock_debug.call_count, 2)
        mock_debug.assert_has_calls(
            [
                mock.call('%s: %s', 'Test Type', 'First message'),
                mock.call('%s: %s', 'Test Type', 'Second message'),
            ]
        )

    def test_log_message_with_string(self) -> None:
        """Test _log_message method with string content."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        with mock.patch.object(claude_instance.logger, 'debug') as mock_debug:
            claude_instance._log_message('Test Type', 'Simple string message')

        mock_debug.assert_called_once_with(
            '%s: %s', 'Test Type', 'Simple string message'
        )

    def test_log_message_with_unknown_block_type(self) -> None:
        """Test _log_message method with unknown block type."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Create a mock unknown block type
        unknown_block = mock.MagicMock()
        unknown_block.__class__.__name__ = 'UnknownBlock'
        content = [unknown_block]

        with self.assertRaises(RuntimeError) as exc_context:
            claude_instance._log_message('Test Type', content)

        self.assertIn('Unknown message type', str(exc_context.exception))

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_full_cycle_success(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test execute method with successful cycle."""
        # Setup mocks
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.connect = mock.AsyncMock()
        mock_client_instance.disconnect = mock.AsyncMock()

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
            verbose=True,
        )

        # Create test action
        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
            max_cycles=2,
        )

        # Create mock prompt files
        (self.working_directory / 'workflow' / 'test-prompt.md').write_text(
            'Generator prompt'
        )
        (
            self.working_directory / 'workflow' / 'test-validation.md'
        ).write_text('Validator prompt')

        # Mock successful cycle execution
        with mock.patch.object(
            claude_instance, '_execute_cycle', return_value=True
        ) as mock_cycle:
            await claude_instance.execute(self.context, action)

        # Verify client lifecycle
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()

        # Verify cycle execution
        mock_cycle.assert_called_once_with(self.context, action, 1)

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_multiple_cycles(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test execute method with multiple cycles."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.connect = mock.AsyncMock()
        mock_client_instance.disconnect = mock.AsyncMock()

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
            max_cycles=3,
        )

        (self.working_directory / 'workflow' / 'test-prompt.md').write_text(
            'Generator prompt'
        )
        (
            self.working_directory / 'workflow' / 'test-validation.md'
        ).write_text('Validator prompt')

        # Mock cycle execution - fail first two, succeed on third
        cycle_results = [False, False, True]
        with mock.patch.object(
            claude_instance, '_execute_cycle', side_effect=cycle_results
        ) as mock_cycle:
            await claude_instance.execute(self.context, action)

        # Verify all cycles were attempted
        self.assertEqual(mock_cycle.call_count, 3)
        mock_cycle.assert_has_calls(
            [
                mock.call(self.context, action, 1),
                mock.call(self.context, action, 2),
                mock.call(self.context, action, 3),
            ]
        )

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_cycle_success(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test _execute_cycle method with successful execution."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
        )

        # Mock successful agent executions
        success_run = models.AgentRun(
            result=models.AgentRunResult.success, message='Success'
        )

        with mock.patch.object(
            claude_instance, '_execute_agent', return_value=success_run
        ) as mock_agent:
            result = await claude_instance._execute_cycle(
                self.context, action, 1
            )

        self.assertTrue(result)

        # Verify both agents were executed
        self.assertEqual(mock_agent.call_count, 2)
        mock_agent.assert_has_calls(
            [
                mock.call(self.context, action, claude.AgentType.generator),
                mock.call(self.context, action, claude.AgentType.validator),
            ]
        )

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_cycle_generator_failure(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test _execute_cycle method with generator failure."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
        )

        # Mock generator failure
        failure_run = models.AgentRun(
            result=models.AgentRunResult.failure, message='Generator failed'
        )

        with mock.patch.object(
            claude_instance, '_execute_agent', return_value=failure_run
        ) as mock_agent:
            result = await claude_instance._execute_cycle(
                self.context, action, 1
            )

        self.assertFalse(result)

        # Verify only generator was executed
        # (validator should not run after generator failure)
        mock_agent.assert_called_once_with(
            self.context, action, claude.AgentType.generator
        )

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_cycle_validator_failure(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test _execute_cycle method with validator failure."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
        )

        # Mock generator success, validator failure
        success_run = models.AgentRun(
            result=models.AgentRunResult.success, message='Success'
        )
        failure_run = models.AgentRun(
            result=models.AgentRunResult.failure, message='Validation failed'
        )

        with mock.patch.object(
            claude_instance,
            '_execute_agent',
            side_effect=[success_run, failure_run],
        ) as mock_agent:
            result = await claude_instance._execute_cycle(
                self.context, action, 1
            )

        self.assertFalse(result)

        # Verify both agents were executed
        self.assertEqual(mock_agent.call_count, 2)

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_agent_with_response_parsing(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test _execute_agent method with full response parsing flow."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.query = mock.AsyncMock()

        # Mock response flow with different message types
        async def mock_receive() -> typing.AsyncGenerator[
            mock.MagicMock, None
        ]:
            # First yield system message (should be ignored)
            system_msg = mock.MagicMock(spec=claude_code_sdk.SystemMessage)
            system_msg.data = 'System initialization'
            yield system_msg

            # Then yield assistant message (should be logged but ignored)
            assistant_msg = mock.MagicMock(
                spec=claude_code_sdk.AssistantMessage
            )
            assistant_msg.content = []
            yield assistant_msg

            # Finally yield successful result
            success_result = {
                'result': 'success',
                'message': 'Agent completed successfully',
            }
            result_msg = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
            result_msg.session_id = 'new-session'
            result_msg.result = json.dumps(success_result)
            result_msg.is_error = False
            yield result_msg

        mock_client_instance.receive_response.return_value = mock_receive()

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action', type='claude', prompt='test-prompt.md'
        )

        (self.working_directory / 'workflow' / 'test-prompt.md').write_text(
            'Test prompt content'
        )

        result = await claude_instance._execute_agent(
            self.context, action, claude.AgentType.generator
        )

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.success)
        self.assertEqual(result.message, 'Agent completed successfully')
        self.assertEqual(claude_instance.session_id, 'new-session')

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_agent_no_valid_response(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test _execute_agent method with no valid response."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.query = mock.AsyncMock()

        async def mock_receive() -> typing.AsyncGenerator[
            mock.MagicMock, None
        ]:
            # Yield messages that don't parse to valid AgentRun
            system_msg = mock.MagicMock(spec=claude_code_sdk.SystemMessage)
            system_msg.data = 'System message'
            yield system_msg

            assistant_msg = mock.MagicMock(
                spec=claude_code_sdk.AssistantMessage
            )
            assistant_msg.content = []
            yield assistant_msg

        mock_client_instance.receive_response.return_value = mock_receive()

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action', type='claude', prompt='test-prompt.md'
        )

        (self.working_directory / 'workflow' / 'test-prompt.md').write_text(
            'Test prompt'
        )

        result = await claude_instance._execute_agent(
            self.context, action, claude.AgentType.generator
        )

        # Should return failure with unspecified failure message
        self.assertEqual(result.result, models.AgentRunResult.failure)
        self.assertEqual(result.message, 'Unspecified failure')
        self.assertEqual(result.errors, [])

    def test_parse_message_result_with_trailing_backticks_only(self) -> None:
        """Test _parse_message with only trailing backticks."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        valid_result = {'result': 'success', 'message': 'Operation completed'}

        # Test with only trailing backticks (no json prefix)
        json_with_backticks = f'{json.dumps(valid_result)}```'

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'test-session'
        message.result = json_with_backticks
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(result.result, models.AgentRunResult.success)
        self.assertEqual(result.message, 'Operation completed')

    def test_log_message_with_unsupported_content_block_type(self) -> None:
        """Test _log_message method with unsupported ContentBlock type."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Test with ContentBlock (should raise RuntimeError as
        # it's not supported)
        content_block = mock.MagicMock(spec=claude_code_sdk.ContentBlock)
        content = [content_block]

        with self.assertRaises(RuntimeError) as exc_context:
            claude_instance._log_message('Test Type', content)

        self.assertIn('Unknown message type', str(exc_context.exception))

    def test_log_message_with_tool_blocks_only(self) -> None:
        """Test _log_message method with only tool blocks."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Test with only tool blocks (should all be skipped)
        tool_use_block = mock.MagicMock(spec=claude_code_sdk.ToolUseBlock)
        tool_result_block = mock.MagicMock(
            spec=claude_code_sdk.ToolResultBlock
        )
        content = [tool_use_block, tool_result_block]

        with mock.patch.object(claude_instance.logger, 'debug') as mock_debug:
            claude_instance._log_message('Test Type', content)

        # Verify no logging occurred since all blocks were skipped
        mock_debug.assert_not_called()

    @mock.patch('claude_code_sdk.ClaudeSDKClient')
    @mock.patch('claude_code_sdk.create_sdk_mcp_server')
    @mock.patch(
        'builtins.open',
        new_callable=mock.mock_open,
        read_data='Mock system prompt',
    )
    @mock.patch('imbi_automations.utils.copy')
    async def test_execute_all_cycles_fail(
        self,
        mock_copy: mock.MagicMock,
        mock_file: mock.MagicMock,
        mock_create_server: mock.MagicMock,
        mock_client_class: mock.MagicMock,
    ) -> None:
        """Test execute method when all cycles fail."""
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.connect = mock.AsyncMock()
        mock_client_instance.disconnect = mock.AsyncMock()

        claude_instance = claude.Claude(
            config=self.config,
            working_directory=self.working_directory,
            commit_author='Test Author <test@example.com>',
        )

        action = models.WorkflowClaudeAction(
            name='test-action',
            type='claude',
            prompt='test-prompt.md',
            validation_prompt='test-validation.md',
            max_cycles=2,
        )

        (self.working_directory / 'workflow' / 'test-prompt.md').write_text(
            'Generator prompt'
        )
        (
            self.working_directory / 'workflow' / 'test-validation.md'
        ).write_text('Validator prompt')

        # Mock all cycles failing
        with mock.patch.object(
            claude_instance, '_execute_cycle', return_value=False
        ) as mock_cycle:
            await claude_instance.execute(self.context, action)

        # Verify all cycles were attempted
        self.assertEqual(mock_cycle.call_count, 2)
        mock_cycle.assert_has_calls(
            [
                mock.call(self.context, action, 1),
                mock.call(self.context, action, 2),
            ]
        )

        # Verify client lifecycle still completed
        mock_client_instance.connect.assert_called_once()
        mock_client_instance.disconnect.assert_called_once()

    def test_parse_message_with_session_id_update(self) -> None:
        """Test _parse_message updates session_id when different."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Set initial session_id
        claude_instance.session_id = 'old-session'

        valid_result = {'result': 'success', 'message': 'Session updated'}

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'new-session'
        message.result = json.dumps(valid_result)
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        self.assertEqual(claude_instance.session_id, 'new-session')

    def test_parse_message_with_same_session_id(self) -> None:
        """Test _parse_message doesn't update session_id when same."""
        with (
            mock.patch('claude_code_sdk.ClaudeSDKClient'),
            mock.patch('claude_code_sdk.create_sdk_mcp_server'),
            mock.patch(
                'builtins.open',
                new_callable=mock.mock_open,
                read_data='Mock system prompt',
            ),
        ):
            claude_instance = claude.Claude(
                config=self.config,
                working_directory=self.working_directory,
                commit_author='Test Author <test@example.com>',
            )

        # Set initial session_id
        claude_instance.session_id = 'same-session'

        valid_result = {'result': 'success', 'message': 'Same session'}

        message = mock.MagicMock(spec=claude_code_sdk.ResultMessage)
        message.session_id = 'same-session'
        message.result = json.dumps(valid_result)
        message.is_error = False

        result = claude_instance._parse_message(message)

        self.assertIsInstance(result, models.AgentRun)
        # Session ID should remain unchanged since it's the same
        self.assertEqual(claude_instance.session_id, 'same-session')


if __name__ == '__main__':
    unittest.main()
