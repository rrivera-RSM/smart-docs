import hashlib
from collections.abc import MutableMapping
from typing import Any

TEMPLATE_BYTES_KEY = "smart_docs.template_bytes"
SOURCE_NAME_KEY = "smart_docs.source_name"
SOURCE_FINGERPRINT_KEY = "smart_docs.source_fingerprint"
OUTPUT_BYTES_KEY = "smart_docs.output_bytes"
UPLOAD_REVISION_KEY = "smart_docs.upload_revision"
FIELD_KEY_PREFIX = "smart_docs.field."


def _fingerprint(name: str, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    return f"{name}:{len(content)}:{digest}"


def _advance_upload_revision(state: MutableMapping[str, Any]) -> None:
    state[UPLOAD_REVISION_KEY] = state.get(UPLOAD_REVISION_KEY, 0) + 1


def _clear_derived_state(state: MutableMapping[str, Any]) -> None:
    state.pop(OUTPUT_BYTES_KEY, None)
    for key in list(state):
        if isinstance(key, str) and key.startswith(FIELD_KEY_PREFIX):
            state.pop(key, None)


def sync_uploaded_template(
    state: MutableMapping[str, Any],
    name: str,
    content: bytes,
) -> bytes:
    """Persist an upload and reset values only when its content changes."""
    fingerprint = _fingerprint(name, content)
    is_new_upload = (
        state.get(SOURCE_FINGERPRINT_KEY) != fingerprint
        or state.get(TEMPLATE_BYTES_KEY) != content
    )

    if is_new_upload:
        state[TEMPLATE_BYTES_KEY] = content
        state[SOURCE_NAME_KEY] = name
        state[SOURCE_FINGERPRINT_KEY] = fingerprint
        _clear_derived_state(state)

    # A fresh uploader key prevents a selected replacement from being handled
    # again on the following Streamlit rerun, even when it is the same file.
    _advance_upload_revision(state)
    return state[TEMPLATE_BYTES_KEY]


def store_fixed_template(
    state: MutableMapping[str, Any],
    content: bytes,
) -> None:
    """Replace the working copy after auto-fix without changing the upload."""
    state[TEMPLATE_BYTES_KEY] = content
    state.pop(OUTPUT_BYTES_KEY, None)
    _advance_upload_revision(state)


def store_output(
    state: MutableMapping[str, Any],
    content: bytes,
) -> None:
    state[OUTPUT_BYTES_KEY] = content
