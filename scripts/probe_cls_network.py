"""Probe CLS endpoint through environment proxy and direct network, without credentials."""

import json

import httpx


for mode, trust_env in (("environment_proxy", True), ("direct", False)):
    try:
        with httpx.Client(timeout=15.0, trust_env=trust_env) as client:
            response = client.post(
                "https://cls.tencentcloudapi.com/",
                json={},
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        print(
            json.dumps(
                {
                    "mode": mode,
                    "status": response.status_code,
                    "server": response.headers.get("server", ""),
                    "request_id": response.headers.get("x-tc-requestid", ""),
                    "body_prefix": response.text[:200],
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        print(
            json.dumps(
                {"mode": mode, "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
            )
        )
