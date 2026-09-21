#!/usr/bin/env node
// Generate deterministic PPTX fixtures with the bundled Artifact Tool.

import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const { SKILL_DIR, TMP_DIR, RUNTIME_PYTHON, WORKSPACE_DIR } = process.env;
for (const [name, value] of Object.entries({ SKILL_DIR, TMP_DIR, RUNTIME_PYTHON, WORKSPACE_DIR })) {
  if (!value || !path.isAbsolute(value)) {
    throw new Error(`${name} debe ser una ruta absoluta`);
  }
}

const { finalizePresentation, resolvePresentationFont } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

const OUTPUT_DIR = path.join(WORKSPACE_DIR, "tests", "fixtures", "e2e");
const fontFamily = resolvePresentationFont();
const slideSize = { width: 1280, height: 720 };
const expectedSlideSizeEmu = "12192000,6858000";
await fs.mkdir(TMP_DIR, { recursive: true });

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: 25,
    color: "#1F2937",
    autoFit: "shrinkText",
    ...style,
  };
  return shape;
}

function addSlide(presentation, title, body, section, notes = "") {
  const slide = presentation.slides.add();
  slide.background.fill = "#FFFFFF";
  addText(
    slide,
    section.toUpperCase(),
    { left: 76, top: 42, width: 1128, height: 28 },
    { fontSize: 14, bold: true, color: "#2E75B6" },
  );
  addText(
    slide,
    title,
    { left: 76, top: 82, width: 1128, height: 72 },
    { fontSize: 42, bold: true, color: "#111827", autoFit: "none" },
  );
  addText(
    slide,
    body,
    { left: 84, top: 188, width: 1080, height: 410 },
    { fontSize: 25, color: "#1F2937", autoFit: "shrinkText" },
  );
  addText(
    slide,
    "SmartDocs · documento de prueba",
    { left: 84, top: 650, width: 1080, height: 24 },
    { fontSize: 12, color: "#6B7280" },
  );
  slide.speakerNotes.textFrame.setText(notes);
}

function anonymizerPresentation() {
  const presentation = Presentation.create({ slideSize });
  addSlide(
    presentation,
    "Ficha de cliente",
    [
      "Empresa: Norte Azul Consultores S.L.",
      "Representante: Doña Ana López Martín",
      "DNI: 12345678Z",
      "Pasaporte: PA-123456",
      "Correo: ana.lopez@example.com",
    ].join("\n\n"),
    "Identificación",
    "Contacto alternativo: ana.lopez@example.com",
  );
  addSlide(
    presentation,
    "Condiciones económicas",
    [
      "Dirección: Calle Alcalá 85, 28009 Madrid",
      "Teléfono: +34 612 345 678",
      "IBAN: ES91 2100 0418 4502 0005 1332",
      "Importe aprobado: 1.234,56 €",
      "País del proyecto: Portugal",
    ].join("\n\n"),
    "Contrato",
  );
  return presentation;
}

function generatorPresentation() {
  const presentation = Presentation.create({ slideSize });
  addSlide(
    presentation,
    "Propuesta para {{ cliente }}",
    [
      "Representante: {{ representante }}",
      "Importe aprobado: {{ importe }}",
      "",
      "Esta presentación se completa con los valores revisados en SmartDocs.",
    ].join("\n\n"),
    "Propuesta comercial",
    "Preparada para {{ cliente }}",
  );
  return presentation;
}

async function finalizeFixture(presentation, relativePath, slideCount) {
  const finalPath = path.join(OUTPUT_DIR, relativePath);
  const stagingDir = path.join(TMP_DIR, path.basename(relativePath, ".pptx"));
  const candidatePath = path.join(stagingDir, "candidate.pptx");
  const receiptPath = path.join(stagingDir, "validation.json");
  await fs.mkdir(stagingDir, { recursive: true });
  await fs.mkdir(path.dirname(finalPath), { recursive: true });
  await fs.rm(finalPath, { force: true });
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  await finalizePresentation({
    explicitTotalSlideCount: slideCount,
    requiredNativeTableOwnerSlides: [],
    requiredNativeChartOwnerSlides: [],
    workspaceDir: WORKSPACE_DIR,
    candidatePath,
    finalPath,
    pythonExecutable: RUNTIME_PYTHON,
    integrityValidatorPath: path.join(
      SKILL_DIR,
      "container_tools/inspect_presentation_package_integrity.py",
    ),
    layoutValidatorPath: path.join(
      SKILL_DIR,
      "container_tools/inspect_presentation_layout_geometry.py",
    ),
    layoutArgs: [
      "--expected-slide-size-emu",
      expectedSlideSizeEmu,
      "--validate-heading-fit",
    ],
    fontPolicy: { basis: "design", families: [fontFamily] },
    verifyArtifactToolImport: true,
    receiptPath,
  });
  console.log(path.relative(WORKSPACE_DIR, finalPath));
}

await finalizeFixture(
  anonymizerPresentation(),
  path.join("anonymizer", "presentacion_cliente.pptx"),
  2,
);
await finalizeFixture(
  generatorPresentation(),
  path.join("generator", "plantilla_propuesta.pptx"),
  1,
);
