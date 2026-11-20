#!/usr/bin/env python3
"""Ejecuta la PoC aislada de extracción de facturas con Docling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from finance_imputer.extractors.docling_poc import (  # noqa: E402
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_PAGES,
    DEFAULT_TIMEOUT_SECONDS,
    DoclingPocError,
    DoclingPocExtractor,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extrae una factura PDF con Docling/NuExtract y genera un "
            "InvoiceDraft JSON, sin modificar el flujo actual de la aplicación."
        )
    )
    parser.add_argument("invoice", type=Path, help="Ruta de la factura PDF")
    parser.add_argument(
        "--output",
        type=Path,
        help="Archivo JSON de salida. Si se omite, se escribe en stdout.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps", "xpu"),
        default="auto",
        help="Dispositivo del modelo (por defecto: auto)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Máximo de páginas a procesar (por defecto: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--max-file-mb",
        type=float,
        default=DEFAULT_MAX_FILE_BYTES / (1024 * 1024),
        help="Tamaño máximo del PDF en MiB (por defecto: 15)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Tiempo máximo en segundos (por defecto: {DEFAULT_TIMEOUT_SECONDS:g})",
    )
    parser.add_argument(
        "--fail-if-not-ready",
        action="store_true",
        help="Devuelve código 4 si el borrador requiere revisión antes del mapeo.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.invoice.is_file():
        print(f"No existe el PDF: {args.invoice}", file=sys.stderr)
        return 2
    if args.max_pages < 1:
        print("--max-pages debe ser mayor que cero", file=sys.stderr)
        return 2
    if args.max_file_mb <= 0:
        print("--max-file-mb debe ser mayor que cero", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout debe ser mayor que cero", file=sys.stderr)
        return 2

    extractor = DoclingPocExtractor(
        device=args.device,
        max_pages=args.max_pages,
        max_file_bytes=int(args.max_file_mb * 1024 * 1024),
        timeout_seconds=args.timeout,
    )

    started = perf_counter()
    try:
        draft = extractor.extract_path(args.invoice)
    except (DoclingPocError, OSError) as exc:
        print(f"La extracción falló: {exc}", file=sys.stderr)
        return 3

    payload = draft.model_dump(mode="json")
    payload["elapsed_seconds"] = round(perf_counter() - started, 3)
    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"InvoiceDraft escrito en {args.output}", file=sys.stderr)
    else:
        print(output, end="")

    if args.fail_if_not_ready and not draft.validation.ready_for_mapping:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
