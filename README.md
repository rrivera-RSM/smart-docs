# DocGen (MVP)

Generador local de documentos **.docx** a partir de **plantillas Word** usando sintaxis **Jinja2** (`{{ variable }}`), con una UI en **Streamlit**.

## Requisitos

- Python 3.11+
- Poetry

## Instalación

```bash
poetry install
```

## Ejecutar la app

```bash
poetry run streamlit run src/docgen/app.py
```

## Cómo crear la plantilla DOCX

- Usa variables **simples** en snake_case: `{{ nombre_y_apellidos }}`, `{{ dni }}`, `{{ salario_neto }}`.
- Importante: `{{ variable }}` debe quedar en el **mismo run** (Word puede partir el texto si aplicas formato dentro del placeholder). Si se parte, la sustitución puede fallar. Consulta el validador incluido.
- (Avanzado, para futuro) docxtpl soporta tags especiales `{%p %}`, `{%tr %}`, `{%tc %}`, `{%r %}` para controlar párrafos/filas/celdas/runs.

## Qué incluye este proyecto

- `extractor.py`: extrae variables del template (docxtpl + fallback por regex).
- `validator.py`: detecta placeholders partidos en runs.
- `renderer.py`: renderiza el docx final.
- `app.py`: Streamlit UI (upload → form → render → download).

## Notas

- La descarga usa `st.download_button` devolviendo `bytes` del docx generado.
