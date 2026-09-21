---
name: migrar-excel-sqlite
description: Método reutilizable para migrar las hojas autorizadas del XLSM a SQLite de forma idempotente y transaccional.
---

# Migración Excel → SQLite

1. Valida que exista `datos/original/operacion_comercial_app.xlsm`. Si no existe, detente y pídelo.
2. Lee las hojas `Proveedores`, `Productos` e `Inventario` con encabezados en fila 4 y datos desde fila 5.
3. Valida columnas requeridas: si falta una, detén la carga y explica cómo corregirla.
4. Crea las tablas `proveedores`, `productos`, `lotes_inventario` (ver `docs/esquema.md`) con restricciones.
5. Importa dentro de una transacción usando una base temporal; reemplaza la final solo si la carga completa es válida.
6. Registra la procedencia (archivo, hoja, fila) en la tabla `importaciones`.
7. Las filas inconsistentes van a `pendientes`/`errores`; no se completan por intuición.
8. Reporta conteos y reconciliación. Una segunda ejecución no debe duplicar registros.