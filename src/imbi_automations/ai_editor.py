"""Direct Anthropic API editor for fast file transformations."""

import logging
import pathlib

import anthropic

LOGGER = logging.getLogger(__name__)


class AIEditor:
    """Direct Anthropic API editor for fast file transformations."""

    def __init__(self, api_key: str, working_directory: pathlib.Path) -> None:
        """Initialize AI Editor with Anthropic API client.

        Args:
            api_key: Anthropic API key
            working_directory: Repository working directory
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.working_directory = working_directory

    async def execute_prompt(
        self,
        prompt_content: str,
        target_file: str,
        timeout_seconds: int = 300,
        max_retries: int = 3,
    ) -> dict[str, str | bool]:
        """Execute AI Editor prompt for file transformation.

        Args:
            prompt_content: The prompt content to send to AI
            target_file: Target file path relative to working directory
            timeout_seconds: Timeout for API call
            max_retries: Maximum retry attempts

        Returns:
            Dictionary with result status and details
        """
        target_file_path = self.working_directory / target_file

        # Read current file content if it exists
        current_content = ''
        if target_file_path.exists():
            try:
                current_content = target_file_path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                LOGGER.warning(
                    'Failed to read target file %s: %s', target_file_path, exc
                )
                current_content = ''

        # Enhance prompt with current file content
        enhanced_prompt = f"""{prompt_content}

## Current File Content

File: {target_file}
Path: {target_file_path}

```
{current_content}
```

## Critical Instructions

You MUST analyze the current file content above and apply the requested
transformations.

Your response format is CRITICAL and must be EXACTLY one of these two options:

### Option 1: No changes needed
Return EXACTLY this single word with NOTHING else: NO_CHANGES

### Option 2: Changes are needed
Return exactly this format with NO deviations:

CORRECTED_CONTENT
[complete file content goes here - must be the entire file, not just changes]
END_CORRECTED_CONTENT

SUMMARY
[brief description of changes made]

