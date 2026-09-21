from typing import Any

import streamlit as st

from docgen.autofix import autofix_split_placeholders
from docgen.config import (
    DOCX_MIME,
    fixed_filename,
    format_variable_label,
    generated_filename,
)
from docgen.renderer import render_docx
from docgen.template_service import TemplateAnalysis
from docgen.ui.components import (
    render_file_meta,
    render_how_it_works,
    render_issue_summary,
    render_ready_callout,
    render_result,
    render_section_heading,
    render_stepper,
    render_variable_list,
)
from docgen.ui.state import (
    OUTPUT_BYTES_KEY,
    UPLOAD_REVISION_KEY,
    store_fixed_template,
    store_output,
)

LONG_TEXT_HINTS = (
    "comentario",
    "comments",
    "descripcion",
    "description",
    "detalle",
    "notas",
    "notes",
    "observaciones",
)


def replacement_widget_key() -> str:
    revision = st.session_state.get(UPLOAD_REVISION_KEY, 0)
    return f"smart_docs.replacement_uploader.{revision}"


def render_upload_card(
    *,
    widget_key: str,
    replacing: bool = False,
) -> Any | None:
    with st.container(border=True):
        st.markdown('<span class="sd-primary-card"></span>', unsafe_allow_html=True)
        render_section_heading(
            "Nueva plantilla" if replacing else "Paso 1",
            "Sustituye la plantilla" if replacing else "Carga tu plantilla",
            (
                "Selecciona otro archivo .docx para reiniciar el flujo."
                if replacing
                else "Selecciona un archivo .docx con variables como {{ cliente }}."
            ),
        )
        upload = st.file_uploader(
            "Plantilla Word",
            type=("docx",),
            key=widget_key,
            label_visibility="collapsed",
            help="Tamaño máximo permitido por la configuración de Streamlit.",
        )
        if upload is not None:
            render_file_meta(upload.name, upload.size)
        return upload


def render_initial_state() -> Any | None:
    render_stepper(1)
    upload_col, info_col = st.columns((1.55, 1), gap="large")

    with upload_col:
        upload = render_upload_card(widget_key="smart_docs.initial_uploader")

    with info_col:
        with st.container(border=True):
            st.markdown(
                '<span class="sd-side-card"></span>',
                unsafe_allow_html=True,
            )
            render_section_heading(
                "Flujo guiado",
                "Cómo funciona",
                "Un proceso corto, trazable y pensado para reducir errores manuales.",
            )
            render_how_it_works()

    return upload


def _render_issue_details(analysis: TemplateAnalysis) -> None:
    for issue in analysis.issues:
        with st.expander(f"{{{{ {issue.variable} }}}} · {issue.location}"):
            st.caption("Vista previa del párrafo")
            st.write(issue.paragraph_preview)
            st.caption("Fragmentos detectados")
            st.code(" | ".join(issue.run_texts), language=None)


def render_validation_state(
    analysis: TemplateAnalysis,
    template_bytes: bytes,
    source_name: str,
) -> Any | None:
    render_stepper(2)
    left, right = st.columns((1.55, 1), gap="large")

    with left:
        with st.container(border=True):
            st.markdown(
                '<span class="sd-primary-card"></span>',
                unsafe_allow_html=True,
            )
            render_section_heading(
                "Revisión de plantilla",
                "Hay campos fragmentados",
                "Revisa el diagnóstico o aplica la reparación automática.",
            )
            render_issue_summary(analysis.issues)
            _render_issue_details(analysis)

            action_col, download_col = st.columns(2)
            with action_col:
                if st.button(
                    "Reparar automáticamente",
                    type="primary",
                    use_container_width=True,
                ):
                    fixed_bytes, merge_count = autofix_split_placeholders(
                        template_bytes
                    )
                    store_fixed_template(st.session_state, fixed_bytes)
                    st.toast(
                        f"Plantilla reparada: {merge_count} correcciones.",
                        icon="✅",
                    )
                    st.rerun()

            with download_col:
                st.download_button(
                    "Descargar copia actual",
                    data=template_bytes,
                    file_name=fixed_filename(source_name),
                    mime=DOCX_MIME,
                    use_container_width=True,
                )

    with right:
        return render_upload_card(
            widget_key=replacement_widget_key(),
            replacing=True,
        )


