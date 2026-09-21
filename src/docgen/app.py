from pathlib import Path
import sys
from typing import Any

import streamlit as st

# Streamlit executes this file outside package mode when launched by path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docgen.config import APP_NAME, LOGO_PATH
from docgen.template_service import analyze_template
from docgen.ui.components import (
    render_brandbar,
    render_footer,
    render_hero,
)
from docgen.ui.state import (
    SOURCE_NAME_KEY,
    TEMPLATE_BYTES_KEY,
    sync_uploaded_template,
)
from docgen.ui.styles import inject_styles
from docgen.ui.views import (
    render_empty_variables_state,
    render_form_state,
    render_initial_state,
    render_unreadable_state,
    render_validation_state,
)


def _configure_page() -> None:
    page_icon = str(LOGO_PATH) if LOGO_PATH.exists() else "📄"
    st.set_page_config(
        page_title=f"{APP_NAME} · RSM",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def _sync_replacement(upload: Any | None) -> None:
    if upload is None:
        return

    sync_uploaded_template(
        st.session_state,
        upload.name,
        upload.getvalue(),
    )
    st.rerun()


def _get_working_template() -> tuple[bytes, str] | None:
    if TEMPLATE_BYTES_KEY in st.session_state:
        return (
            st.session_state[TEMPLATE_BYTES_KEY],
            st.session_state[SOURCE_NAME_KEY],
        )

    upload = render_initial_state()
    if upload is None:
        return None

    template_bytes = sync_uploaded_template(
        st.session_state,
        upload.name,
        upload.getvalue(),
    )
    return template_bytes, upload.name


def main() -> None:
    _configure_page()
    inject_styles()
    render_brandbar(LOGO_PATH)
    render_hero()

    working_template = _get_working_template()
    if working_template is None:
        render_footer()
        return

    template_bytes, source_name = working_template

    try:
        analysis = analyze_template(template_bytes)
    except Exception:
        replacement = render_unreadable_state()
    else:
        if analysis.issues:
            replacement = render_validation_state(
                analysis,
                template_bytes,
                source_name,
            )
        elif not analysis.variables:
            replacement = render_empty_variables_state()
        else:
            replacement = render_form_state(
                analysis,
                template_bytes,
                source_name,
            )

    _sync_replacement(replacement)
    render_footer()


if __name__ == "__main__":
    main()
