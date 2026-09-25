"""Opt-in local byte storage for synthetic file_ref testing (not production)."""

from __future__ import annotations

from collections.abc import AsyncIterable
from pathlib import Path
from uuid import uuid4

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class InvalidUpload(ValueError):
    pass


async def save_local_upload(*, chunks: AsyncIterable[bytes], directory: Path,
                            session_id: str, content_type: str) -> dict[str, object]:
    # The session ID comes from our UUID-backed store, never a user path.
    target_dir = directory / session_id
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    filename = uuid4().hex + ".blob"
    target = target_dir / filename
    length = 0
    try:
        with target.open("xb") as output:
            target.chmod(0o600)
            async for chunk in chunks:
                length += len(chunk)
                if length > MAX_UPLOAD_BYTES:
                    raise InvalidUpload("Files must be no larger than 10 MiB")
                output.write(chunk)
        if not length:
            raise InvalidUpload("Cannot upload an empty file")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {"ref": f"local://{session_id}/{filename}", "bytes": length,
            "content_type": content_type or "application/octet-stream"}
