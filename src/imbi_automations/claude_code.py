"""Claude Code integration for workflow actions."""

import json
import logging
import pathlib
import typing

import claude_code_sdk
import jinja2

from imbi_automations import models

LOGGER = logging.getLogger(__name__)


class ClaudeCode:
    """Claude Code client for executing AI-powered code transformations."""

    def __init__(
        self,
        config: models.ClaudeCodeConfiguration,
        working_directory: pathlib.Path,
        workflow_directory: pathlib.Path | None = None,
    ) -> None:
        """Initialize Claude Code client.

        Args:
            config: Claude Code configuration
            working_directory: Repository working directory for execution

        """
        self.config = config
        self.working_directory = working_directory
        self.workflow_directory = workflow_directory
        self.logger = LOGGER  # Default logger

    def _set_workflow_logger(self, context: models.WorkflowContext) -> None:
        """Set logger name to workflow directory name from context."""
        if context.workflow:
            workflow_dir_name = context.workflow.path.name
            self.logger = logging.getLogger(workflow_dir_name)

    def _create_context_message(self, context: models.WorkflowContext) -> str:
        """Create structured context message with project data."""
        return f"""# Project Context Data

Here is the complete structured context for this workflow execution:

```json
{context.model_dump_json(indent=2, exclude={'actions'})}
```

You can reference any field from this context data structure in your
analysis and actions."""

    def setup_agents_for_action(
        self, action: models.WorkflowAction, context: models.WorkflowContext
    ) -> pathlib.Path:
        """Setup dynamic agents and settings for claude-agents action.

        Args:
            action: Claude agents action configuration
            context: Workflow template context

        Returns:
            Path to generated settings.json file
        """
        # Set workflow-specific logger
        self._set_workflow_logger(context)

        # Create .claude directory structure
        claude_dir = self.working_directory.parent / '.claude'
        agents_dir = claude_dir / 'agents'
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Create generator agent file
        if action.prompt:
            generator_content = self._create_agent_file(
                action.prompt,
                'generator',
                'Generates and modifies files according to specifications',
                ['Read', 'Write', 'Edit', 'Bash'],
                context,
            )
            generator_file = agents_dir / 'generator.md'
            generator_file.write_text(generator_content, encoding='utf-8')

        # Create validator agent file
        if action.validation_prompt:
            validator_content = self._create_agent_file(
                action.validation_prompt,
                'validator',
                'Validates generated content and provides feedback',
                ['Read', 'Bash'],
                context,
            )
            validator_file = agents_dir / 'validator.md'
            validator_file.write_text(validator_content, encoding='utf-8')

        # Create custom settings.json
        settings = {
            'agentsPath': str(agents_dir),
            'mcpServers': {},
            'toolsConfig': {'allowedTools': ['Read', 'Write', 'Edit', 'Bash']},
        }

        settings_file = claude_dir / 'settings.json'
        settings_file.write_text(
            json.dumps(settings, indent=2), encoding='utf-8'
        )

        self.logger.debug('Created Claude agents setup at %s', claude_dir)
        return settings_file

    def _create_agent_file(
        self,
        prompt_file: str,
        agent_name: str,
        description: str,
        tools: list[str],
        context: models.WorkflowContext,
    ) -> str:
        """Create agent file with YAML frontmatter and rendered prompt."""
        # Get the prompt file path from workflow directory
        if not self.workflow_directory:
            raise RuntimeError(
                'Workflow directory required for agent creation'
            )

        prompt_file_path = self.workflow_directory / prompt_file
        if not prompt_file_path.exists():
            raise FileNotFoundError(
                f'Agent prompt file not found: {prompt_file_path}'
            )

        # Read and render prompt content if it's a Jinja2 template
        if prompt_file_path.suffix == '.j2':
            template_content = prompt_file_path.read_text(encoding='utf-8')
            jinja_env = jinja2.Environment(
                autoescape=True,
                variable_start_string='{{',
                variable_end_string='}}',
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = jinja_env.from_string(template_content)
            prompt_content = template.render(context.model_dump())
        else:
            prompt_content = prompt_file_path.read_text(encoding='utf-8')

        # For validator agents, prepend base validator behavior
        if agent_name == 'validator':
            base_validator_path = (
                pathlib.Path(__file__).parent / 'prompts' / 'base_validator.md'
            )
            if base_validator_path.exists():
                try:
                    base_validator_content = base_validator_path.read_text(
                        encoding='utf-8'
                    )
                    prompt_content = (
                        base_validator_content + '\n\n' + prompt_content
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    self.logger.warning(
                        'Failed to read base validator prompt: %s', exc
                    )

        # Create agent file with YAML frontmatter
        agent_content = f"""---
name: {agent_name}
description: {description}
tools: {', '.join(tools)}
---

{prompt_content}
"""
        return agent_content

    def _render_prompt_for_agents(
        self, prompt_file: str, context: models.WorkflowContext
    ) -> str:
        """Render prompt template for agent execution."""
        if not self.workflow_directory:
            raise RuntimeError(
                'Workflow directory required for prompt rendering'
            )

        prompt_file_path = self.workflow_directory / prompt_file
        if not prompt_file_path.exists():
            raise FileNotFoundError(
                f'Prompt file not found: {prompt_file_path}'
            )

        # Read and render prompt content if it's a Jinja2 template
        if prompt_file_path.suffix == '.j2':
            template_content = prompt_file_path.read_text(encoding='utf-8')
            jinja_env = jinja2.Environment(
                autoescape=True,
                variable_start_string='{{',
                variable_end_string='}}',
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = jinja_env.from_string(template_content)
            prompt_content = template.render(context.model_dump())
        else:
            prompt_content = prompt_file_path.read_text(encoding='utf-8')

        # Note: Base validator behavior is already included in the agent file
        # created by _create_agent_file, so we don't need to add it here again

        return prompt_content

    async def execute_agents(
        self, action: models.WorkflowAction, context: models.WorkflowContext
    ) -> dict[str, typing.Any]:
        """Execute claude-agents action using Task API with proper
        agent isolation.

        Args:
            action: Claude agents action configuration
            context: Workflow template context

        Returns:
            Dictionary with execution results including agent outputs
            and metrics
        """
        settings_file = self.setup_agents_for_action(action, context)

        # Configure SDK with custom settings
        options = claude_code_sdk.ClaudeCodeOptions(
            settings=str(settings_file),  # Use our custom settings
            cwd=self.working_directory,
            allowed_tools=['Read', 'Write', 'Bash', 'Edit'],
            permission_mode='bypassPermissions',
            add_dirs=[
                self.working_directory.parent / 'workflow',
                self.working_directory.parent / 'extracted',
            ],
        )

        result = {
            'action': action.name,
            'status': 'success',
            'cycles': 0,
            'generator_results': [],
            'validator_results': [],
            'total_cost': 0.0,
            'total_duration': 0,
        }

        try:
            for cycle in range(1, action.max_cycles + 1):
                self.logger.info(
                    'Agent cycle %d/%d for action %s',
                    cycle,
                    action.max_cycles,
                    action.name,
                )

                result['cycles'] = cycle

                # Run generator agent with rendered prompt
                generator_prompt_content = self._render_prompt_for_agents(
                    action.prompt, context, 'generator'
                )

                if cycle > 1 and context.previous_failure:
                    generator_prompt_content += (
                        f'\n\nPrevious validation feedback:\n'
                        f'{context.previous_failure}'
                    )

                # Debug log the generator prompt content
                self.logger.debug(
                    'Invoking generator agent for %s cycle %d:\n%s',
                    action.name,
                    cycle,
                    generator_prompt_content[:500] + '...'
                    if len(generator_prompt_content) > 500
                    else generator_prompt_content,
                )

                # Create separate client session for generator
                async with claude_code_sdk.ClaudeSDKClient(
                    options=options
                ) as generator_client:
                    # First, inject structured context data
                    context_message = self._create_context_message(context)
                    await generator_client.query(context_message)

                    # Then invoke the generator agent with the rendered prompt
                    await generator_client.query(
                        f'/agent generator\n\n{generator_prompt_content}'
                    )

                    # Collect generator response - use only last message
                    response_messages = []
                    async for message in generator_client.receive_response():
                        response_messages.append(message)

                    # Get the last message's result (the final response)
                    final_response = ''
                    if response_messages:
                        message_result = response_messages[-1].result
                        final_response = (
                            message_result
                            if message_result is not None
                            else ''
                        )

                    generator_task_result = {
                        'result': final_response,
                        'status': 'success',
                    }

                    # Debug log the full generator output
                    self.logger.debug(
                        'Generator output for %s cycle %d:\n%s',
                        action.name,
                        cycle,
                        generator_task_result['result'],
                    )

                    result['generator_results'].append(generator_task_result)
                    result['total_cost'] += generator_task_result.get(
                        'total_cost_usd', 0
                    )
                    result['total_duration'] += generator_task_result.get(
                        'duration_ms', 0
                    )

                    # Run validator agent with rendered prompt
                    validator_prompt_content = self._render_prompt_for_agents(
                        action.validation_prompt, context, 'validator'
                    )

                    # Debug log the validator prompt content
                    self.logger.debug(
                        'Invoking validator agent for %s cycle %d:\n%s',
                        action.name,
                        cycle,
                        validator_prompt_content[:500] + '...'
                        if len(validator_prompt_content) > 500
                        else validator_prompt_content,
                    )

                    # Create separate validator client session
                    async with claude_code_sdk.ClaudeSDKClient(
                        options=options
                    ) as validator_client:
                        # First, inject structured context data
                        context_message = self._create_context_message(context)
                        await validator_client.query(context_message)

                        # Then invoke the validator agent
                        await validator_client.query(
                            f'/agent validator\n\n{validator_prompt_content}'
                        )

                        # Collect validator response for JSON parsing
                        response_messages = []

                        async for (
                            message
                        ) in validator_client.receive_response():
                            response_messages.append(message)

                        # Get final response for JSON parsing
                        final_response = ''
                        if response_messages:
                            message_result = response_messages[-1].result
                            final_response = (
                                message_result
                                if message_result is not None
                                else ''
                            )

                        validator_task_result = {
                            'result': final_response,
                            'status': 'success',
                        }

                        result['validator_results'].append(
                            validator_task_result
                        )
                        result['total_cost'] += validator_task_result.get(
                            'total_cost_usd', 0
                        )
                        result['total_duration'] += validator_task_result.get(
                            'duration_ms', 0
                        )

                        # Check validator result for JSON parsing
                    validator_output = validator_task_result.get('result', '')

                    # Debug log the validator output
                    self.logger.debug(
                        'Validator output for %s cycle %d:\n%s',
                        action.name,
                        cycle,
                        validator_output,
                    )

                    # Parse JSON validation result - no fallback
                    validator_output = validator_task_result.get('result', '')

                    try:
                        # Extract JSON from response (handle markdown)
                        json_text = validator_output.strip()
                        if '```json' in json_text:
                            # Extract from markdown code block
                            start = json_text.find('```json') + 7
                            end = json_text.find('```', start)
                            json_text = json_text[start:end].strip()
                        elif json_text.startswith(
                            '```'
                        ) and json_text.endswith('```'):
                            # Remove plain code block markers
                            json_text = json_text[3:-3].strip()

                        validation_result = json.loads(json_text)
                        validation_status = validation_result.get(
                            'validation_status'
                        )
                        validation_errors = validation_result.get('errors', [])

                        self.logger.info(
                            'Validator JSON result for %s cycle %d: %s',
                            action.name,
                            cycle,
                            validation_status,
                        )

                        if validation_status == 'VALIDATION_PASSED':
                            self.logger.debug(
                                'Agent validation passed for %s in cycle %d',
                                action.name,
                                cycle,
                            )
                            result['status'] = 'success'
                            return result
                        elif validation_status == 'VALIDATION_FAILED':
                            error_details = '; '.join(validation_errors)
                            self.logger.warning(
                                'Validation failed for %s cycle %d: %s',
                                action.name,
                                cycle,
                                error_details,
                            )
                            if cycle < action.max_cycles:
                                context.previous_failure = error_details
                                continue
                            else:
                                result['status'] = 'failed'
                                result['final_failure'] = error_details
                                raise RuntimeError(
                                    f'Validation failed after '
                                    f'{action.max_cycles} cycles'
                                )
                        else:
                            # Invalid validation status
                            raise ValueError(
                                f'Invalid validation_status: '
                                f'{validation_status}'
                            )

                    except (json.JSONDecodeError, KeyError, ValueError) as exc:
                        # JSON parsing failed - this is a configuration error
                        self.logger.error(
                            'Validator invalid JSON for %s cycle %d. '
                            'Parse error: %s. Validator output: %s',
                            action.name,
                            cycle,
                            exc,
                            validator_output[:300],
                        )

                        # Configuration error, not validation failure
                        result['status'] = 'failed'
                        result['error'] = (
                            f'Validator provided invalid JSON: {exc}'
                        )
                        raise RuntimeError(
                            'Validator failed to provide valid JSON response'
                        ) from exc

        except claude_code_sdk.ClaudeSDKError as exc:
            result['status'] = 'failed'
            result['error'] = str(exc)
            raise

        return result
