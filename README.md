# SmartDocs

SmartDocs es una suite interna para automatizar documentos. Este MVP reúne dos
flujos bajo una interfaz web común:

- **Generador**: valida plantillas DOCX, PDF y PPTX con variables simples,
  propone reparaciones para DOCX y genera documentos en el formato de entrada.
- **Anonimizador**: detecta datos estructurados, permite revisión humana y crea
  una copia anonimizada de DOCX, PDF o PPTX.

La aplicación Streamlit original se mantiene disponible como interfaz legacy.
El frontend principal usa Next.js y comparte el sistema visual corporativo de
People Analytics.

## Arquitectura

    apps/
      api/                 FastAPI, contratos HTTP y sesiones temporales
      web/                 Next.js App Router + React + TypeScript
    src/docgen/
      anonymizer/          detectores y adaptadores DOCX/PDF/PPTX
      ui/                  componentes de la interfaz Streamlit legacy
      template_service.py  orquestación del generador
    tests/                 dominio, API, seguridad y smoke tests

La lógica de documentos no depende del framework web. FastAPI actúa como capa
de transporte y Next.js se ocupa de rutas, navegación, presentación y proxy
local hacia la API.

## Requisitos

- Python 3.11 o superior.
- Node.js 20.9 o superior. Se incluye `.nvmrc` para usar la versión del proyecto.
- LibreOffice es opcional para la previsualización PDF del Streamlit legacy.

## Instalación

Backend:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-api.txt

Para desarrollo y pruebas:

    pip install -r requirements-test.txt

Frontend:

    cd apps/web
    nvm use
    npm install

## Desarrollo

Desde WSL:

    ./scripts/dev.sh

La aplicación estará disponible normalmente en:

    http://127.0.0.1:3050

La API y su documentación interactiva estarán normalmente en:

    http://127.0.0.1:8050/docs

Si alguno de esos puertos está ocupado, el script selecciona automáticamente
el siguiente puerto libre y configura el proxy de Next.js. Las URLs reales se
muestran al arrancar. Los puertos iniciales pueden fijarse con
`SMARTDOCS_WEB_PORT` y `SMARTDOCS_API_PORT`.

### Feature flags del despliegue

El despliegue de fase 1 expone DOCX y PPTX. PDF, OCR de imágenes y WebAdmin
permanecen apagados por defecto:

    SMARTDOCS_FEATURE_PDF=false
    SMARTDOCS_FEATURE_IMAGE_OCR=false
    SMARTDOCS_FEATURE_WEBADMIN=false

Next.js incorpora estos valores durante la compilación y FastAPI los comprueba
en cada subida. Activar únicamente el flag del frontend no permite saltarse la
validación del backend. Para ejecutar localmente la cobertura de fase 2:

    SMARTDOCS_FEATURE_PDF=true \
    SMARTDOCS_FEATURE_IMAGE_OCR=true \
    SMARTDOCS_FEATURE_WEBADMIN=true \
    ./scripts/dev.sh

También pueden iniciarse por separado:

    PYTHONPATH=src:. .venv/bin/uvicorn apps.api.main:app --reload

    cd apps/web
    nvm use
    npm run dev

### Despliegue de fase 1

El despliegue de producción se compone de una imagen FastAPI y otra Next.js. La
API solo se expone a la red interna de Compose y la web se publica, por defecto,
en el puerto `3050`; la API queda disponible localmente en `8050`. El modelo NER
aprobado se descarga y verifica durante el
build de la imagen; el contenedor no descarga modelos en runtime.

    cp .env.example .env
    ./scripts/deploy.sh

Con las variables de ejemplo, la interfaz y la API solo admiten DOCX y PPTX,
`/webadmin` responde `404` y PDF/OCR quedan reservados para fase 2. Como las
flags visibles por Next.js se fijan durante el build, cualquier cambio exige
reconstruir las imágenes con `docker compose up --build -d`.

## Anonimizador

El anonimizador es un pipeline local de anonimización asistida:

1. Carga de un DOCX o PPTX de hasta 15 MB (60 MB expandido para OOXML). PDF se
   conserva detrás de la flag de fase 2.
2. Extracción con localizadores reversibles para Word y PowerPoint, texto con
   coordenadas para PDF digital y OCR local para páginas escaneadas.
3. Detección combinada mediante reglas con checksum, gazetteers locales,
   contexto y NER español orquestado por Presidio.
4. Inspector agrupado con filtros, alias editables, decisiones por grupo y
   hallazgos manuales creados desde el texto extraído.
5. Saneamiento de comentarios, revisiones, propiedades, relaciones y contenido
   oculto; los PDF se reconstruyen desde páginas rasterizadas ya redactadas.
6. Reapertura del resultado, búsqueda estructural y segunda pasada de
   detectores. La descarga solo se habilita si la verificación termina bien.

El perfil `maximum` activa por defecto personas, empresas, países, regiones,
localidades, direcciones, importes, identificadores españoles, datos bancarios,
contacto, fecha de nacimiento y edad contextual. Los alias se asignan por orden
de aparición, por ejemplo `[PERS_01]`, `[EMP_01]` o `[IMP_01]`.

