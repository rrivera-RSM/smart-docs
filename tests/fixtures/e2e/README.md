# Corpus E2E de SmartDocs

Este directorio contiene documentos ficticios y versionados para probar los dos recorridos del producto con archivos reales.

- `anonymizer/contrato_servicios.docx`: cuerpo, tabla, cabecera, pie, datos repetidos, pasaporte e identificadores con checksum.
- `anonymizer/factura_proveedor.pdf`: PDF digital con texto posicionable.
- `anonymizer/formulario_alta_escaneado.pdf`: PDF raster sin capa de texto para forzar OCR local.
- `anonymizer/presentacion_cliente.pptx`: texto en diapositivas y notas del presentador.
- `generator/`: una plantilla con las mismas variables para DOCX, PDF y PPTX.
- `manifest.json`: contrato de datos esperados que consumen las pruebas parametrizadas.

Los datos no pertenecen a personas o empresas reales. Los fixtures se regeneran con los runtimes de artefactos empaquetados:

    python scripts/generate_e2e_fixtures.py --format docx
    python scripts/generate_e2e_fixtures.py --format pdf
    node scripts/generate_e2e_pptx_fixtures.mjs

La prueba rápida excluye OCR:

    SMARTDOCS_NER_MODE=rules PYTHONPATH=src:. .venv/bin/python -m pytest -m "not slow"

La suite completa, la cobertura, el typecheck y el build se ejecutan con:

    ./scripts/check.sh

