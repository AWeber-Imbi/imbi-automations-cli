import copy
import logging
import typing

import httpx

from imbi_automations import http, models

LOGGER = logging.getLogger(__name__)


class Imbi(http.BaseURLClient):
    def __init__(
        self,
        config: models.ImbiConfiguration,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(transport)
        self._base_url = f'https://{config.hostname}'
        self.add_header('Private-Token', config.api_key.get_secret_value())
        self._project_types: list[models.ImbiProjectType] = []

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

    async def search_projects_by_github_url(
        self, github_url: str
    ) -> list[models.ImbiProject]:
        """Search for Imbi projects by GitHub repository URL in project links.

        Args:
            github_url: GitHub repository URL to search for

        Returns:
            List of matching Imbi projects

        """
        query = self._opensearch_payload()
        query['query'] = {
            'bool': {
                'must': [
                    {'match': {'archived': False}},
                    {
                        'nested': {
                            'path': 'links',
                            'query': {
                                'bool': {
                                    'must': [
                                        {'match': {'links.url': github_url}}
                                    ]
                                }
                            },
                        }
                    },
                ]
            }
        }
        return await self._opensearch_projects(query)

    async def get_all_projects(self) -> list[models.ImbiProject]:
        """Get all active Imbi projects.

        Returns:
            List of all active Imbi projects

        """
        all_projects = []
        page_size = 100
        start_from = 0

        while True:
            query = self._opensearch_payload()
            query['query'] = {'match': {'archived': False}}
            query['from'] = start_from
            query['size'] = page_size

            page_projects = await self._opensearch_projects(query)
            if not page_projects:
                break

            all_projects.extend(page_projects)
            start_from += page_size

            # Break if we got fewer results than page_size (last page)
            if len(page_projects) < page_size:
                break

        LOGGER.info('Found %d total active projects', len(all_projects))

        # Sort by project slug for deterministic results
        all_projects.sort(key=lambda project: project.slug)

        return all_projects

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
