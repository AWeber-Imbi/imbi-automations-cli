import copy
import logging
import typing

import httpx

from imbi_automations import http, models

LOGGER = logging.getLogger(__name__)


class Imbi(http.BaseURLClient):
    def __init__(
        self,
        config: models.APIConfiguration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.hostname}'
        self.add_header('Private-Token', config.api_key.get_secret_value())
        self._project_types: list[models.ImbiProjectType] = []

    async def get_project_types(self) -> list[models.ImbiProjectType]:
        response = await self.get('/project-types')
        self._project_types = [
            models.ImbiProjectType(**item) for item in response.json()
        ]
        return self._project_types

    async def get_project_fact_types(self) -> list[models.ImbiProjectFactType]:
        """Get all project fact types."""
        response = await self.get('/project-fact-types')
        response.raise_for_status()
        return [models.ImbiProjectFactType(**item) for item in response.json()]

    async def get_project_fact_type_enums(
        self,
    ) -> list[models.ImbiProjectFactTypeEnum]:
        """Get all project fact type enum values."""
        response = await self.get('/project-fact-type-enums')
        response.raise_for_status()
        return [
            models.ImbiProjectFactTypeEnum(**item) for item in response.json()
        ]

    async def get_project_facts(
        self, project_id: int
    ) -> list[models.ImbiProjectFact]:
        """Get current facts for a project."""
        response = await self.get(f'/projects/{project_id}/facts')
        response.raise_for_status()
        return [models.ImbiProjectFact(**item) for item in response.json()]

    async def set_project_facts(
        self, project_id: int, facts: list[models.ImbiProjectFact]
    ) -> None:
        """Set project facts."""
        LOGGER.debug('Setting %d facts for project %s', len(facts), project_id)

        # Send only the essential fields the API expects
        facts_data = [
            {'fact_type_id': fact.fact_type_id, 'value': fact.value}
            for fact in facts
        ]
        LOGGER.debug('Facts data: %s', facts_data)

        response = await self.post(
            f'/projects/{project_id}/facts', json=facts_data
        )
        response.raise_for_status()
        LOGGER.debug('Successfully set facts for project %s', project_id)

    async def set_project_link(
        self, project_id: int, link_type_id: int, url: str
    ) -> models.ImbiProjectLink:
        """Set a project link for an Imbi project."""
        LOGGER.debug(
            'Setting project link for project %s: type_id=%s, url=%s',
            project_id,
            link_type_id,
            url,
        )

        link_data = {
            'project_id': project_id,
            'link_type_id': link_type_id,
            'url': url,
        }

        LOGGER.debug('Sending link data: %s', link_data)

        try:
            # First, try to create the link
            response = await self.post(
                f'/projects/{project_id}/links', json=link_data
            )
            response.raise_for_status()
            LOGGER.debug(
                'Successfully created new link type %s for project %s',
                link_type_id,
                project_id,
            )
            return models.ImbiProjectLink(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Conflict - link already exists, update it instead
                LOGGER.debug(
                    'Link type %s already exists for project %s, updating URL',
                    link_type_id,
                    project_id,
                )
                try:
                    # Update the existing link using PATCH
                    patch_data = [
                        {'op': 'replace', 'path': '/url', 'value': url}
                    ]
                    response = await self.patch(
                        f'/projects/{project_id}/links/{link_type_id}',
                        json=patch_data,
                    )

                    # Handle 304 Not Modified as success (URL already correct)
                    if response.status_code == 304:
                        LOGGER.debug(
                            'Link type %s for project %s already correct',
                            link_type_id,
                            project_id,
                        )
                        # Get existing link data since 304 has no content
                        links_response = await self.get(
                            f'/projects/{project_id}/links'
                        )
                        links_data = links_response.json()
                        for link in links_data:
                            if link.get('link_type_id') == link_type_id:
                                return models.ImbiProjectLink(**link)
                        # Fallback if link not found in list
                        return models.ImbiProjectLink(
                            id=None,  # Unknown ID since link wasn't found
                            project_id=project_id,
                            link_type_id=link_type_id,
                            created_by='migration-tool',
                            url=url,
                        )

                    response.raise_for_status()
                    LOGGER.debug(
                        'Successfully updated existing link type %s for '
                        'project %s',
                        link_type_id,
                        project_id,
                    )
                    return models.ImbiProjectLink(**response.json())
                except httpx.HTTPStatusError as update_error:
                    LOGGER.error(
                        'Failed to update existing link type %s for '
                        'project %s. Status: %s, Response: %s',
                        link_type_id,
                        project_id,
                        update_error.response.status_code,
                        update_error.response.text,
                    )
                    raise
            else:
                LOGGER.error(
                    'Failed to create link type %s for project %s. '
                    'Status: %s, Response: %s',
                    link_type_id,
                    project_id,
                    e.response.status_code,
                    e.response.text,
                )
                raise

    async def set_github_repository_link(
        self, project_id: int, github_repo: models.GitHubRepository
    ) -> models.ImbiProjectLink:
        """Set the GitHub repository link for an Imbi project."""
        return await self.set_project_link(project_id, 7, github_repo.html_url)

    async def delete_project_link(self, project_id: int, link_id: int) -> None:
        """Delete a project link by link ID."""
        LOGGER.debug(
            'Deleting project link %s for project %s', link_id, project_id
        )

        response = await self.delete(f'/projects/{project_id}/links/{link_id}')
        response.raise_for_status()
        LOGGER.debug('Successfully deleted project link %s', link_id)

    async def delete_project_link_by_type(
        self, project_id: int, link_type_id: int
    ) -> bool:
        """Delete project link by type ID. Returns True if found."""
        LOGGER.debug(
            'Searching for project link with type %s for project %s',
            link_type_id,
            project_id,
        )

        # Get current project links
        links_response = await self.get(f'/projects/{project_id}/links')
        links_data = links_response.json()

        LOGGER.debug(
            'Retrieved %d links for project %s', len(links_data), project_id
        )

        # Find link with matching type
        for link in links_data:
            if link.get('link_type_id') == link_type_id:
                link_id = link.get('id')
                LOGGER.debug(
                    'Found existing link type %s (ID: %s), deleting',
                    link_type_id,
                    link_id,
                )
                if link_id is not None:
                    await self.delete_project_link(project_id, link_id)
                else:
                    # If no individual link ID, delete by link type directly
                    LOGGER.debug(
                        'No individual link ID found, deleting by type %s',
                        link_type_id,
                    )
                    response = await self.delete(
                        f'/projects/{project_id}/links/{link_type_id}'
                    )
                    response.raise_for_status()
                return True

        LOGGER.debug(
            'No existing link found with type %s for project %s',
            link_type_id,
            project_id,
        )
        return False

    async def set_project_identifier(
        self, project_id: int, integration_name: str, external_id: str
    ) -> None:
        """Set a project identifier for a specific integration."""
        LOGGER.debug(
            'Setting project identifier for project %s: %s=%s',
            project_id,
            integration_name,
            external_id,
        )

        identifier_data = {
            'integration_name': integration_name,
            'external_id': external_id,
        }

        LOGGER.debug('Sending identifier data: %s', identifier_data)

        try:
            response = await self.post(
                f'/projects/{project_id}/identifiers', json=identifier_data
            )
            response.raise_for_status()
            LOGGER.debug(
                'Successfully set %s identifier for project %s: %s',
                integration_name,
                project_id,
                external_id,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Identifier already exists, check if it needs updating
                LOGGER.debug(
                    '%s identifier for project %s exists, checking if update '
                    'needed',
                    integration_name,
                    project_id,
                )

                # Get current project data to check existing identifier value
                project = await self.get_project(project_id)
                current_id = None
                if (
                    project.identifiers
                    and integration_name in project.identifiers
                ):
                    current_id = str(project.identifiers[integration_name])

                if current_id == external_id:
                    LOGGER.debug(
                        '%s identifier for project %s has correct value: %s',
                        integration_name,
                        project_id,
                        external_id,
                    )
                else:
                    LOGGER.debug(
                        '%s identifier for project %s needs update: %s -> %s',
                        integration_name,
                        project_id,
                        current_id,
                        external_id,
                    )

                    # Delete existing identifier and create new one
                    await self.delete_project_identifier(
                        project_id, integration_name
                    )

                    # Retry the POST request
                    try:
                        response = await self.post(
                            f'/projects/{project_id}/identifiers',
                            json=identifier_data,
                        )
                        response.raise_for_status()
                        LOGGER.debug(
                            'Updated %s identifier for project %s: %s',
                            integration_name,
                            project_id,
                            external_id,
                        )
                    except httpx.HTTPStatusError as retry_error:
                        if retry_error.response.status_code == 409:
                            LOGGER.warning(
                                'Failed to update %s identifier for project %s'
                                'after delete/retry - may be correct already',
                                integration_name,
                                project_id,
                            )
                            # Don't re-raise - treat as non-fatal
                        else:
                            raise
            else:
                LOGGER.error(
                    'Failed to set %s identifier for project %s. Status: %s, '
                    'Response: %s',
                    integration_name,
                    project_id,
                    e.response.status_code,
                    e.response.text,
                )
                raise

    async def delete_project_identifier(
        self, project_id: int, integration_name: str
    ) -> bool:
        """Delete a project identifier for a specific integration."""
        LOGGER.debug(
            'Deleting %s identifier for project %s',
            integration_name,
            project_id,
        )

        try:
            response = await self.delete(
                f'/projects/{project_id}/identifiers/{integration_name}'
            )
            if response.status_code == 204:
                LOGGER.debug(
                    'Successfully deleted %s identifier for project %s',
                    integration_name,
                    project_id,
                )
                return True
            elif response.status_code == 404:
                LOGGER.debug(
                    'No %s identifier found for project %s',
                    integration_name,
                    project_id,
                )
                return False
            else:
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            LOGGER.error(
                'Failed to delete %s identifier for project %s. Status: %s, '
                'Response: %s',
                integration_name,
                project_id,
                e.response.status_code,
                e.response.text,
            )
            raise

    async def get_project(self, project_id: int) -> models.ImbiProject | None:
        result = await self._opensearch_projects(
            self._search_project_id(project_id)
        )
        return result[0] if result else None

    async def get_projects_by_type(
        self, project_type_slug: str
    ) -> list[models.ImbiProject]:
        """Get all projects of a specific project type using slug."""
        all_projects = []
        page_size = 100  # OpenSearch default is usually 10, increase to 100
        start_from = 0

        while True:
            query = self._search_project_type_slug(project_type_slug)
            # Add pagination parameters
            query['from'] = start_from
            query['size'] = page_size

            LOGGER.debug(
                'Fetching projects page: from=%d, size=%d, slug=%s',
                start_from,
                page_size,
                project_type_slug,
            )

            page_results = await self._opensearch_projects(query)

            if not page_results:
                # No more results
                break

            all_projects.extend(page_results)

            # If we got fewer results than page_size, we've reached the end
            if len(page_results) < page_size:
                break

            start_from += page_size

        LOGGER.debug(
            'Found %d total projects with project_type_slug: %s',
            len(all_projects),
            project_type_slug,
        )

        # Sort by project slug for deterministic results
        all_projects.sort(key=lambda project: project.slug)

        return all_projects

    def _add_imbi_url(
        self, project: dict[str, typing.Any]
    ) -> models.ImbiProject:
        value = project['_source'].copy()
        value['imbi_url'] = f'{self.base_url}/ui/projects/{value["id"]}'
        return models.ImbiProject.model_validate(value)

    async def _opensearch_projects(
        self, query: dict[str, typing.Any]
    ) -> list[models.ImbiProject]:
        try:
            data = await self._opensearch_request(
                '/opensearch/projects', query
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            LOGGER.error(
                'Error searching Imbi projects: Request error %s', err
            )
            return []
        if not data or 'hits' not in data or 'hits' not in data['hits']:
            return []
        projects = []
        for project in data['hits']['hits']:
            projects.append(self._add_imbi_url(project))
        return projects

    def _search_project_id(self, value: int) -> dict[str, typing.Any]:
        """Return a query payload for searching by project ID."""
        payload = self._opensearch_payload()
        payload['query'] = {
            'bool': {'filter': [{'term': {'_id': f'{value}'}}]}
        }
        return payload

    def _search_project_type_slug(self, value: str) -> dict[str, typing.Any]:
        """Return a query payload for searching by project_type_slug."""
        payload = self._opensearch_payload()
        payload['query'] = {
            'bool': {
                'must': [
                    {'match': {'archived': False}},
                    {'term': {'project_type_slug.keyword': value}},
                ]
            }
        }
        return payload

    def _search_projects(self, value: str) -> dict[str, typing.Any]:
        payload = self._opensearch_payload()
        slug_value = value.lower().replace(' ', '-')
        payload['query'] = {
            'bool': {
                'must': [{'match': {'archived': False}}],
                'should': [
                    {
                        'term': {
                            'name': {'value': value, 'case_insensitive': True}
                        }
                    },
                    {'fuzzy': {'name': {'value': value}}},
                    {'match_phrase': {'name': {'query': value}}},
                    {
                        'term': {
                            'slug': {
                                'value': slug_value,
                                'case_insensitive': True,
                            }
                        }
                    },
                ],
                'minimum_should_match': 1,
            }
        }
        return payload

    @staticmethod
    def _opensearch_payload() -> dict[str, typing.Any]:
        return copy.deepcopy(
            {
                '_source': {
                    'exclude': ['archived', 'component_versions', 'components']
                },
                'query': {'bool': {'must': {'term': {'archived': False}}}},
            }
        )

    async def _opensearch_request(
        self, url: str, query: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        LOGGER.debug('Query: %r', query)
        response = await self.post(url, json=query)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            LOGGER.error('Error searching Imbi projects: %s', err)
            LOGGER.debug('Response: %r', response.content)
            raise err
        try:
            return response.json() if response.content else {}
        except ValueError as err:
            LOGGER.error('Error deserializing the response: %s', err)
            raise err
