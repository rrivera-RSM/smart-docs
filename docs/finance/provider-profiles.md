# Perfiles de proveedor

Un perfil describe cómo reconocer y leer un formato de factura digital. Es JSON
validado: no contiene Python, JavaScript ni ningún otro código ejecutable.

## Ubicación y precedencia

- `provider_profiles/*.json`: perfiles base incluidos con el producto.
- `data/finance/providers/*.json`: perfiles creados desde la interfaz.

El catálogo combina ambos directorios por `id`. Un perfil local prevalece
sobre el base con el mismo identificador. Los JSON locales inválidos se ignoran
al listar para que un archivo corrupto no impida arrancar toda la aplicación.

## Flujo de alta

1. Abrir `/finance/proveedores`.
2. Cargar un perfil JSON o partir de **Cargar ejemplo**.
3. Cambiar ID, nombre, detección, páginas y patrones.
4. Añadir una factura PDF real del proveedor.
5. Probar el perfil.
6. Comprobar detección, líneas, base imponible y conciliación.
7. Guardar y activar.

La prueba no persiste nada. Guardar escribe primero un archivo temporal y
después reemplaza el destino.

## Estructura

```json
{
  "schema_version": 1,
  "id": "proveedor-demo",
  "name": "Proveedor Demo",
  "description": "Factura digital de servicios.",
  "detection": {
    "all_terms": ["PROVEEDOR DEMO", "FACTURA"],
    "page_limit": 2
  },
  "header": {
    "page": 0,
    "invoice_number": {
      "pattern": "Factura\\s+(?P<value>[A-Z0-9-]+)",
      "group": "value",
      "required": true
    },
    "invoice_date": {
      "pattern": "Fecha\\s+(?P<value>\\d{2}/\\d{2}/\\d{4})"
    },
    "taxable_base": {
      "pattern": "Base imponible\\s+(?P<value>[0-9.,]+)"
    },
    "invoice_total": {
      "pattern": "Total\\s+(?P<value>[0-9.,]+)"
    }
  },
  "lines": {
    "mode": "flat",
    "page": 1,
    "row_pattern": "^(?P<service>.+?)\\s+(?P<quantity>[0-9.,]+)\\s+(?P<unit_price>[0-9.,]+)\\s+(?P<amount>[0-9.,]+)$"
  }
}
```

Los campos de cabecera `customer_code`, `customer_name`, `tax_rate` y
`tax_amount` son opcionales en el esquema. Si se omiten, el dominio usa un
valor vacío o cero; la interfaz no debe presentar esa ausencia como un dato
confirmado.

## Detección

`all_terms` contiene entre 1 y 12 textos. Todos deben aparecer, sin distinguir
mayúsculas, en las primeras `page_limit` páginas. Elegir términos estables y
específicos reduce falsos positivos.

El catálogo prueba perfiles en orden alfabético por nombre. Dos perfiles con
términos demasiado genéricos pueden competir; la solución es mejorar la
detección, no depender del orden.

## Cabecera

Cada campo usa un `RegexCapture`:

| Campo | Uso |
| --- | --- |
| `pattern` | expresión regular, máximo 800 caracteres |
| `group` | grupo con nombre o índice; por defecto `value` |
| `required` | si es `true`, la ausencia invalida la extracción |
| `join_following_line` | concatena la primera línea posterior al match |

`page` es un índice desde cero. Una página inexistente produce un error claro.

## Modos de línea

### `grouped_detail`

Representa documentos con este ciclo:

```text
usuario
  resumen de servicio
  detalle con cantidad, precio e importe
```

Grupos obligatorios:

- `user_pattern`: `user`.
- `summary_pattern`: `service`, `quantity`, `amount`.
- `detail_pattern`: `quantity`, `unit_price`, `amount`.

`service_names` puede limitar los servicios admitidos. Si queda vacío, acepta
cualquier servicio que coincida con el patrón.

### `flat`

Cada fila contiene una línea completa. `row_pattern` exige los grupos
`service`, `quantity`, `unit_price` y `amount`; `user` es opcional.

### Referencia de proyecto

`project_reference` es un grupo opcional tanto en `row_pattern` como en los
patrones de resumen y detalle. Se usa cuando la referencia forma parte de la
misma fila, por ejemplo en una columna `Referencia`:

```json
{
  "row_pattern": "^(?P<project_reference>[0-9]+)\\s+(?P<service>.+?)\\s+(?P<quantity>[0-9.,]+)\\s+(?P<unit_price>[0-9.,]+)\\s+(?P<amount>[0-9.,]+)$"
}
```

Cuando la referencia aparece en una línea anterior al concepto, se puede usar
`project_reference_pattern`. El extractor conserva el último valor visible y
lo asigna a las líneas siguientes, salvo que la propia fila capture otro:

```json
{
  "project_reference_pattern": "\\bRef:\\s*(?:proyecto\\s+)?(?P<project_reference>[0-9]+)\\b"
}
```

Esta configuración cubre rótulos como `Ref:` y `Ref: proyecto`; el patrón de
fila cubre columnas como la de Nacex. Si el documento no muestra una referencia,
el campo queda vacío para revisión. En particular, Lleida.net no recibe un
valor inventado ni derivado del correo del usuario.

## Validaciones de seguridad

- `id` sólo admite minúsculas, números y guiones.
- El esquema rechaza campos desconocidos.
- Las regex se compilan y verifican antes de probar el PDF.
- Los grupos obligatorios deben existir.
- El perfil completo está limitado a 100 KiB en la API.
- El contenido se interpreta como datos; nunca se evalúa.

## Límites

Los perfiles funcionan bien cuando el PDF contiene texto y mantiene una
estructura estable. No resuelven de forma fiable:

- documentos escaneados;
- tablas cuyo orden se pierde al extraer texto;
- formatos con grandes variaciones entre páginas;
- conceptos que requieren clasificación semántica.

Esos casos son candidatos para OCR o IA documental, manteniendo la misma etapa
posterior de normalización, conciliación y moderación humana.
