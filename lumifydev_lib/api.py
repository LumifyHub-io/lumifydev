"""LumifyHub API client."""

import json
import urllib.error
import urllib.request


class APIError(Exception):
    """Raised when an API request fails."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def api_request(api_url, api_key, path, method="GET", body=None):
    """Make an authenticated request to the LumifyHub API."""
    url = f"{api_url}{path}"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

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


def api(config, path, method="GET", body=None):
    """Shorthand for api_request using loaded config."""
    return api_request(config["api_url"], config["api_key"], path, method, body)
