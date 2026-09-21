import base64
import html
from collections.abc import Sequence
from pathlib import Path
from textwrap import dedent

import streamlit as st

from docgen.config import APP_NAME
from docgen.validator import SplitPlaceholderIssue


def _html_markup(markup: str) -> str:
    """Remove Python indentation before handing HTML to Markdown."""
    return dedent(markup).strip()


def _image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def render_brandbar(logo_path: Path) -> None:
    logo_uri = _image_data_uri(logo_path)
    logo = (
        f'<img class="sd-brandbar__logo" src="{logo_uri}" alt="RSM">'
        if logo_uri
        else '<strong class="sd-brandbar__name">RSM</strong>'
    )
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-brandbar">
          <div class="sd-brandbar__product">
            {logo}
            <span class="sd-brandbar__divider"></span>
            <span class="sd-brandbar__name">{APP_NAME}</span>
          </div>
          <span class="sd-badge">
            <span class="sd-badge__dot"></span>
            Document automation
          </span>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        _html_markup(
            """
        <section class="sd-hero">
          <p class="sd-hero__eyebrow">Document workspace</p>
          <h1>De plantilla a documento, sin fricción.</h1>
          <p>
            Carga una plantilla Word, revisa automáticamente su estructura y
            completa sus campos desde un flujo seguro y guiado.
          </p>
        </section>
        """
        ),
        unsafe_allow_html=True,
    )


def render_stepper(active_step: int) -> None:
    labels = ("Plantilla", "Validación", "Contenido", "Documento")
    steps = []
    for index, label in enumerate(labels, start=1):
        state_class = ""
        number = str(index)
        if index < active_step:
            state_class = " sd-step--done"
            number = "✓"
        elif index == active_step:
            state_class = " sd-step--active"

        steps.append(
            _html_markup(
                f"""
            <div class="sd-step{state_class}">
              <span class="sd-step__number">{number}</span>
              <span class="sd-step__label">{label}</span>
            </div>
            """
            )
        )

    st.markdown(
        f'<div class="sd-stepper">{"".join(steps)}</div>',
        unsafe_allow_html=True,
    )


def render_section_heading(
    eyebrow: str,
    title: str,
    description: str,
) -> None:
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-section-heading">
          <p class="sd-section-heading__eyebrow">{html.escape(eyebrow)}</p>
          <h2>{html.escape(title)}</h2>
          <p>{html.escape(description)}</p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_file_meta(filename: str, size: int) -> None:
    size_kb = max(1, round(size / 1024))
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-file-meta">
          <span class="sd-file-meta__icon">DOCX</span>
          <div>
            <div class="sd-file-meta__name">{html.escape(filename)}</div>
            <div class="sd-file-meta__size">{size_kb:,} KB · Plantilla Word</div>
          </div>
          <span class="sd-status">Cargada</span>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_how_it_works() -> None:
    items = (
        (
            "Analizamos la plantilla",
            "Localizamos los campos y comprobamos que Word no los haya fragmentado.",
        ),
        (
            "Preparas el contenido",
            "Mostramos un formulario limpio y ordenado a partir de las variables.",
        ),
        (
            "Generamos el documento",
            "Descargas una nueva copia conservando el formato de la plantilla.",
        ),
    )
    content = []
    for index, (title, description) in enumerate(items, start=1):
        content.append(
            _html_markup(
                f"""
            <div class="sd-feature">
              <span class="sd-feature__number">0{index}</span>
              <div>
                <strong>{title}</strong>
                <p>{description}</p>
              </div>
            </div>
            """
            )
        )

    st.markdown(
        f'<div class="sd-feature-list">{"".join(content)}</div>',
        unsafe_allow_html=True,
    )


def render_issue_summary(issues: Sequence[SplitPlaceholderIssue]) -> None:
    issue_count = len(issues)
    suffix = "campo" if issue_count == 1 else "campos"
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-callout">
          <p class="sd-callout__title">
            Hemos detectado {issue_count} {suffix} que necesita revisión
          </p>
          <p class="sd-callout__text">
            Word ha dividido parte del marcador en varios fragmentos.
            Podemos repararlo automáticamente conservando el estilo inicial.
          </p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_ready_callout(variable_count: int) -> None:
    suffix = "campo disponible" if variable_count == 1 else "campos disponibles"
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-callout sd-callout--success">
          <p class="sd-callout__title">Plantilla validada</p>
          <p class="sd-callout__text">
            La estructura es correcta y hemos encontrado
            {variable_count} {suffix}.
          </p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_variable_list(variables: Sequence[str]) -> None:
    chips = "".join(
        f'<span class="sd-variable">{html.escape(variable)}</span>'
        for variable in variables
    )
    st.markdown(
        f'<div class="sd-variable-list">{chips}</div>',
        unsafe_allow_html=True,
    )


def render_result(filename: str) -> None:
    st.markdown(
        _html_markup(
            f"""
        <div class="sd-result">
          <h3>Documento listo</h3>
          <p>
            Se ha generado <strong>{html.escape(filename)}</strong>.
            Ya puedes descargarlo y revisar el resultado final.
          </p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        _html_markup(
            """
        <div class="sd-footer">
          <span>RSM Smart Docs · Herramienta interna</span>
          <span class="sd-footer__security">
            El archivo se procesa durante esta sesión
          </span>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
