"""Preview-only file refs: mocked Temporal, no file bytes or live services."""

from unittest.mock import AsyncMock, patch



def _start_at_file(api_client, mock_temporal, *, token="file-token", optional=False):
    mock_temporal.set_awaiting({
        "token": token, "prompt": "Upload an attachment", "state_id": "attachment",
        "schema": {"kind": "file_ref", "allow_skip": optional}, "state_type": "input",
    })
    response = api_client.post("/api/sessions", json={"form_id": "2130"})
    assert response.status_code == 200
    return response.json()["session_id"]


def test_mock_file_allows_progress_with_no_byte_upload(api_client, mock_temporal, monkeypatch):
    monkeypatch.delenv("FORMS_ENABLE_DEV_UPLOADS", raising=False)
    session_id = _start_at_file(api_client, mock_temporal)
    state = api_client.get(f"/api/sessions/{session_id}/state")
    assert state.json()["upload_mode"] == "mock"

    response = api_client.post(
        f"/api/sessions/{session_id}/files/mock?token=file-token",
        json={"bytes": 123, "content_type": "application/pdf"},
    )
    assert response.status_code == 200
    ref = response.json()
    assert ref["ref"].startswith("mock://")
    assert ref == {
        "ref": ref["ref"], "bytes": 123,
        "content_type": "application/pdf", "mock": True,
    }

    next_state = {"status": "RUNNING", "awaiting": {
        "token": "next-token", "state_id": "next", "prompt": "Next question",
        "schema": {"kind": "string"}, "state_type": "input",
    }}
    with patch("agent.tools.submit_input", new_callable=AsyncMock, return_value=next_state) as submit:
        answer = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "file-token", "value": ref},
        )
    assert answer.status_code == 200
    assert answer.json()["awaiting"]["token"] == "next-token"
    assert submit.await_args.kwargs["value"] == ref


def test_mock_file_rejects_stale_token_and_forged_reference(api_client, mock_temporal, monkeypatch):
    monkeypatch.delenv("FORMS_ENABLE_DEV_UPLOADS", raising=False)
    session_id = _start_at_file(api_client, mock_temporal)
    url = f"/api/sessions/{session_id}/files/mock"
    stale = api_client.post(f"{url}?token=old-token", json={"bytes": 1})
    assert stale.status_code == 409
    missing = api_client.post(f"{url}?token=file-token", json={"bytes": 0})
    assert missing.status_code == 422
    selected = api_client.post(f"{url}?token=file-token", json={"bytes": 1}).json()

    with patch("agent.tools.submit_input", new_callable=AsyncMock) as submit:
        forged = dict(selected, bytes=2)
        response = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "file-token", "value": forged},
        )
        assert response.status_code == 422
        response = api_client.post(
            f"/api/sessions/{session_id}/submit",
            json={"token": "file-token", "value": dict(selected, mock=False)},
        )
        assert response.status_code == 422
        submit.assert_not_called()


def test_mock_ref_cannot_be_submitted_in_another_session(api_client, mock_temporal, monkeypatch):
    monkeypatch.delenv("FORMS_ENABLE_DEV_UPLOADS", raising=False)
    first_id = _start_at_file(api_client, mock_temporal)
    ref = api_client.post(
        f"/api/sessions/{first_id}/files/mock?token=file-token", json={"bytes": 42},
    ).json()
    second_id = _start_at_file(api_client, mock_temporal)
    with patch("agent.tools.submit_input", new_callable=AsyncMock) as submit:
        response = api_client.post(
            f"/api/sessions/{second_id}/submit", json={"token": "file-token", "value": ref},
        )
        assert response.status_code == 422
        submit.assert_not_called()


def test_local_upload_mode_remains_opt_in(api_client, mock_temporal, monkeypatch):
    monkeypatch.setenv("FORMS_ENABLE_DEV_UPLOADS", "1")
    session_id = _start_at_file(api_client, mock_temporal)
    assert api_client.get(f"/api/sessions/{session_id}/state").json()["upload_mode"] == "local"
    response = api_client.post(
        f"/api/sessions/{session_id}/files/mock?token=file-token", json={"bytes": 42},
    )
    assert response.status_code == 409
