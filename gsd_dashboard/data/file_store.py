"""
File upload storage for the dashboard.

Demo mode stores files under data/uploads. Production mode stores files in a
private Supabase Storage bucket using the configured server-side secret key.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


_DATA_DIR = Path(__file__).parent
_UPLOAD_DIR = _DATA_DIR / "uploads"
_MANIFEST = _UPLOAD_DIR / "manifest.json"
_BUCKET = "dashboard-uploads"


def _is_demo() -> bool:
    return str(_secret("DEMO_MODE", os.environ.get("DEMO_MODE", "true"))).lower() in ("true", "1", "yes")


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name)
    return cleaned.strip().replace("/", "_") or "upload"


def _load_manifest() -> list[dict]:
    if not _MANIFEST.exists():
        return []
    with open(_MANIFEST) as f:
        return json.load(f)


def _save_manifest(rows: list[dict]) -> None:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(_MANIFEST, "w") as f:
        json.dump(rows, f, indent=2)


def _supabase():
    from data.queries import _get_supabase

    return _get_supabase()


def _ensure_bucket(client: Any) -> None:
    try:
        buckets = client.storage.list_buckets()
        for bucket in buckets:
            bucket_name = getattr(bucket, "name", None)
            if bucket_name is None and isinstance(bucket, dict):
                bucket_name = bucket.get("name")
            if bucket_name == _BUCKET:
                return
    except Exception:
        pass

    try:
        client.storage.create_bucket(_BUCKET, options={"public": False})
    except TypeError:
        client.storage.create_bucket(_BUCKET)
    except Exception:
        pass


def save_upload(uploaded_file, uploaded_by: str, role: str) -> dict:
    content = uploaded_file.getvalue()
    digest = hashlib.sha256(content).hexdigest()[:16]
    original_name = _safe_name(uploaded_file.name)
    stored_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{digest}_{original_name}"
    content_type = uploaded_file.type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    record = {
        "name": original_name,
        "stored_name": stored_name,
        "size": len(content),
        "content_type": content_type,
        "uploaded_by": uploaded_by,
        "role": role,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    if _is_demo():
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (_UPLOAD_DIR / stored_name).write_bytes(content)
        rows = _load_manifest()
        rows.insert(0, record)
        _save_manifest(rows)
        return record

    client = _supabase()
    if not client:
        raise RuntimeError("Supabase is not configured.")

    _ensure_bucket(client)
    client.storage.from_(_BUCKET).upload(
        stored_name,
        content,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return record


def list_uploads() -> list[dict]:
    if _is_demo():
        return _load_manifest()

    client = _supabase()
    if not client:
        return []

    try:
        _ensure_bucket(client)
        rows = client.storage.from_(_BUCKET).list()
    except Exception:
        return []

    uploads = []
    for row in rows or []:
        name = row.get("name", "")
        metadata = row.get("metadata") or {}
        uploads.append({
            "name": name.split("_", 2)[-1] if "_" in name else name,
            "stored_name": name,
            "size": metadata.get("size"),
            "content_type": metadata.get("mimetype") or metadata.get("contentType"),
            "uploaded_by": "",
            "role": "",
            "uploaded_at": row.get("created_at") or row.get("updated_at"),
        })
    return sorted(uploads, key=lambda item: item.get("uploaded_at") or "", reverse=True)


def get_download_bytes(stored_name: str) -> bytes | None:
    if _is_demo():
        path = _UPLOAD_DIR / stored_name
        return path.read_bytes() if path.exists() else None

    client = _supabase()
    if not client:
        return None
    try:
        return client.storage.from_(_BUCKET).download(stored_name)
    except Exception:
        return None


def delete_upload(stored_name: str) -> None:
    if _is_demo():
        path = _UPLOAD_DIR / stored_name
        if path.exists():
            path.unlink()
        rows = [row for row in _load_manifest() if row.get("stored_name") != stored_name]
        _save_manifest(rows)
        return

    client = _supabase()
    if not client:
        raise RuntimeError("Supabase is not configured.")
    client.storage.from_(_BUCKET).remove([stored_name])
