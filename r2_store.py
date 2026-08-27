"""
R2-backed durable store — replaces local filesystem for users + usage logs.

Streamlit Cloud filesystem is EPHEMERAL (wipes on redeploy/sleep).
This module persists JSON blobs to Cloudflare R2 so state survives deploys.

Keys:
    control/users.json          — user store (bcrypt hashes + roles)
    control/usage_log.jsonl     — append-only audit log
"""
import json
import threading
from io import BytesIO
from typing import Any

import boto3
import streamlit as st

_LOCK = threading.Lock()
_CLIENT = None
_BUCKET = None


def _client():
    """Cached boto3 client for R2."""
    global _CLIENT, _BUCKET
    if _CLIENT is not None:
        return _CLIENT, _BUCKET
    r2 = st.secrets["r2"]
    _CLIENT = boto3.client(
        "s3",
        endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto"),
    )
    _BUCKET = r2["bucket"]
    return _CLIENT, _BUCKET


def get_json(key: str, default: Any = None) -> Any:
    """Read JSON blob from R2. Returns default if not found or corrupted."""
    try:
        c, bucket = _client()
        resp = c.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except Exception:
        return default if default is not None else {}


def put_json(key: str, data: Any):
    """Write JSON blob to R2 (atomic — R2 is strongly consistent)."""
    c, bucket = _client()
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    c.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8",
    )


def append_jsonl(key: str, entry: dict, max_lines: int = 10000):
    """Append a JSON line to R2 blob. Rotates when exceeds max_lines."""
    with _LOCK:
        try:
            c, bucket = _client()
            try:
                resp = c.get_object(Bucket=bucket, Key=key)
                existing = resp["Body"].read().decode("utf-8")
            except Exception:
                existing = ""

            line = json.dumps(entry, ensure_ascii=False)
            lines = existing.split("\n") if existing else []
            lines = [ln for ln in lines if ln.strip()]
            lines.append(line)

            # Rotate: keep last N lines
            if len(lines) > max_lines:
                lines = lines[-max_lines:]

            body = ("\n".join(lines) + "\n").encode("utf-8")
            c.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType="application/x-ndjson; charset=utf-8",
            )
        except Exception:
            pass  # Never crash on log failure


def read_jsonl_tail(key: str, limit: int = 500) -> list:
    """Read last N entries from JSONL blob."""
    try:
        c, bucket = _client()
        resp = c.get_object(Bucket=bucket, Key=key)
        text = resp["Body"].read().decode("utf-8")
    except Exception:
        return []

    lines = [ln for ln in text.split("\n") if ln.strip()]
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries[::-1]  # newest first
