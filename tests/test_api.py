"""Tests for API client."""

import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from io import BytesIO

from lumifydev_lib.api import api_request, api, APIError


class TestAPIRequest(unittest.TestCase):
    @patch("lumifydev_lib.api.urllib.request.urlopen")
    def test_get_request_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"boards": []}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = api_request("https://www.lumifyhub.io", "lumify_key", "/api/v1/integrations/boards")
        self.assertEqual(result, {"boards": []})

        # Verify request was built correctly
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("X-api-key"), "lumify_key")
        self.assertEqual(req.get_method(), "GET")
        self.assertTrue(req.full_url.endswith("/api/v1/integrations/boards"))

    @patch("lumifydev_lib.api.urllib.request.urlopen")
    def test_post_request_sends_body(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"comment": {"id": "123"}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = api_request(
            "https://www.lumifyhub.io", "lumify_key",
            "/api/v1/integrations/boards/cards/abc/comments",
            method="POST",
            body={"content": "test comment"},
        )
        self.assertEqual(result["comment"]["id"], "123")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data), {"content": "test comment"})

    @patch("lumifydev_lib.api.urllib.request.urlopen")
    def test_http_error_raises_api_error(self, mock_urlopen):
        error_body = json.dumps({"error": "Board not found"}).encode()
        mock_urlopen.side_effect = HTTPError(
            url="https://www.lumifyhub.io/api/test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(error_body),
        )

        with self.assertRaises(APIError) as ctx:
            api_request("https://www.lumifyhub.io", "lumify_key", "/api/test")

        self.assertEqual(str(ctx.exception), "Board not found")
        self.assertEqual(ctx.exception.status_code, 404)

    @patch("lumifydev_lib.api.urllib.request.urlopen")
    def test_http_error_with_non_json_body(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://www.lumifyhub.io/api/test",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(b"not json"),
        )

        with self.assertRaises(APIError) as ctx:
            api_request("https://www.lumifyhub.io", "lumify_key", "/api/test")

        self.assertEqual(ctx.exception.status_code, 500)

    @patch("lumifydev_lib.api.urllib.request.urlopen")
    def test_connection_error_raises_api_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Connection refused")

        with self.assertRaises(APIError) as ctx:
            api_request("https://www.lumifyhub.io", "lumify_key", "/api/test")

        self.assertIn("Connection failed", str(ctx.exception))


class TestAPIShorthand(unittest.TestCase):
    @patch("lumifydev_lib.api.api_request")
    def test_api_passes_config(self, mock_api_request):
        mock_api_request.return_value = {"ok": True}

        config = {"api_url": "https://www.lumifyhub.io", "api_key": "lumify_abc"}
        result = api(config, "/api/test", method="POST", body={"key": "val"})

        mock_api_request.assert_called_once_with(
            "https://www.lumifyhub.io", "lumify_abc", "/api/test", "POST", {"key": "val"}
        )
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
