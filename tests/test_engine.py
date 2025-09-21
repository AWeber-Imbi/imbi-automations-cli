import unittest

from imbi_automations import engine, models


class TestAutomationIterator(unittest.TestCase):
    def test_automation_iterator_enum_values(self) -> None:
        """Test that AutomationIterator enum has correct values."""
        self.assertEqual(engine.AutomationIterator.github_repositories.value, 1)
        self.assertEqual(engine.AutomationIterator.github_organization.value, 2)
        self.assertEqual(engine.AutomationIterator.github_project.value, 3)
        self.assertEqual(engine.AutomationIterator.gitlab_repositories.value, 4)
        self.assertEqual(engine.AutomationIterator.gitlab_organization.value, 5)
        self.assertEqual(engine.AutomationIterator.gitlab_project.value, 6)
        self.assertEqual(engine.AutomationIterator.imbi_project_types.value, 7)
        self.assertEqual(engine.AutomationIterator.imbi_project.value, 8)
        self.assertEqual(engine.AutomationIterator.imbi_projects.value, 9)

    def test_automation_iterator_enum_names(self) -> None:
        """Test that AutomationIterator enum has correct names."""
        self.assertEqual(engine.AutomationIterator.github_repositories.name, 'github_repositories')
        self.assertEqual(engine.AutomationIterator.github_organization.name, 'github_organization')
        self.assertEqual(engine.AutomationIterator.github_project.name, 'github_project')
        self.assertEqual(engine.AutomationIterator.gitlab_repositories.name, 'gitlab_repositories')
        self.assertEqual(engine.AutomationIterator.gitlab_organization.name, 'gitlab_organization')
        self.assertEqual(engine.AutomationIterator.gitlab_project.name, 'gitlab_project')
        self.assertEqual(engine.AutomationIterator.imbi_project_types.name, 'imbi_project_types')
        self.assertEqual(engine.AutomationIterator.imbi_project.name, 'imbi_project')
        self.assertEqual(engine.AutomationIterator.imbi_projects.name, 'imbi_projects')

    def test_automation_iterator_count(self) -> None:
        """Test that AutomationIterator has expected number of values."""
        self.assertEqual(len(engine.AutomationIterator), 9)


class TestAutomationEngine(unittest.TestCase):
    def test_automation_engine_init(self) -> None:
        """Test AutomationEngine initialization."""
        config = models.Configuration()
        iterator = engine.AutomationIterator.imbi_project

        ae = engine.AutomationEngine(config, iterator)

        self.assertEqual(ae.configuration, config)
        self.assertEqual(ae.iterator, iterator)

    def test_automation_engine_init_all_iterator_types(self) -> None:
        """Test AutomationEngine initialization with all iterator types."""
        config = models.Configuration()

        for iterator in engine.AutomationIterator:
            ae = engine.AutomationEngine(config, iterator)
            self.assertEqual(ae.configuration, config)
            self.assertEqual(ae.iterator, iterator)

    def test_automation_engine_run_method_exists(self) -> None:
        """Test that AutomationEngine has run method."""
        config = models.Configuration()
        iterator = engine.AutomationIterator.imbi_project

        ae = engine.AutomationEngine(config, iterator)

        # Test that run method exists and is callable
        self.assertTrue(hasattr(ae, 'run'))
        self.assertTrue(callable(ae.run))

        # Test that run method doesn't raise exception when called
        # (it's a stub implementation with ... so should not raise)
        try:
            ae.run()
        except NotImplementedError:
            # This is expected for stub implementation
            pass


if __name__ == '__main__':
    unittest.main()