def render_empty_variables_state() -> Any | None:
    render_stepper(2)
    left, right = st.columns((1.55, 1), gap="large")

    with left:
        with st.container(border=True):
            st.markdown(
                '<span class="sd-primary-card"></span>',
                unsafe_allow_html=True,
            )
            render_section_heading(
                "Revisión de plantilla",
                "No encontramos campos rellenables",
                "Añade variables simples a tu documento y vuelve a cargarlo.",
            )
            st.warning(
                "Utiliza el formato {{ nombre_variable }} y evita espacios "
                "o estilos distintos dentro del marcador."
            )

    with right:
        return render_upload_card(
            widget_key=replacement_widget_key(),
            replacing=True,
        )


def render_unreadable_state() -> Any | None:
    render_stepper(2)
    st.error(
        "No hemos podido leer el archivo. Comprueba que sea un documento "
        "Word .docx válido y vuelve a intentarlo."
    )
    return render_upload_card(
        widget_key=replacement_widget_key(),
        replacing=True,
    )


def _field_widget(variable: str) -> str:
    label = format_variable_label(variable)
    widget_key = f"smart_docs.field.{variable}"
    help_text = f"Variable de plantilla: {{{{ {variable} }}}}"
    lowered = variable.lower()

    if any(hint in lowered for hint in LONG_TEXT_HINTS):
        return st.text_area(
            label,
            key=widget_key,
            help=help_text,
            height=112,
        )

    return st.text_input(
        label,
        key=widget_key,
        help=help_text,
    )


def _render_content_form(template_bytes: bytes, variables: tuple[str, ...]) -> None:
    with st.form("smart_docs.content_form", border=False):
        context: dict[str, str] = {}
        field_columns = st.columns(2, gap="medium")
        for index, variable in enumerate(variables):
            with field_columns[index % 2]:
                context[variable] = _field_widget(variable)

        submitted = st.form_submit_button(
            "Generar documento",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    try:
        output_bytes = render_docx(template_bytes, context)
    except Exception as exc:
        st.error(
            "No se ha podido generar el documento. "
            "Revisa que la plantilla sea válida."
        )
        with st.expander("Detalles técnicos"):
            st.code(str(exc), language=None)
    else:
        store_output(st.session_state, output_bytes)
        st.rerun()


def render_form_state(
    analysis: TemplateAnalysis,
    template_bytes: bytes,
    source_name: str,
) -> Any | None:
    has_output = OUTPUT_BYTES_KEY in st.session_state
    render_stepper(4 if has_output else 3)
    form_col, summary_col = st.columns((1.65, 1), gap="large")

    with form_col:
        with st.container(border=True):
            st.markdown(
                '<span class="sd-primary-card"></span>',
                unsafe_allow_html=True,
            )
            render_section_heading(
                "Paso 3",
                "Completa el contenido",
                "Los campos se han creado automáticamente desde la plantilla.",
            )
            _render_content_form(template_bytes, analysis.variables)

    with summary_col:
        with st.container(border=True):
            st.markdown(
                '<span class="sd-side-card"></span>',
                unsafe_allow_html=True,
            )
            render_section_heading(
                "Resumen",
                "Plantilla preparada",
                "La estructura ha superado las comprobaciones previas.",
            )
            render_ready_callout(len(analysis.variables))
            st.markdown("##### Variables detectadas")
            render_variable_list(analysis.variables)

        if has_output:
            output_name = generated_filename(source_name)
            with st.container(border=True):
                st.markdown(
                    '<span class="sd-result-card"></span>',
                    unsafe_allow_html=True,
                )
                render_result(output_name)
                st.download_button(
                    "Descargar documento",
                    data=st.session_state[OUTPUT_BYTES_KEY],
                    file_name=output_name,
                    mime=DOCX_MIME,
                    type="primary",
                    use_container_width=True,
                )

        return render_upload_card(
            widget_key=replacement_widget_key(),
            replacing=True,
        )