Las imágenes, objetos OLE, gráficos, macros, firmas y referencias no
inspeccionables de DOCX/PPTX bloquean el resultado. El usuario puede eliminarlos
de la copia, pero no conservarlos y descargar un archivo presentado como
seguro. En PDF, una página no vacía sin texto digital que el OCR no pueda leer
se marca como bloqueo no evitable.

La integración PDF/PPTX no usa servicios externos ni licencias comerciales.
Se apoya en el paquete ligero de Docling, PDFium, RapidOCR, pypdf, ReportLab y
OOXML. Los modelos OCR se instalan con las dependencias y no se descargan en
runtime.

### Modelo NER local

La API nunca descarga modelos durante el arranque. Después de instalar las
dependencias hay que preparar una revisión aprobada:

    .venv/bin/python scripts/prepare_ner_model.py

El script descarga el snapshot durante el setup y genera un manifiesto SHA-256.
En ejecución, `SMARTDOCS_NER_MODE=required` verifica versión y checksums antes
de precargar el modelo. Si falta o está alterado, `POST /api/anonymizer/analyze`
responde `503`; no continúa silenciosamente solo con regex.

El repositorio PlanTL/BSC indicado inicialmente ya no permite descarga anónima.
El setup fija temporalmente `raulgdp/roberta-base-bne-capitel-ner`, un modelo
público Apache-2.0 de la misma familia española CAPITEL, en la revisión
`0996689461f0ce247b6c9226c11454a3277f21e3`. Cualquier cambio de modelo exige
actualizar esa revisión y regenerar el manifiesto.

Variables relevantes:

    SMARTDOCS_NER_MODE=required
    SMARTDOCS_NER_MODEL_PATH=.models/roberta-base-bne-capitel-ner-plus
    TRANSFORMERS_OFFLINE=1
    HF_HUB_OFFLINE=1

`SMARTDOCS_NER_MODE=rules` se reserva para la suite determinista de CI.

### API y retención

El ciclo es asíncrono: `analyze` y `apply` devuelven `202`, y el estado se
consulta en `GET /api/anonymizer/{job_id}`. Los trabajos usan una cola local
de concurrencia uno, viven únicamente en memoria y caducan a los 30 minutos.
`DELETE /api/anonymizer/{job_id}` elimina original y resultado inmediatamente.

Los tipos del frontal se generan desde OpenAPI:

    npm --prefix apps/web run generate:api-types

No se registran nombres de archivo, texto, valores detectados ni reemplazos.

### Rendimiento de referencia

En CPU, el benchmark local sintético de 50 páginas tras cargar el modelo tardó
25,88 segundos en análisis y alcanzó aproximadamente 800 MB de RSS máximo. Es
una referencia de desarrollo, no una garantía para todos los DOCX.

### Alcance

El producto se presenta como anonimización asistida. La confirmación humana es
obligatoria y no se promete ausencia absoluta de falsos negativos. El piloto
no incluye autenticación corporativa, multitenencia, Redis ni auditoría
persistente.

## Generador


El frontend Next.js utiliza el mismo contrato para los tres formatos:

1. Carga y validación de una plantilla DOCX, PDF o PPTX.
2. Reparación automática opcional de variables partidas en DOCX.
3. Formulario dinámico con una entrada por variable.
4. Generación y descarga en el formato original.

DOCX conserva la compatibilidad completa con Jinja/docxtpl. En PDF y PPTX la
PoC admite marcadores simples como {{ cliente }}. PPTX sustituye texto sobre
OOXML; PDF reconstruye el resultado como páginas rasterizadas, por lo que la
copia pierde selección de texto y accesibilidad semántica a cambio de eliminar
capas, metadatos y adjuntos ocultos.

## Calidad

Ejecutar toda la validación:

    ./scripts/check.sh

El script ejecuta pytest con cobertura de ramas, exige al menos un 75% sobre el
dominio Python y la API, comprueba los tipos y compila el frontend Next.js para
producción.

La suite distingue reglas puras, integración de adaptadores y recorridos E2E
por API. Los casos marcados como `slow` ejercitan OCR y renderizado:

    SMARTDOCS_NER_MODE=rules PYTHONPATH=src:. .venv/bin/python -m pytest -m "not slow"
    SMARTDOCS_NER_MODE=rules PYTHONPATH=src:. .venv/bin/python -m pytest -m slow

El corpus versionado está en `tests/fixtures/e2e/`. Incluye un contrato DOCX,
un PDF digital, un PDF escaneado, una presentación PPTX y plantillas de
generación para los tres formatos. `manifest.json` contiene los hallazgos,
variables y textos esperados para que ampliar el corpus no requiera duplicar
assertions.

## Streamlit legacy

La interfaz anterior sigue disponible durante la transición:

    streamlit run main.py

Esto permite migrar por fases sin duplicar la lógica de negocio.
