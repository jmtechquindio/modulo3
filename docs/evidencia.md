# Evidencia del Módulo 3 — Inventario inteligente

## ¿Qué se hizo?
Se construyó `inventario-inteligente/`: arnés de OpenCode (AGENTS.md, agentes de
software/datos/QA, skills y commands), migración idempotente del XLSM a SQLite,
herramientas de solo lectura, búsqueda por significado con confirmación SQL,
asistente CLI y pruebas de casos normales y fallos.

## ¿Con qué datos?
`datos/original/operacion_comercial_app.xlsm` (Comercial La Esquina), copiado
sin modificaciones. Integridad verificado por md5 contra el respaldo externo:
`2689cd52ce9bf462929b600b7d7f1904`. No se abrió Excel ni se ejecutaron macros.

## ¿Qué se importó?
Hojas autorizadas: Proveedores, Productos e Inventario (encabezados fila 4,
datos fila 5), dentro de una transacción sobre archivo temporal. Se conserva
la procedencia (archivo/hoja/fila) en `importaciones`.

## ¿Cuántos registros? (reconciliación)
| Concepto | Obtenido | Esperado | Estado |
|---|---|---|---|
| Proveedores | 75 | 75 | OK |
| Productos | 1250 | 1250 | OK |
| Inventario | 827 | 827 | OK |
| Bajo el mínimo | 73 | 73 | OK |
| Relaciones inválidas | 0 | 0 | OK |

Reporte en `datos/procesados/reporte_importacion.md`.

## ¿Qué errores aparecieron?
Cero. No se fabricaron datos ni duplicados. La segunda ejecución del importador
mantiene los mismos conteos (idempotencia comprobada).

## ¿Cómo se verificaron?
- `uv sync` → OK.
- `uv run python scripts/importar_excel.py ...` → 75/1250/827/73/0 en dos ejecuciones.
- `uv run pytest` → 17 pruebas aprobadas (incluye los 9 casos obligatorios: código válido,
  nombre ambiguo, producto inexistente, stock bajo, lote vencido, proveedor inválido,
  segunda importación, columna ausente y escritura no autorizada).
- `uv run python -m src.app` → respuestas con fuente SQLite y corte reproducible.

## ¿Qué herramientas existen?
`consultar_producto`, `consultar_existencias`, `listar_bajo_minimo`,
`listar_proximos_vencer`, `calcular_reposicion` (en `src/herramientas.py`) y
`buscar_productos` (significado, en `src/buscador.py`). Cada una documenta
entrada, salida, fuente, errores y permisos, y es solo lectura.

## ¿Qué pruebas pasaron?
Ver `logs/pruebas_final.log` y ejecutar `uv run pytest`. Caso crítico: una
búsqueda aproximada nunca se presenta como hecho; se exige confirmación SQL.

## ¿Qué operaciones están prohibidas?
- Registrar ventas o compras. Migrar clientes o libro diario.
- Modificar existencias desde la conversación (rechazado por el asistente).
- Ejecutar macros o reemplazar el Excel.
- Inventar datos ausentes: se declara que no existen o quedan pendientes.

## Definición de terminado
Los cuatro comandos obligatorios se ejecutaron en orden desde la raíz sin errores
(pasos 1-4 anteriores). Ver `logs/ejecucion_final.log`.

## Límites de seguridad
`Ninguna conversación modifica el inventario.` El asistente rechaza escrituras
(intentó "registrar 20 unidades" y fue bloqueado).