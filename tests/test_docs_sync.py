import unittest

from advanced_fetch_mcp.docs_sync import (
    ENV_EXAMPLE_PATH,
    README_EN_PATH,
    README_ZH_PATH,
    render_env_example,
    render_synced_readme_text,
)


class DocsSyncTests(unittest.TestCase):
    def test_env_example_is_synced(self):
        self.assertEqual(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), render_env_example())

    def test_readme_zh_is_synced(self):
        content = README_ZH_PATH.read_text(encoding="utf-8")
        self.assertEqual(content, render_synced_readme_text(content, "zh"))

    def test_readme_en_is_synced(self):
        content = README_EN_PATH.read_text(encoding="utf-8")
        self.assertEqual(content, render_synced_readme_text(content, "en"))
