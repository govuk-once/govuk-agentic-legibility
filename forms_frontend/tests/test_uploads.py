"""Local synthetic upload storage; no Temporal/AWS needed."""

import asyncio

import pytest

from forms_frontend.api.uploads import InvalidUpload, MAX_UPLOAD_BYTES, save_local_upload


def test_upload_persists_real_bytes_and_returns_opaque_ref(tmp_path):
    async def chunks():
        yield b"%PDF-"
        yield b"synthetic data"

    ref = asyncio.run(save_local_upload(chunks=chunks(), directory=tmp_path,
        session_id="test-session", content_type="application/pdf"))
    assert ref["bytes"] == len(b"%PDF-synthetic data")
    assert ref["content_type"] == "application/pdf"
    assert ref["ref"].startswith("local://test-session/")
    assert (tmp_path / "test-session" / ref["ref"].rsplit("/", 1)[-1]).read_bytes() == b"%PDF-synthetic data"


@pytest.mark.parametrize("data,message", [(b"", "empty"), (b"x" * (MAX_UPLOAD_BYTES + 1), "larger")])
def test_invalid_upload_leaves_no_partial_file(tmp_path, data, message):
    async def chunks():
        yield data

    with pytest.raises(InvalidUpload, match=message):
        asyncio.run(save_local_upload(chunks=chunks(), directory=tmp_path,
            session_id="test-session", content_type="application/pdf"))
    assert not list((tmp_path / "test-session").glob("*"))
