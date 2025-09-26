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
        self._cached_settings_file: pathlib.Path | None = (
            None  # Cache agent setup
        )

    def _set_workflow_logger(self, context: models.WorkflowContext) -> None:
        """Set logger name to workflow directory name from context."""
        if context.workflow:
            workflow_dir_name = context.workflow.path.name
            self.logger = logging.getLogger(workflow_dir_name)

    def _create_context_message(self, context: models.WorkflowContext) -> str:
        """Create structured context message with project data."""
        context_template_path = (
            pathlib.Path(__file__).parent / 'prompts' / 'context.md.j2'
        )

        if context_template_path.exists():
            template_content = context_template_path.read_text(
                encoding='utf-8'
            )
            jinja_env = jinja2.Environment(
                autoescape=True,
                variable_start_string='{{',
                variable_end_string='}}',
                trim_blocks=True,
                lstrip_blocks=True,
            )
            template = jinja_env.from_string(template_content)
            return template.render(
                context_json=context.model_dump_json(
                    indent=2, exclude={'actions'}
                )
            )
        else:
            # Fallback to inline template if file doesn't exist
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
        # Return cached settings if already created
        if self._cached_settings_file and self._cached_settings_file.exists():
            return self._cached_settings_file

        # Set workflow-specific logger
        self._set_workflow_logger(context)

        # Create .claude directory structure
        claude_dir = self.working_directory.parent / '.claude'
        agents_dir = claude_dir / 'agents'
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Create generator agent file
        if action.prompt:
            generator_content = self._create_agent_file(
                action.prompt, 'generator', context
            )
            generator_file = agents_dir / 'generator.md'
            generator_file.write_text(generator_content, encoding='utf-8')

        # Create validator agent file
        if action.validation_prompt:
            validator_content = self._create_agent_file(
                action.validation_prompt, 'validator', context
            )
            validator_file = agents_dir / 'validator.md'
            validator_file.write_text(validator_content, encoding='utf-8')

        # Create custom settings.json - disable all global settings
        settings = {
            'agentsPath': str(agents_dir),
            'mcpServers': {},
            'toolsConfig': {'allowedTools': ['Read', 'Write', 'Edit', 'Bash']},
            'hooks': {},  # Disable user hooks
            'outputStyle': 'plain',  # Disable custom output styles
            'settingSources': ['project', 'local'],  # Exclude user settings
        }

        settings_file = claude_dir / 'settings.json'
        settings_file.write_text(
            json.dumps(settings, indent=2), encoding='utf-8'
        )

        # Copy CLAUDE.md from prompts directory to override user settings
        claude_md_source = (
            pathlib.Path(__file__).parent / 'prompts' / 'CLAUDE.md'
        )
        claude_md_file = claude_dir / 'CLAUDE.md'

        if claude_md_source.exists():
            claude_md_content = claude_md_source.read_text(encoding='utf-8')
            claude_md_file.write_text(claude_md_content, encoding='utf-8')
        else:
            self.logger.warning('CLAUDE.md not found at %s', claude_md_source)

        self.logger.debug('Created Claude agents setup at %s', claude_dir)

        # Cache the settings file for reuse
        self._cached_settings_file = settings_file
        return settings_file

    def _create_agent_file(
        self,
        prompt_file: str,
        agent_name: str,
        context: models.WorkflowContext,
    ) -> str:
        """Create agent file content with base and workflow prompts."""
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

        # For generator agents, prepend base generator behavior
        if agent_name == 'generator':
            base_generator_path = (
                pathlib.Path(__file__).parent / 'prompts' / 'generator.md'
            )
            if base_generator_path.exists():
                try:
                    base_generator_content = base_generator_path.read_text(
                        encoding='utf-8'
                    )
                    prompt_content = (
                        base_generator_content + '\n\n' + prompt_content
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    self.logger.warning(
                        'Failed to read base generator prompt: %s', exc
                    )

        # For validator agents, prepend base validator behavior
        elif agent_name == 'validator':
            base_validator_path = (
                pathlib.Path(__file__).parent / 'prompts' / 'validator.md'
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

        # YAML frontmatter is now included in the base prompt files
        return prompt_content

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

    async def execute_agent(
        self,
        agent_type: str,
        prompt_file: str,
        context: models.WorkflowContext,
        options: claude_code_sdk.ClaudeCodeOptions,
    ) -> dict[str, typing.Any]:
        """Execute a single agent (generator or validator) and return results.

        Args:
            agent_type: 'generator' or 'validator'
            prompt_file: Path to the agent's prompt file
            context: Workflow context
            options: Claude Code SDK options

        Returns:
            Dictionary with agent execution results
        """
        # Render the agent-specific prompt
        agent_prompt_content = self._render_prompt_for_agents(
            prompt_file, context
        )

        # Add previous failure context for generator on retry cycles
        if agent_type == 'generator' and context.previous_failure:
            agent_prompt_content += (
                f'\n\nPrevious validation feedback:\n'
                f'{context.previous_failure}'
            )

        # Execute the agent
        command = f'/agent {agent_type}\n\n{agent_prompt_content}'
        self.logger.debug(
            'Sending to %s client:\n%s',
            agent_type,
            command[:500] + '...' if len(command) > 500 else command,
        )

        async with claude_code_sdk.ClaudeSDKClient(options=options) as client:
            # First, inject structured context data
            context_message = self._create_context_message(context)
            await client.query(context_message)

            # Then invoke the agent
            await client.query(command)

            # Stream response messages and log thinking process
            response_messages = []
            async for message in client.receive_response():
                response_messages.append(message)

                # Stream intermediate thinking/action as debug logs
                if message.result:
                    # Log streaming chunks with basic parsing for tool usage
                    chunk_preview = (
                        message.result[:200] + '...'
                        if len(message.result) > 200
                        else message.result
                    )

                    # Detect if this chunk contains tool usage
                    if any(
                        tool in message.result.lower()
                        for tool in [
                            '<function_calls>',
                            'read',
                            'write',
                            'edit',
                            'bash',
                        ]
                    ):
                        self.logger.debug(
                            '[%s action] %s', agent_type.title(), chunk_preview
                        )
                    else:
                        self.logger.debug(
                            '[%s thinking] %s',
                            agent_type.title(),
                            chunk_preview,
                        )

            # Get the final response
            final_response = ''
            if response_messages:
                message_result = response_messages[-1].result
                final_response = (
                    message_result if message_result is not None else ''
                )

            return {
                'result': final_response,
                'status': 'success',
                'agent_type': agent_type,
            }

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

        # Configure SDK with custom settings - isolate from user environment
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

        # Main execution cycle - only risky operations in try blocks
        for cycle in range(1, action.max_cycles + 1):
            self.logger.info(
                'Agent cycle %d/%d for action %s',
                cycle,
                action.max_cycles,
                action.name,
            )

            result['cycles'] = cycle

            # Execute generator agent - risky operation
            try:
                generator_result = await self.execute_agent(
                    'generator', action.prompt, context, options
                )
            except claude_code_sdk.ClaudeSDKError as exc:
                result['status'] = 'failed'
                result['error'] = str(exc)
                raise

            # Safe operations - logging and result processing
            self.logger.debug(
                'Generator output for %s cycle %d:\n%s',
                action.name,
                cycle,
                generator_result['result'],
            )

            result['generator_results'].append(generator_result)
            result['total_cost'] += generator_result.get('total_cost_usd', 0)
            result['total_duration'] += generator_result.get('duration_ms', 0)

            # Execute validator agent if validation prompt exists
            if action.validation_prompt:
                # Execute validator - risky operation
                try:
                    validator_result = await self.execute_agent(
                        'validator', action.validation_prompt, context, options
                    )
                except claude_code_sdk.ClaudeSDKError as exc:
                    result['status'] = 'failed'
                    result['error'] = str(exc)
                    raise

                # Safe operations - logging and result processing
                self.logger.debug(
                    'Validator output for %s cycle %d:\n%s',
                    action.name,
                    cycle,
                    validator_result['result'],
                )

                result['validator_results'].append(validator_result)
                result['total_cost'] += validator_result.get(
                    'total_cost_usd', 0
                )
                result['total_duration'] += validator_result.get(
                    'duration_ms', 0
                )

                # Parse and validate JSON response - risky operation
                validator_output = validator_result.get('result', '')

                try:
                    # Extract JSON from response (handle markdown)
                    json_text = validator_output.strip()
                    if '```json' in json_text:
                        # Extract from markdown code block
                        start = json_text.find('```json') + 7
                        end = json_text.find('```', start)
                        json_text = json_text[start:end].strip()
                    elif json_text.startswith('```') and json_text.endswith(
                        '```'
                    ):
                        # Remove plain code block markers
                        json_text = json_text[3:-3].strip()

                    validation_result = json.loads(json_text)
                    validation_status = validation_result.get(
                        'validation_status'
                    )
                    validation_errors = validation_result.get('errors', [])
                except (json.JSONDecodeError, KeyError) as exc:
                    # JSON parsing failed - this is a configuration error
                    self.logger.error(
                        'Validator invalid JSON for %s cycle %d. '
                        'Parse error: %s. Validator output: %s',
                        action.name,
                        cycle,
                        exc,
                        validator_output[:300],
                    )
                    result['status'] = 'failed'
                    result['error'] = f'Validator provided invalid JSON: {exc}'
                    raise RuntimeError(
                        'Validator failed to provide valid JSON response'
                    ) from exc

                # Safe operations - process validation result
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
                    result['status'] = 'failed'
                    result['error'] = (
                        f'Invalid validation_status: {validation_status}'
                    )
                    raise ValueError(
                        f'Invalid validation_status: {validation_status}'
                    )
            else:
                # No validation prompt - generator only workflow
                self.logger.debug(
                    'No validation prompt for %s, completing after generator',
                    action.name,
                )
                result['status'] = 'success'
                return result

        return result
