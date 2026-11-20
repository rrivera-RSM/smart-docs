# Imputación de gastos en SmartDocs

Finance Imputer es la tercera herramienta de SmartDocs. El código del dominio
mantiene el paquete `finance_imputer`, pero la web, la API y la autenticación
se ejecutan dentro de SmartDocs.

## Recorrido y rutas

| Función | Web | API |
| --- | --- | --- |
| Cargar, moderar y exportar | `/finance` | `/api/finance/invoices/*` |
| Probar y guardar proveedores | `/finance/proveedores` | `/api/finance/providers*` |
| Política de acceso y usuarios observados | `/finance/webadmin` | `/api/finance/admin/access-overview` |
| Identidad observada | — | `/api/finance/me` |

El navegador utiliza el BFF de SmartDocs. La sesión Microsoft y el token de
API se gestionan con la configuración `SMARTDOCS_*` y `NEXTAUTH_*` existente;
no se necesita un segundo login ni otro registro de aplicación para Finance.
Todas las rutas de Finance se montan con la misma dependencia de autenticación
que las otras herramientas. WebAdmin es informativo: no concede ni revoca
acceso y no consulta un directorio completo de empleados.

## Código y responsabilidades

- `src/finance_imputer/`: modelos, perfiles, extracción, conciliación y Excel.
- `apps/api/finance/`: rutas, contratos HTTP, serializadores y sesiones.
- `apps/web/src/features/finance/`: pantallas y componentes de la herramienta.
- `apps/web/app/finance/`: rutas Next.js dentro del shell compartido.
- `provider_profiles/`: perfiles base versionados.
- `tests/finance/`: pruebas de dominio y de integración con SmartDocs.

Los importes se calculan con `Decimal`; las referencias de proyecto son
identificadores de texto. Un campo ausente o ambiguo queda pendiente de
revisión. Lleida.net conserva su comportamiento: no inventa referencias de
proyecto que no figuran en la factura.

## Configuración y persistencia

`FINANCE_IMPUTER_TOLERANCE_PERCENTAGE` fija la tolerancia porcentual de
conciliación (por defecto `0.10` %). Se conserva este nombre para facilitar
la transición desde la aplicación independiente.

Los perfiles de usuario se guardan por defecto en `data/finance/providers/`.
Puede cambiarse con `FINANCE_IMPUTER_PROVIDER_DIR`. Los perfiles con un ID
igual a uno incluido tienen prioridad sobre el perfil base.

El registro informativo de usuarios se mantiene bajo `data/finance/access/`.
Docker Compose utiliza el volumen `finance-data`, montado en `/app/data/finance`:
permite persistencia aun con el sistema de archivos del contenedor en modo
de sólo lectura. No eliminar el volumen si se quieren conservar los perfiles.

Las sesiones de factura viven en memoria durante 60 minutos. Un reinicio las
pierde y el despliegue debe usar un solo worker mientras no exista un almacén
compartido. Los PDFs subidos no se guardan por defecto y el Excel se genera
para descargarlo.

## Ejecutar y comprobar

Usar el entorno y comandos normales de SmartDocs:

```bash
pip install -r requirements-api.txt -r requirements-test.txt
./scripts/dev.sh
```

Los puertos habituales son 3050 para web y 8050 para API. En producción
mantener la autenticación corporativa activada. Para una comprobación local
sin credenciales, el script carga `.env` y sus valores prevalecen. Para
omitirlo sólo en esa comprobación local, usar
`SMARTDOCS_ENV_FILE=/dev/null SMARTDOCS_AUTH_ENABLED=false NEXTAUTH_SECRET="$(openssl rand -hex 32)" ./scripts/dev.sh`.
El secreto temporal permite inicializar el middleware de sesión de NextAuth
incluso con el login desactivado; no se guarda en el proyecto.

```bash
SMARTDOCS_AUTH_ENABLED=false SMARTDOCS_NER_MODE=rules PYTHONPATH=src:. \
  .venv/bin/python -m pytest tests/finance
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

Los flags PDF/OCR del generador y anonimizador no controlan la lectura nativa
de facturas digitales de Finance. El PDF sigue siendo el único formato de
entrada de esta herramienta, con límite de 15 MiB por sesión.

## Perfiles y alcance

El motor usa perfiles JSON declarativos `grouped_detail` o `flat`; valida el
esquema, los patrones y los identificadores antes de guardarlos. La pantalla
de proveedores permite probar un perfil con un PDF de muestra y comprobar
su conciliación antes de activarlo.

El [formato de perfiles](provider-profiles.md) documenta grupos obligatorios,
captura de referencias de proyecto y unión de líneas.

La migración conserva el alcance probado del proyecto original. La PoC de
Docling permanece aislada del extractor de producción, sin cargar modelos
ni añadir dependencias VLM al arranque de la API. No se promete extracción
automática de cualquier proveedor sin perfil ni OCR para PDFs escaneados.
Los tres Excel de referencia preparados anteriormente son material de
validación; no implican que existan perfiles productivos para esos formatos.

El script de evaluación se conserva como
`scripts/poc_finance_docling_extract.py`. Ejecutarlo con `--help` muestra sus
opciones. La extracción VLM necesita un entorno opcional con Docling/NuExtract;
no está incluida en el proceso normal de SmartDocs ni se descargan sus pesos
durante esta migración. Las pruebas de la PoC usan respuestas simuladas.

Sólo se exportan líneas aceptadas. Si quedan líneas pendientes, la API exige
confirmación explícita antes de descartarlas de la sesión y generar el Excel.

## Continuidad y reversibilidad

El proyecto hermano `finance-imputer` se conserva como respaldo sin borrarlo.
SmartDocs contiene su propia copia del dominio y no requiere rutas, imports
o servidores del proyecto anterior. No se han trasladado secretos, PDFs de
clientes, Excel generados, entornos virtuales ni historiales de acceso.

Los perfiles locales que se creen en el proyecto anterior deben revisarse y
copiarse a `data/finance/providers/` antes de retirar definitivamente ese
proyecto. Los cambios posteriores deben mantenerse en SmartDocs para evitar
que evolucionen dos implementaciones del mismo módulo.
