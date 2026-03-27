"""Tests for config management."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from lumifydev_lib.config import load_config, save_config, require_config


class TestLoadConfig(unittest.TestCase):
    def test_returns_none_when_file_missing(self):
        with patch("lumifydev_lib.config.CONFIG_FILE", "/nonexistent/path.json"):
            self.assertIsNone(load_config())

    def test_loads_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_key": "lumify_test123", "api_url": "https://www.lumifyhub.io"}, f)
            f.flush()
            with patch("lumifydev_lib.config.CONFIG_FILE", f.name):
                config = load_config()
                self.assertEqual(config["api_key"], "lumify_test123")
                self.assertEqual(config["api_url"], "https://www.lumifyhub.io")
        os.unlink(f.name)


class TestSaveConfig(unittest.TestCase):
    def test_saves_and_loads_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            with patch("lumifydev_lib.config.CONFIG_DIR", tmpdir), \
                 patch("lumifydev_lib.config.CONFIG_FILE", config_file):
                save_config({"api_key": "lumify_abc", "vm_host": "root@1.2.3.4"})
                config = load_config()
                self.assertEqual(config["api_key"], "lumify_abc")
                self.assertEqual(config["vm_host"], "root@1.2.3.4")


class TestRequireConfig(unittest.TestCase):
    def test_exits_when_no_config(self):
        with patch("lumifydev_lib.config.CONFIG_FILE", "/nonexistent/path.json"):
            with self.assertRaises(SystemExit):
                require_config()

    def test_exits_when_no_api_key(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_url": "https://www.lumifyhub.io"}, f)
            f.flush()
            with patch("lumifydev_lib.config.CONFIG_FILE", f.name):
                with self.assertRaises(SystemExit):
                    require_config()
        os.unlink(f.name)

    def test_returns_config_when_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_key": "lumify_valid"}, f)
            f.flush()
            with patch("lumifydev_lib.config.CONFIG_FILE", f.name):
                config = require_config()
                self.assertEqual(config["api_key"], "lumify_valid")
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
