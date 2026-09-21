# Revisar
Revisa el cumplimiento del alcance, la reconciliación y la evidencia.

1. Revisa los conteos en `docs/reporte_importacion.md`.
2. Revisa que el XLSM original esté intacto (md5 contra el respaldo externo).
3. Confirma que ninguna herramienta escriba inventario.
4. Ejecuta `uv run pytest` y revisa `logs/`.