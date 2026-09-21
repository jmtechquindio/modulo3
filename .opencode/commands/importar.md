# Importar y reconciliar
Ejecuta la importación idempotente y muestra los conteos de reconciliación.

```
uv run python scripts/importar_excel.py datos/original/operacion_comercial_app.xlsm datos/procesados/inventario.db
```

Después verifica: Proveedores 75, Productos 1250, Inventario 827, Bajo el mínimo 73, Relaciones inválidas 0. Si algún conteo difiere, conserva el error e investiga antes de continuar.