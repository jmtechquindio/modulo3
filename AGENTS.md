# AGENTS.md — Inventario Inteligente (Módulo 3)

## Alcance del proyecto

Asistente de inventario de solo lectura basado en `operacion_comercial_app.xlsm`.
Migra únicamente las hojas autorizadas a SQLite y expone herramientas de consulta.

## Reglas obligatorias

- Trabaja primero en modo Plan. No implementes hasta que el usuario apruebe el plan.
- No modifiques el Excel original (`datos/original/operacion_comercial_app.xlsm`).
- No inventes datos ausentes. Ante un dato faltante, declara que no existe o lo envía a pendientes.
- Usa SQL para valores exactos. La búsqueda por significado solo encuentra candidatos; SQL confirma los hechos.
- Ejecuta las pruebas después de modificar código (`uv run pytest`).
- No escribas ni modifiques inventario desde una conversación. Ninguna conversación modifica existencias.
- Respeta el alcance del proyecto: no registrar ventas, compras, ni migrar otras hojas (Clientes, Ventas, Libro diario, etc.).
- No ejecutes macros del Excel ni abras Excel para migrar.
- Una prueba fallida no se oculta: conserva el error, investiga la causa y corrige lo necesario.

## Estructura del proyecto

```
inventario-inteligente/
├── AGENTS.md
├── .opencode/{agents,skills,commands}/
├── datos/{original,procesados}/
├── docs/
├── scripts/
├── src/
├── tests/
└── logs/
```

## Comandos estándar

- `uv sync` — instala dependencias.
- `uv run python scripts/importar_excel.py datos/original/operacion_comercial_app.xlsm datos/procesados/inventario.db` — migración idempotente y reconciliación.
- `uv run pytest` — pruebas.
- `uv run python -m src.app` — asistente CLI.

## Definición de terminado

El proyecto se declara terminado solo si los cuatro comandos anteriores se ejecutan
sin errores desde la raíz del proyecto y los conteos de reconciliación coinciden.