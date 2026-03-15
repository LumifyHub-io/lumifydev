"""Tests for remote session management and helpers."""

import unittest

from lumifydev_lib.remote import build_prompt, parse_session_comment, json_content_to_text


class TestBuildPrompt(unittest.TestCase):
    def test_basic_prompt(self):
        result = build_prompt("Fix login bug", "In Progress", "", [], None)
        self.assertIn("# Card: Fix login bug", result)
        self.assertIn("Status: In Progress", result)
        self.assertIn("Implement this card", result)

    def test_with_description(self):
        result = build_prompt("Add dark mode", "", "Support dark/light toggle", [], None)
        self.assertIn("## Description", result)
        self.assertIn("Support dark/light toggle", result)

    def test_with_comments(self):
        comments = [
            {"user_name": "Saad", "content": "Use CSS variables"},
            {"user_name": "Bot", "content": "Automated comment"},
        ]
        result = build_prompt("Theme support", "", "", comments, None)
        self.assertIn("## Comments", result)
        self.assertIn("- Saad: Use CSS variables", result)
        self.assertIn("- Bot: Automated comment", result)

    def test_with_user_prompt(self):
        result = build_prompt("Fix bug", "", "", [], "Focus on the auth flow")
        self.assertIn("## Task", result)
        self.assertIn("Focus on the auth flow", result)
        self.assertNotIn("Implement this card", result)

    def test_without_user_prompt_uses_default(self):
        result = build_prompt("Fix bug", "", "", [], None)
        self.assertIn("Implement this card", result)

    def test_empty_list_name_excluded(self):
        result = build_prompt("Fix bug", "", "", [], None)
        self.assertNotIn("Status:", result)

    def test_full_prompt(self):
        comments = [{"user_name": "Alice", "content": "Check edge cases"}]
        result = build_prompt(
            "Refactor auth", "To Do", "Clean up the auth module",
            comments, "Make it simpler"
        )
        self.assertIn("# Card: Refactor auth", result)
        self.assertIn("Status: To Do", result)
        self.assertIn("Clean up the auth module", result)
        self.assertIn("- Alice: Check edge cases", result)
        self.assertIn("Make it simpler", result)


class TestParseSessionComment(unittest.TestCase):
    def test_valid_comment(self):
        content = (
            "[LumifyDev] Session started\n"
            "Session: card-abc12345\n"
            "Worktree: my-project--card-abc12345\n"
            "VM: root@1.2.3.4"
        )
        info = parse_session_comment(content)
        self.assertIsNotNone(info)
        self.assertEqual(info["session"], "card-abc12345")
        self.assertEqual(info["worktree"], "my-project--card-abc12345")
        self.assertEqual(info["vm"], "root@1.2.3.4")

    def test_non_lumifydev_comment(self):
        self.assertIsNone(parse_session_comment("Just a regular comment"))

    def test_empty_content(self):
        self.assertIsNone(parse_session_comment(""))

    def test_incomplete_comment_missing_worktree(self):
        content = "[LumifyDev] Session started\nSession: card-abc12345"
        self.assertIsNone(parse_session_comment(content))

    def test_incomplete_comment_missing_session(self):
        content = "[LumifyDev] Session started\nWorktree: my-project--card-abc"
        self.assertIsNone(parse_session_comment(content))

    def test_comment_with_extra_lines(self):
        content = (
            "[LumifyDev] Session started\n"
            "Some extra info\n"
            "Session: card-xyz\n"
            "More stuff\n"
            "Worktree: proj--card-xyz\n"
            "VM: user@host"
        )
        info = parse_session_comment(content)
        self.assertIsNotNone(info)
        self.assertEqual(info["session"], "card-xyz")
        self.assertEqual(info["worktree"], "proj--card-xyz")


class TestJsonContentToText(unittest.TestCase):
    def test_plain_string_passthrough(self):
        self.assertEqual(json_content_to_text("hello"), "hello")

    def test_simple_paragraph(self):
        content = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        self.assertEqual(json_content_to_text(content), "Hello world")

    def test_multi_paragraph(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 1"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Line 2"}]},
            ],
        }
        self.assertEqual(json_content_to_text(content), "Line 1\nLine 2")

    def test_empty_paragraph(self):
        content = {
            "type": "doc",
            "content": [{"type": "paragraph"}],
        }
        self.assertEqual(json_content_to_text(content), "")

    def test_lumifydev_comment_as_json(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "[LumifyDev] Session started"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Session: card-abc12345"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Worktree: proj--card-abc12345"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "VM: root@1.2.3.4"}]},
            ],
        }
        text = json_content_to_text(content)
        self.assertIn("[LumifyDev]", text)
        self.assertIn("Session: card-abc12345", text)
        self.assertIn("Worktree: proj--card-abc12345", text)


class TestParseSessionCommentJSONContent(unittest.TestCase):
    def test_parse_json_content_comment(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "[LumifyDev] Session started"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Session: card-xyz"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "Worktree: proj--card-xyz"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "VM: root@1.2.3.4"}]},
            ],
        }
        info = parse_session_comment(content)
        self.assertIsNotNone(info)
        self.assertEqual(info["session"], "card-xyz")
        self.assertEqual(info["worktree"], "proj--card-xyz")
        self.assertEqual(info["vm"], "root@1.2.3.4")

    def test_non_lumifydev_json_content(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Just a comment"}]},
            ],
        }
        self.assertIsNone(parse_session_comment(content))


if __name__ == "__main__":
    unittest.main()
