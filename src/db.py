"""Acceso a la base SQLite del asistente de inventario."""

from __future__ import annotations

import sqlite3
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
BASE_POR_DEFECTO = RAIZ_PROYECTO / "datos" / "procesados" / "inventario.db"
ORIGEN_POR_DEFECTO = RAIZ_PROYECTO / "datos" / "original" / "operacion_comercial_app.xlsm"

FECHA_CORTE = "2026-09-04"


def conectar(ruta: str | Path | None = None) -> sqlite3.Connection:
    """Abre una conexión a la base. Por defecto usa datos/procesados/inventario.db."""
    destino = Path(ruta) if ruta else BASE_POR_DEFECTO
    if destino.parent and not destino.parent.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(destino)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def leer_corte(conn: sqlite3.Connection, conn_apertura=None) -> str:
    """Devuelve la fecha de corte reproducible de la base (por defecto la del proyecto)."""
    try:
        fila = conn.execute(
            "SELECT valor FROM metadata WHERE clave = 'fecha_corte'"
        ).fetchone()
        if fila:
            return fila["valor"]
    except sqlite3.Error:
        pass
    return FECHA_CORTE