CRITICAL REQUIREMENTS:
- If no changes needed: Return ONLY "NO_CHANGES" with no explanations
- If changes needed: Use CORRECTED_CONTENT/END_CORRECTED_CONTENT markers
- The markers must appear on their own lines with nothing else
- Do NOT use markdown code blocks around the markers
- Do NOT add any text before "CORRECTED_CONTENT"
- The content between markers must be the complete corrected file
- Do NOT include partial content or just the changes
- The SUMMARY section comes after END_CORRECTED_CONTENT
- Do NOT provide analysis, explanations, or reasoning in your response"""

        # Execute with retries
        for attempt in range(max_retries):
            try:
                LOGGER.debug(
                    'AI Editor attempt %d/%d for file %s',
                    attempt + 1,
                    max_retries,
                    target_file,
                )

                response = self.client.messages.create(
                    model='claude-3-haiku-20240307',
                    max_tokens=8192,
                    system=(
                        'You are an expert code editor. You MUST follow the '
                        'exact response format specified in the user message. '
                        'If no changes are needed, return ONLY "NO_CHANGES" '
                        'with no additional text or explanations. If changes '
                        'are needed, use the CORRECTED_CONTENT/'
                        'END_CORRECTED_CONTENT markers. Any deviation from '
                        'these exact formats will cause parsing failures. '
                        'Never include analysis or explanations.'
                    ),
                    messages=[{'role': 'user', 'content': enhanced_prompt}],
                    timeout=timeout_seconds,
                )

                response_text = response.content[0].text.strip()

                # Check if no changes are needed
                if (
                    response_text == 'NO_CHANGES'
                    or response_text.strip().endswith('NO_CHANGES')
                    and 'CORRECTED_CONTENT' not in response_text
                ):
                    LOGGER.debug('AI Editor determined no changes needed')
                    return {
                        'status': 'no_changes',
                        'changed': False,
                        'target_file': target_file,
                        'attempts': attempt + 1,
                    }

                # Parse corrected content from response
                corrected_content = self._parse_corrected_content(
                    response_text
                )
                if corrected_content is None:
                    if attempt < max_retries - 1:
                        LOGGER.warning(
                            'AI Editor parsing failed (%d/%d), retrying',
                            attempt + 1,
                            max_retries,
                        )
                        continue
                    else:
                        return {
                            'status': 'parse_error',
                            'changed': False,
                            'target_file': target_file,
                            'attempts': attempt + 1,
                            'error': 'Failed to parse AI response',
                        }

                # Check if content actually changed
                if corrected_content.strip() == current_content.strip():
                    LOGGER.debug(
                        'AI Editor content unchanged after transformation'
                    )
                    return {
                        'status': 'no_changes',
                        'changed': False,
                        'target_file': target_file,
                        'attempts': attempt + 1,
                    }

                # Write corrected content to target file
                try:
                    # Ensure target directory exists
                    target_file_path.parent.mkdir(parents=True, exist_ok=True)

                    target_file_path.write_text(
                        corrected_content, encoding='utf-8'
                    )

                    LOGGER.debug(
                        'AI Editor successfully wrote %d characters to %s',
                        len(corrected_content),
                        target_file_path,
                    )

                    return {
                        'status': 'success',
                        'changed': True,
                        'target_file': target_file,
                        'attempts': attempt + 1,
                    }

                except OSError as exc:
                    if attempt < max_retries - 1:
                        LOGGER.warning(
                            'Failed to write file (attempt %d/%d): %s',
                            attempt + 1,
                            max_retries,
                            exc,
                        )
                        continue
                    else:
                        return {
                            'status': 'write_error',
                            'changed': False,
                            'target_file': target_file,
                            'attempts': attempt + 1,
                            'error': str(exc),
                        }

            except anthropic.APITimeoutError as exc:
                if attempt < max_retries - 1:
                    LOGGER.warning(
                        'AI Editor API timeout (attempt %d/%d), retrying...',
                        attempt + 1,
                        max_retries,
                    )
                    continue
                else:
                    return {
                        'status': 'timeout',
                        'changed': False,
                        'target_file': target_file,
                        'attempts': attempt + 1,
                        'error': str(exc),
                    }

            except (anthropic.APIError, anthropic.APIConnectionError) as exc:
                if attempt < max_retries - 1:
                    LOGGER.warning(
                        'AI Editor API error (attempt %d/%d): %s',
                        attempt + 1,
                        max_retries,
                        exc,
                    )
                    continue
                else:
                    return {
                        'status': 'api_error',
                        'changed': False,
                        'target_file': target_file,
                        'attempts': attempt + 1,
                        'error': str(exc),
                    }

        # Should not reach here
        return {
            'status': 'unknown_error',
            'changed': False,
            'target_file': target_file,
            'attempts': max_retries,
            'error': 'All retry attempts failed',
        }

    def _parse_corrected_content(self, response_text: str) -> str | None:
        """Parse corrected content from AI Editor response.

        Args:
            response_text: Raw response text from Anthropic API

        Returns:
            Corrected file content or None if parsing failed
        """
        # Look for corrected content markers
        start_marker = 'CORRECTED_CONTENT'
        end_marker = 'END_CORRECTED_CONTENT'

        # Case-insensitive search
        response_upper = response_text.upper()
        start_idx = response_upper.find(start_marker)
        if start_idx == -1:
            LOGGER.warning(
                'AI Editor response missing CORRECTED_CONTENT marker'
            )
            return None

        # Find the actual content start (after the marker)
        content_start = start_idx + len(start_marker)

        # Skip any whitespace/newlines after the start marker
        while (
            content_start < len(response_text)
            and response_text[content_start] in ' \n\r\t'
        ):
            content_start += 1

        # Look for end marker (case-insensitive)
        end_idx = response_upper.find(end_marker, content_start)
        if end_idx == -1:
            LOGGER.warning(
                'AI Editor response missing END_CORRECTED_CONTENT marker, '
                'using content from CORRECTED_CONTENT to end'
            )
            corrected_content = response_text[content_start:]
        else:
            # Extract the content between markers
            corrected_content = response_text[content_start:end_idx]

        # Clean up the content
        corrected_content = corrected_content.rstrip()

        # Final validation - ensure we have actual content
        if not corrected_content.strip():
            LOGGER.warning(
                'AI Editor response contained markers but no content between '
                'them'
            )
            return None

        return corrected_content
