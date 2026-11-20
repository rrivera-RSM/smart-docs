# SmartDocs

SmartDocs es una suite interna para automatizar documentos. Este MVP reúne tres
flujos bajo una interfaz web común:

- **Generador**: valida plantillas DOCX, PDF y PPTX con variables simples,
  propone reparaciones para DOCX y genera documentos en el formato de entrada.
- **Anonimizador**: detecta datos estructurados, permite revisión humana y crea
  una copia anonimizada de DOCX, PDF o PPTX.
- **Imputación de gastos**: extrae líneas de facturas PDF, permite moderar
  importes y referencias de proyecto y exporta a Excel las líneas aceptadas.

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
    src/finance_imputer/   extracción, conciliación y exportación de facturas
    provider_profiles/     perfiles declarativos incluidos de proveedores
    apps/api/finance/      rutas de imputación bajo /api/finance
    docs/finance/          arquitectura y operación de imputación de gastos

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

En generador y anonimizador, el despliegue de fase 1 expone DOCX y PPTX.
Sus funciones PDF, OCR de imágenes y WebAdmin permanecen apagadas por defecto:

    SMARTDOCS_FEATURE_PDF=false
    SMARTDOCS_FEATURE_IMAGE_OCR=false
    SMARTDOCS_FEATURE_WEBADMIN=false

Estos flags pertenecen a las herramientas documentales previas. Imputación
de gastos acepta PDFs digitales y mantiene su propia vista informativa de
acceso en `/finance/webadmin`, bajo la autenticación corporativa común.

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

### Autenticación corporativa

La web usa NextAuth con Microsoft Entra ID y solicita el scope delegado
`user_impersonation` de la aplicación registrada para FastAPI. Todas las
operaciones de documentos pasan por el proxy autenticado de Next.js; FastAPI
valida el bearer token y mantiene público únicamente `/api/health`.

Configura estas variables en `.env`:

    SMARTDOCS_AUTH_ENABLED=true
    SMARTDOCS_AZURE_TENANT_ID=
    SMARTDOCS_AZURE_WEB_CLIENT_ID=
    SMARTDOCS_AZURE_WEB_CLIENT_SECRET=
    SMARTDOCS_AZURE_API_CLIENT_ID=
    NEXTAUTH_SECRET=
    NEXTAUTH_URL=

`SMARTDOCS_AZURE_WEB_CLIENT_ID` y
`SMARTDOCS_AZURE_WEB_CLIENT_SECRET` pertenecen al registro de la aplicación
web. `SMARTDOCS_AZURE_API_CLIENT_ID` pertenece al registro de FastAPI, que
debe exponer `api://<client-id>/user_impersonation`. En el registro web añade
ese permiso delegado y configura como URI de redirección
`<NEXTAUTH_URL>/api/auth/callback/azure-ad`.

`NEXTAUTH_SECRET` protege las cookies de sesión y debe ser un valor aleatorio
independiente del secreto de Azure; puede generarse con
`openssl rand -base64 32`. En desarrollo, `scripts/dev.sh` calcula
`NEXTAUTH_URL` cuando se deja vacía. `SMARTDOCS_AUTH_ENABLED=false` se
reserva para pruebas locales y CI sin conexión a Azure.

### Despliegue de fase 1

El despliegue de producción se compone de una imagen FastAPI y otra Next.js. La
API solo se expone a la red interna de Compose y la web se publica, por defecto,
en el puerto `3050`; la API queda disponible localmente en `8050`. El modelo NER
aprobado se descarga y verifica durante el
build de la imagen; el contenedor no descarga modelos en runtime.

    cp .env.example .env
    ./scripts/deploy.sh

Después de completar las variables de autenticación, la interfaz y la API solo admiten DOCX y PPTX,
`/webadmin` responde `404` y PDF/OCR quedan reservados para fase 2. Como las
flags visibles por Next.js se fijan durante el build, cualquier cambio exige
reconstruir las imágenes con `docker compose up --build -d`.

La imagen `web` instala sus dependencias dentro de Linux y genera un build
standalone limpio; no utiliza `node_modules`, `.next` ni archivos `.env` del
equipo desde el que se construye. El script de despliegue solo anuncia éxito
cuando ambos contenedores están saludables. Si no lo consigue en 300 segundos,
devuelve un error y muestra estados y logs. El plazo se puede ajustar con
`SMARTDOCS_DEPLOY_TIMEOUT`.

Si la web queda pendiente, comprobar primero la API: `web` espera a que su
dependencia supere el healthcheck antes de arrancar.

    docker compose ps -a
    docker compose logs --tail=100 api web

Para reconstruir únicamente el frontal con una API ya saludable:

    docker compose build web
    docker compose up -d --no-deps --wait --wait-timeout 60 web

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
no incluye multitenencia, Redis ni auditoría persistente.

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

## Imputación de gastos

Finance Imputer se integra como tercera herramienta en `/finance`. Incluye
carga de un PDF digital, moderación editable y exportación Excel de líneas
aceptadas; `/finance/proveedores` permite probar y guardar perfiles JSON y
`/finance/webadmin` muestra la política de acceso y usuarios observados.

Todo se ejecuta con la web y API de SmartDocs: no necesita otro proceso,
puerto ni registro de aplicación en Entra ID. Los endpoints `/api/finance/*`
usan la misma dependencia de autenticación que generador y anonimizador.

Los perfiles incluidos viven en `provider_profiles/` y los creados desde la
interfaz en `data/finance/providers/`. Docker Compose monta un volumen
`finance-data` para preservar estos perfiles y el registro informativo de
acceso. Las sesiones de factura siguen en memoria con TTL de 60 minutos.

La tolerancia de conciliación se configura con
`FINANCE_IMPUTER_TOLERANCE_PERCENTAGE` (por defecto `0.10` %). La extracción
actual requiere un perfil compatible: Docling sigue siendo una PoC opcional.
No se incorporan PDFs reales, Excel de validación ni secretos del proyecto
original al código de SmartDocs.

Consulta [la guía de integración](docs/finance/README.md) para rutas,
pruebas, persistencia, limitaciones y continuidad del proyecto original.

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
