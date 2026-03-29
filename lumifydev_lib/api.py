"""LumifyHub API client."""

import json
import urllib.error
import urllib.request


class APIError(Exception):
    """Raised when an API request fails."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def api_request(api_url, api_key, path, method="GET", body=None, workspace_id=None):
    """Make an authenticated request to the LumifyHub API.

    For CLI tokens (lhcli_*), includes x-workspace-id header when workspace_id is provided.
    For workspace API keys (lumify_*), workspace_id is ignored (embedded in key).
    """
    url = f"{api_url}{path}"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    # CLI tokens need workspace context via header
    if workspace_id and api_key.startswith("lhcli_"):
        headers["x-workspace-id"] = workspace_id

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode("utf-8"))
            msg = error_body.get("error", str(e))
        except (json.JSONDecodeError, UnicodeDecodeError):
            msg = str(e)
        raise APIError(msg, status_code=e.code)
    except urllib.error.URLError as e:
        raise APIError(f"Connection failed: {e.reason}")


def api(config, path, method="GET", body=None, workspace_id=None):
    """Shorthand for api_request using loaded config.

    Resolves workspace_id from: explicit param > current_workspace > default_workspace.
    """
    ws_id = workspace_id or config.get("current_workspace") or config.get("default_workspace")
    return api_request(config["api_url"], config["api_key"], path, method, body, workspace_id=ws_id)
