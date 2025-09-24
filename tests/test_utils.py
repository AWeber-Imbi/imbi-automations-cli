import tomllib
import unittest
from io import StringIO

import pydantic

from imbi_automations import utils


class TestSanitize(unittest.TestCase):
    def test_sanitize_url_with_password(self) -> None:
        """Test sanitizing URL containing password."""
        url = 'https://user:secret123@example.com/path'
        result = utils.sanitize(url)
        expected = 'https://user:******@example.com/path'
        self.assertEqual(result, expected)

    def test_sanitize_url_without_password(self) -> None:
        """Test sanitizing URL without password."""
        url = 'https://example.com/path'
        result = utils.sanitize(url)
        self.assertEqual(result, url)

    def test_sanitize_url_with_username_only(self) -> None:
        """Test sanitizing URL with username but no password."""
        url = 'https://user@example.com/path'
        result = utils.sanitize(url)
        self.assertEqual(result, url)

    def test_sanitize_multiple_urls_in_string(self) -> None:
        """Test sanitizing string with multiple URLs containing passwords."""
        text = (
            'Connect to https://user1:pass1@server1.com and '
            'https://user2:pass2@server2.com for data'
        )
        result = utils.sanitize(text)
        expected = (
            'Connect to https://user1:******@server1.com and '
            'https://user2:******@server2.com for data'
        )
        self.assertEqual(result, expected)

    def test_sanitize_different_protocols(self) -> None:
        """Test sanitizing URLs with different protocols."""
        urls = [
            'http://user:pass@example.com',
            'ftp://user:pass@example.com',
            'ssh://user:pass@example.com',
        ]
        for url in urls:
            result = utils.sanitize(url)
            self.assertIn('******', result)
            self.assertNotIn('pass', result)

    def test_sanitize_pydantic_anyurl(self) -> None:
        """Test sanitizing pydantic AnyUrl object."""
        url = pydantic.AnyUrl('https://user:secret@example.com')
        result = utils.sanitize(url)
        expected = 'https://user:******@example.com/'
        self.assertEqual(result, expected)

    def test_sanitize_complex_password(self) -> None:
        """Test sanitizing URL with complex password."""
        url = 'https://user:password123!@example.com/path'
        result = utils.sanitize(url)
        expected = 'https://user:******@example.com/path'
        self.assertEqual(result, expected)


class TestLoadToml(unittest.TestCase):
    def test_load_toml_success(self) -> None:
        """Test successful TOML loading."""
        toml_content = """
        [section]
        key = "value"
        number = 42
        boolean = true
        """
        toml_file = StringIO(toml_content)

        result = utils.load_toml(toml_file)

        expected = {'section': {'key': 'value', 'number': 42, 'boolean': True}}
        self.assertEqual(result, expected)

    def test_load_toml_empty_file(self) -> None:
        """Test loading empty TOML file."""
        toml_file = StringIO('')
        result = utils.load_toml(toml_file)
        self.assertEqual(result, {})

    def test_load_toml_invalid_syntax(self) -> None:
        """Test loading TOML with invalid syntax."""
        toml_file = StringIO('[invalid toml content [')

        with self.assertRaises(tomllib.TOMLDecodeError):
            utils.load_toml(toml_file)

    def test_load_toml_complex_structure(self) -> None:
        """Test loading TOML with complex nested structure."""
        toml_content = """
        [database]
        hostname = "localhost"
        port = 5432

        [database.credentials]
        username = "user"
        password = "pass"

        [[servers]]
        name = "server1"
        ip = "192.168.1.1"

        [[servers]]
        name = "server2"
        ip = "192.168.1.2"
        """
        toml_file = StringIO(toml_content)

        result = utils.load_toml(toml_file)

        self.assertEqual(result['database']['hostname'], 'localhost')
        self.assertEqual(result['database']['port'], 5432)
        self.assertEqual(result['database']['credentials']['username'], 'user')
        self.assertEqual(len(result['servers']), 2)
        self.assertEqual(result['servers'][0]['name'], 'server1')
        self.assertEqual(result['servers'][1]['ip'], '192.168.1.2')

    def test_load_toml_unicode_content(self) -> None:
        """Test loading TOML with unicode characters."""
        toml_content = """
        [unicode]
        name = "测试"
        emoji = "🚀"
        """
        toml_file = StringIO(toml_content)

        result = utils.load_toml(toml_file)

        self.assertEqual(result['unicode']['name'], '测试')
        self.assertEqual(result['unicode']['emoji'], '🚀')

    def test_load_toml_file_positioning(self) -> None:
        """Test that file is read completely regardless of initial position."""
        toml_content = """
        [test]
        value = "content"
        """
        toml_file = StringIO(toml_content)

        # Read some content first to change file position
        toml_file.read(5)
        # Reset position
        toml_file.seek(0)

        result = utils.load_toml(toml_file)

        self.assertEqual(result['test']['value'], 'content')


class TestVersionComparison(unittest.TestCase):
    def test_compare_versions_with_build_numbers_same_semantic_different_build(
        self,
    ) -> None:
        """Test version comparison with same semantic, different builds."""
        from imbi_automations.utils import Utils

        # Critical case: same semantic version, newer build number
        self.assertTrue(
            Utils.compare_versions_with_build_numbers('3.9.18-0', '3.9.18-4')
        )
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.18-4', '3.9.18-0')
        )

        # Edge case: equal versions
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.18-4', '3.9.18-4')
        )

    def test_compare_versions_with_build_numbers_different_semantic(
        self,
    ) -> None:
        """Test version comparison with different semantic versions."""
        from imbi_automations.utils import Utils

        # Older semantic version (build number irrelevant)
        self.assertTrue(
            Utils.compare_versions_with_build_numbers('3.9.17-4', '3.9.18-0')
        )

        # Newer semantic version (build number irrelevant)
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.19-0', '3.9.18-4')
        )

    def test_compare_versions_with_build_numbers_missing_build(self) -> None:
        """Test version comparison with missing build numbers."""
        from imbi_automations.utils import Utils

        # No build number vs with build number
        self.assertTrue(
            Utils.compare_versions_with_build_numbers('3.9.18', '3.9.18-4')
        )
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.18-4', '3.9.18')
        )

        # Both without build numbers
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.18', '3.9.18')
        )

    def test_compare_versions_with_build_numbers_invalid_build(self) -> None:
        """Test version comparison with invalid build numbers."""
        from imbi_automations.utils import Utils

        # Invalid build numbers should default to 0
        self.assertTrue(
            Utils.compare_versions_with_build_numbers('3.9.18-abc', '3.9.18-4')
        )
        self.assertFalse(
            Utils.compare_versions_with_build_numbers('3.9.18-4', '3.9.18-abc')
        )


if __name__ == '__main__':
    unittest.main()
