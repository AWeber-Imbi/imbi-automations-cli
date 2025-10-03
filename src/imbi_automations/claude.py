import enum
import json
import logging
import pathlib
from email import utils as email_utils

import anthropic
import claude_agent_sdk
import pydantic
from anthropic import types as anthropic_types
from claude_agent_sdk import types

from imbi_automations import mixins, models, prompts, utils, version

LOGGER = logging.getLogger(__name__)
BASE_PATH = pathlib.Path(__file__).parent


class AgentType(enum.StrEnum):
    """Enum for available actions."""

    task = 'task'
    validator = 'validator'


COMMIT = 'commit'


@claude_agent_sdk.tool(
    name='response_validator',
    description='Validate the response format from for the final message',
    input_schema=str,
)
def response_validator(message: str) -> str:
    """Use to format the result of an agent run."""
    LOGGER.debug('Validator tool invoked')
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return 'Payload not validate as JSON'
    try:
        models.AgentRun.model_validate(payload)
    except pydantic.ValidationError as exc:
        return str(exc)
    return 'Response is valid'


class Claude(mixins.WorkflowLoggerMixin):
    """Claude Code client for executing AI-powered code transformations."""

    def __init__(
        self,
        config: models.Configuration,
        context: models.WorkflowContext,
        verbose: bool = False,
    ) -> None:
        super().__init__(verbose)
        if config.anthropic.bedrock:
            self.anthropic = anthropic.AsyncAnthropicBedrock()
        else:
            self.anthropic = anthropic.AsyncAnthropic()
        self.agents: dict[str, types.AgentDefinition] = {}
        self.anthropic_model = config.anthropic.model
        self.config = config
        self.context = context
        self.logger: logging.Logger = LOGGER
        self.session_id: str | None = None
        commit_author = email_utils.parseaddr(self.config.commit_author)
        self.prompt_kwargs = {
            'commit_author': self.config.commit_author,
            'commit_author_name': commit_author[0],
            'commit_author_address': commit_author[1],
            'workflow_name': context.workflow.configuration.name,
            'working_directory': self.context.working_directory,
        }
        self._set_workflow_logger(self.context.workflow)
        self.client = self._create_client()

    async def commit(
        self, context: models.WorkflowContext, action: models.WorkflowAction
    ) -> None:
        """Leverage Claude Code to commit changes."""
        self.session_id = None
        self._log_verbose_info(
            'Using Claude Code to commit changes for %s', action.name
        )
        await self.client.connect()

        # Build the commit prompt from the command template
        commit_template = BASE_PATH / 'prompts' / 'commit.md.j2'
        prompt = prompts.render(
            source=commit_template,
            action_name=action.name,
            **self.prompt_kwargs,
        )

        await self.client.query(prompt)
        run = await self._get_response()
        await self.client.disconnect()

        if run.result == models.AgentRunResult.failure:
            for phrase in ['no changes to commit', 'working tree is clean']:
                if phrase in (run.message or '').lower():
                    return None
            raise RuntimeError(f'Claude Code commit failed: {run.message}')
        return None

    async def execute(self, action: models.WorkflowClaudeAction) -> None:
        """Execute the Claude Code action."""
        self.session_id = None
        await self.client.connect()

        success = False
        for cycle in range(1, action.max_cycles + 1):
            self._log_verbose_info(
                'Claude Code cycle %d/%d for action %s',
                cycle,
                action.max_cycles,
                action.name,
            )
            if await self._execute_cycle(action, cycle):
                LOGGER.debug(
                    'Claude Code %s cycle %d successful', action.name, cycle
                )
                success = True
                break

        await self.client.disconnect()

        if not success:
            raise RuntimeError(
                f'Claude Code action {action.name} failed after '
                f'{action.max_cycles} cycles'
            )

    async def query(self, prompt: str) -> str:
        """Use the Anthropic API to run one-off tasks"""
        message = await self.anthropic.messages.create(
            model=self.anthropic_model,
            max_tokens=8192,
            messages=[
                anthropic_types.MessageParam(role='user', content=prompt)
            ],
        )
        return message.content[0].text

    def _create_client(self) -> claude_agent_sdk.ClaudeSDKClient:
        """Create the Claude SDK client, initializing the environment"""
        settings = self._initialize_working_directory()
        LOGGER.debug('Claude Code settings: %s', settings)

        agent_tools = claude_agent_sdk.create_sdk_mcp_server(
            'agent_tools', version, [response_validator]
        )

        system_prompt = (BASE_PATH / 'claude-code' / 'CLAUDE.md').read_text()
        if self.context.workflow.configuration.prompt:
            system_prompt += '\n\n---\n\n'
            if isinstance(
                self.context.workflow.configuration.prompt, pydantic.AnyUrl
            ):
                system_prompt += prompts.render(
                    self.context,
                    self.context.workflow.configuration.prompt,
                    **self.prompt_kwargs,
                )
            else:
                raise RuntimeError

        options = claude_agent_sdk.ClaudeAgentOptions(
            agents=self.agents,
            allowed_tools=[
                'Bash',
                'Bash(git:*)',
                'BashOutput',
                'Edit',
                'Glob',
                'Grep',
                'KillShell',
                'MultiEdit',
                'Read',
                'Task',
                'Write',
                'Write',
                'WebFetch',
                'WebSearch',
                'SlashCommand',
                'mcp__agent_tools__response_validator',
            ],
            cwd=self.context.working_directory,
            mcp_servers={'agent_tools': agent_tools},
            settings=str(settings),
            setting_sources=['local'],
            system_prompt=types.SystemPromptPreset(
                type='preset', preset='claude_code', append=system_prompt
            ),
            permission_mode='bypassPermissions',
        )
        return claude_agent_sdk.ClaudeSDKClient(options)

    async def _execute_agent(
        self,
        action: models.WorkflowAction | models.WorkflowClaudeAction,
        agent: AgentType,
    ) -> models.AgentRun:
        prompt = self._get_prompt(action, agent)
        await self.client.query(prompt, session_id=self.session_id)
        return await self._get_response()

    async def _execute_cycle(
        self, action: models.WorkflowClaudeAction, cycle: int
    ) -> bool:
        for agent in [AgentType.task, AgentType.validator]:
            if agent == AgentType.validator and not action.validation_prompt:
                self.logger.debug('No validation prompt, skipping')
                continue
            self._log_verbose_info(
                'Executing Claude Code %s agent %s in cycle %d',
                agent,
                action.name,
                cycle,
            )
            execution = await self._execute_agent(action, agent)
            LOGGER.debug('Execute agent result: %r', execution)
            if execution.result == models.AgentRunResult.failure:
                self.logger.error(
                    'Claude Code %s agent %s failed in cycle %d',
                    agent,
                    action.name,
                    cycle,
                )
                return False
        return True

    def _get_prompt(
        self,
        action: models.WorkflowAction | models.WorkflowClaudeAction,
        agent: AgentType,
    ) -> str:
        """Return the rendered prompt for the given agent."""
        prompt = f'Use the "{agent}" agent to complete the following task:\n\n'

        if agent == AgentType.task:
            prompt_file = (
                self.context.working_directory / 'workflow' / action.prompt
            )
        elif agent == AgentType.validator:
            prompt_file = (
                self.context.working_directory
                / 'workflow'
                / action.validation_prompt
            )
        else:
            raise RuntimeError(f'Unknown agent: {agent}')

        if prompt_file.suffix == '.j2':
            data = dict(self.prompt_kwargs)
            data.update(self.context.model_dump())
            data.update({'action': action.model_dump()})
            for key in {'source', 'destination'}:
                if key in data:
                    del data[key]
            prompt += prompts.render(self.context, prompt_file, **data)
        else:
            prompt += prompt_file.read_text(encoding='utf-8')
        return prompt

    async def _get_response(self) -> models.AgentRun:
        async for message in self.client.receive_response():
            response = self._parse_message(message)
            if response and isinstance(response, models.AgentRun):
                return response

        return models.AgentRun(
            result=models.AgentRunResult.failure,
            message='Unspecified failure',
            errors=[],
        )

    def _initialize_working_directory(self) -> pathlib.Path:
        """Setup dynamic agents and settings for claude-agents action.

        Returns:
            Path to generated settings.json file

        """
        claude_dir = self.context.working_directory / '.claude'
        commands_dir = claude_dir / 'commands'
        commands_dir.mkdir(parents=True, exist_ok=True)

        for file in (BASE_PATH / 'claude-code' / 'commands').rglob('*'):
            if file.suffix == '.j2':
                content = prompts.render(
                    self.context, file, **self.prompt_kwargs
                )
            else:
                content = file.read_text(encoding='utf-8')
            commands_dir.joinpath(file.name.rstrip('.j2')).write_text(
                content, encoding='utf-8'
            )

        output_styles_dir = claude_dir / 'output-style'
        output_styles_dir.mkdir(parents=True, exist_ok=True)

        for agent in AgentType:
            self.agents[agent] = self._parse_agent_file(agent)

        # Create custom settings.json - disable all global settings
        settings = claude_dir / 'settings.json'
        settings.write_text(
            json.dumps(
                {
                    'hooks': {},
                    'outputStyle': 'json',
                    'settingSources': ['project', 'local'],
                },
                indent=2,
            ),
            encoding='utf-8',
        )

        with settings.open('r', encoding='utf-8') as f:
            LOGGER.debug('Claude Code settings: %s', f.read())

        return settings

    def _log_message(
        self,
        message_type: str,
        content: str
        | list[
            claude_agent_sdk.TextBlock
            | claude_agent_sdk.ContentBlock
            | claude_agent_sdk.ToolUseBlock
            | claude_agent_sdk.ToolResultBlock
        ],
    ) -> None:
        """Log the message from Claude Code passed in as a dataclass."""
        if isinstance(content, list):
            for entry in content:
                if isinstance(
                    entry,
                    claude_agent_sdk.ToolUseBlock
                    | claude_agent_sdk.ToolResultBlock,
                ):
                    continue
                elif isinstance(entry, claude_agent_sdk.TextBlock):
                    self.logger.debug('%s: %s', message_type, entry.text)
                else:
                    raise RuntimeError(f'Unknown message type: {type(entry)}')
        else:
            self.logger.debug('%s: %s', message_type, content)

    def _parse_agent_file(self, name: str) -> types.AgentDefinition:
        """Parse the agent file and return the agent.

        Expects format:
        ---
        name: agent_name
        description: Agent description
        tools: Tool1, Tool2, Tool3
        model: inherit
        ---
        Prompt content here...
        """
        agent_file = BASE_PATH / 'claude-code' / 'agents' / f'{name}.md.j2'
        content = agent_file.read_text(encoding='utf-8')

        # Split frontmatter and prompt content
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f'Invalid agent file format for {name}')

        # Parse frontmatter manually (simple YAML-like format)
        frontmatter = {}
        for line in parts[1].strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        # Extract prompt (everything after second ---)
        prompt = parts[2].strip()

        # Parse tools (comma-separated string to list)
        tools_str = frontmatter.get('tools', '')
        tools = [t.strip() for t in tools_str.split(',')] if tools_str else []

        return types.AgentDefinition(
            description=frontmatter.get('description', ''),
            prompt=prompts.render(self.context, prompt, **self.prompt_kwargs),
            tools=tools,
            model=frontmatter.get('model', 'inherit'),
        )

    def _parse_message(
        self, message: claude_agent_sdk.Message
    ) -> models.AgentRun | None:
        """Parse the response from Claude Code."""
        if isinstance(message, claude_agent_sdk.AssistantMessage):
            self._log_message('Claude Assistant', message.content)
        elif isinstance(message, claude_agent_sdk.SystemMessage):
            self.logger.debug('Claude System: %s', message.data)
        elif isinstance(message, claude_agent_sdk.UserMessage):
            self._log_message('Claude User', message.content)
        elif isinstance(message, claude_agent_sdk.ResultMessage):
            if self.session_id != message.session_id:
                self.session_id = message.session_id
            if message.is_error:
                return models.AgentRun(
                    result=models.AgentRunResult.failure,
                    message='Claude Error',
                    errors=[message.result],
                )
            if message.result.startswith('```json'):
                message.result = message.result[7:]
            if message.result.endswith('```'):
                message.result = message.result[:-3]

            LOGGER.debug('Result (%s): %r', message.session_id, message.result)

            try:
                payload = utils.extract_json(message.result)
            except ValueError as err:
                self.logger.error('Failed to parse JSON result: %s', err)
                return models.AgentRun(
                    result=models.AgentRunResult.failure,
                    errors=[f'Failed to parse JSON result: {err}'],
                    message='Agent Contract Failure',
                )
            return models.AgentRun.model_validate(payload)
        return None
