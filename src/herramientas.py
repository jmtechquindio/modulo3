"""Herramientas de consulta del asistente de inventario.

Cada herramienta define entrada, salida, fuente, errores y permisos.
Todas son SOLO LECTURA: ninguna conversación modifica inventario.
Los valores exactos provienen de SQLite; la búsqueda por significado solo
propone candidatos (ver src/buscador.py).
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any

from src.db import conectar, leer_corte


def _errores_argumento(mensaje: str) -> dict[str, Any]:
    return {"estado": "error", "tipo": "argumento_invalido", "mensaje": mensaje}


def _conexion(ruta: str | None = None) -> tuple[sqlite3.Connection, str]:
    conn = conectar(ruta)
    return conn, leer_corte(conn)


def consultar_producto(codigo: str, ruta: str | None = None) -> dict[str, Any]:
    """Entrada: código de producto exacto. Salida: ficha oficial o ausencia."""
    codigo = (codigo or "").strip()
    if not codigo:
        return _errores_argumento("Se requiere un código de producto.")
    conn, corte = _conexion(ruta)
    try:
        fila = conn.execute(
            """SELECT p.codigo, p.nombre, p.categoria, p.proveedor_id, pr.razon_social,
                      p.unidad, p.precio_costo, p.precio_venta, p.fecha_vencimiento
               FROM productos p
               JOIN proveedores pr ON pr.id = p.proveedor_id
               WHERE p.codigo = ?""",
            (codigo,),
        ).fetchone()
        if fila is None:
            return {
                "estado": "no_encontrado",
                "tipo": "producto_inexistente",
                "mensaje": f"No existe el producto {codigo!r} en la base.",
                "fuente": "SQLite · tablas productos y proveedores",
            }
        return {
            "estado": "ok",
            "producto": dict(fila),
            "fuente": "SQLite · tablas productos y proveedores",
            "corte": corte,
        }
    finally:
        conn.close()


def consultar_existencias(codigo: str, ruta: str | None = None) -> dict[str, Any]:
    """Entrada: código. Salida: stock total, mínimo, lotes, ubicación y corte."""
    codigo = (codigo or "").strip()
    if not codigo:
        return _errores_argumento("Se requiere un código de producto.")
    conn, corte = _conexion(ruta)
    try:
        producto = conn.execute(
            "SELECT nombre, categoria FROM productos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if producto is None:
            return {
                "estado": "no_encontrado",
                "tipo": "producto_inexistente",
                "mensaje": f"No existe el producto {codigo!r} en la base.",
                "fuente": "SQLite · tabla productos",
            }
        lotes = conn.execute(
            """SELECT lote, ubicacion, stock, stock_minimo, fecha_vencimiento
               FROM lotes_inventario WHERE producto_codigo = ?
               ORDER BY fecha_vencimiento IS NULL, fecha_vencimiento""",
            (codigo,),
        ).fetchall()
        stock_total = sum(l["stock"] for l in lotes)
        minimo = max((l["stock_minimo"] for l in lotes), default=0)
        return {
            "estado": "ok",
            "codigo": codigo,
            "producto": producto["nombre"],
            "categoria": producto["categoria"],
            "stock_total": stock_total,
            "stock_minimo": minimo,
            "lotes": [dict(l) for l in lotes],
            "corte": corte,
            "fuente": "SQLite · tablas productos y lotes_inventario",
        }
    finally:
        conn.close()


def listar_bajo_minimo(ruta: str | None = None) -> dict[str, Any]:
    """Entrada: ninguna. Salida: productos cuyo stock está por debajo de la política."""
    conn, corte = _conexion(ruta)
    try:
        filas = conn.execute(
            """SELECT p.codigo, p.nombre, p.categoria,
                      COALESCE(SUM(l.stock), 0) AS stock,
                      MAX(l.stock_minimo) AS stock_minimo
               FROM productos p
               JOIN lotes_inventario l ON l.producto_codigo = p.codigo
               GROUP BY p.codigo, p.nombre, p.categoria
               HAVING COALESCE(SUM(l.stock), 0) < MAX(l.stock_minimo)
               ORDER BY stock ASC"""
        ).fetchall()
        return {
            "estado": "ok",
            "total": len(filas),
            "productos": [dict(f) for f in filas],
            "fuente": "SQLite · consulta stock vs stock_minimo",
            "corte": corte,
        }
    finally:
        conn.close()


def listar_proximos_vencer(dias: int, ruta: str | None = None) -> dict[str, Any]:
    """Entrada: horizonte en días. Salida: lotes por vencer y vencidos por separado."""
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        return _errores_argumento("La cantidad de días debe ser un número entero.")
    if dias <= 0:
        return _errores_argumento("La cantidad de días debe ser mayor a cero.")
    conn, corte = _conexion(ruta)
    try:
        corte_dt = dt.date.fromisoformat(corte)
        limite_dt = corte_dt + dt.timedelta(days=dias)
        por_vencer = conn.execute(
            """SELECT l.producto_codigo, p.nombre, l.lote, l.stock, l.fecha_vencimiento,
                      CAST(julianday(l.fecha_vencimiento) - julianday(?) AS INTEGER) AS dias_al_vencimiento
               FROM lotes_inventario l
               JOIN productos p ON p.codigo = l.producto_codigo
               WHERE l.fecha_vencimiento IS NOT NULL
                 AND date(l.fecha_vencimiento) >= date(?)
                 AND date(l.fecha_vencimiento) <= date(?)
               ORDER BY date(l.fecha_vencimiento) ASC""",
            (corte, corte, limite_dt.isoformat()),
        ).fetchall()
        vencidos = conn.execute(
            """SELECT l.producto_codigo, p.nombre, l.lote, l.stock, l.fecha_vencimiento
               FROM lotes_inventario l
               JOIN productos p ON p.codigo = l.producto_codigo
               WHERE l.fecha_vencimiento IS NOT NULL
                 AND date(l.fecha_vencimiento) < date(?)
               ORDER BY date(l.fecha_vencimiento) ASC""",
            (corte,),
        ).fetchall()
        return {
            "estado": "ok",
            "horizonte_dias": dias,
            "por_vencer": [dict(f) for f in por_vencer],
            "vencidos": [dict(f) for f in vencidos],
            "fuente": "SQLite · tabla lotes_inventario (corte reproducible)",
            "corte": corte,
        }
    finally:
        conn.close()


def calcular_reposicion(codigo: str, ruta: str | None = None) -> dict[str, Any]:
    """Entrada: código. Salida: PROPUESTA pendiente reproducible. No registra compras."""
    codigo = (codigo or "").strip()
    if not codigo:
        return _errores_argumento("Se requiere un código de producto.")
    conn, corte = _conexion(ruta)
    try:
        fila = conn.execute(
            """SELECT p.codigo, p.nombre,
                      COALESCE(SUM(l.stock), 0) AS existencias,
                      MAX(l.stock_minimo) AS stock_minimo
               FROM productos p
               LEFT JOIN lotes_inventario l ON l.producto_codigo = p.codigo
               WHERE p.codigo = ?
               GROUP BY p.codigo, p.nombre""",
            (codigo,),
        ).fetchone()
        if fila is None:
            return {
                "estado": "no_encontrado",
                "tipo": "producto_inexistente",
                "mensaje": f"No existe el producto {codigo!r} en la base.",
                "fuente": "SQLite · tablas productos y lotes_inventario",
            }
        existencias = fila["existencias"] or 0
        minimo = fila["stock_minimo"] or 0
        propuesta = max(0, minimo - existencias)
        return {
            "estado": "ok",
            "producto": fila["nombre"],
            "codigo": codigo,
            "existencias": existencias,
            "stock_minimo": minimo,
            "cantidad_propuesta": propuesta,
            "fuente": "SQLite · tablas productos y lotes_inventario",
            "estado_propuesta": "propuesta_pendiente",
            "nota": "Solo es una propuesta. No se registró ninguna compra ni modificación de inventario.",
            "corte": corte,
        }
    finally:
        conn.close()