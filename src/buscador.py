"""Búsqueda por significado.

Regla: la búsqueda por significado encuentra CANDIDATOS; SQL confirma los hechos.
Este módulo devuelve candidatos con puntuación basada en coincidencia de tokens
sobre nombre, categoría y proveedor. Nunca presenta una coincidencia aproximada
como un hecho exacto: cada candidato debe confirmarse con las herramientas SQL
(src/herramientas.py) antes de citar valores.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.db import conectar

SINONIMOS: dict[str, tuple[str, ...]] = {
    "clavos": ("clavo", "punta"),
    "martillo": ("martillar", "herramienta de golpe"),
    "tornillo": ("tornilleria", "tuerca", "perno"),
    "ferreteria": ("ferreteria", "herramienta"),
    "sellador": ("silicona", "silicón", "sellante"),
    "silicona": ("sellador", "sellante"),
    "candado": ("seguridad", "cerradura"),
    "pintura": ("esmalte", "vinilo", "laca"),
    "bateria": ("batería", "pila", "acumulador"),
}

STOPWORDS = {
    "para", "para", "de", "del", "el", "la", "los", "las", "un", "una",
    "unos", "unas", "que", "con", "por", "en", "al", "cuanto", "cuanto",
    "hay", "quiero", "necesito", "productos", "producto", "buscar", "usar",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower()


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{2,}", _normalizar(texto)) if t not in STOPWORDS}


def _expandir(texto: str) -> set[str]:
    base = _tokens(texto)
    singular: set[str] = set()
    for token in base:
        if token.endswith("es") and len(token) > 4:
            singular.add(token[:-2])
        elif token.endswith("s") and len(token) > 3:
            singular.add(token[:-1])
    base |= singular
    extra: set[str] = set()
    for token in base:
        extra.update(SINONIMOS.get(token, ()))
    return base | extra


def buscar_productos(texto: str, limite: int = 8, ruta: str | None = None) -> dict[str, Any]:
    """Entrada: texto libre (nombre aproximado, categoría, uso, sinónimos).

    Salida: lista de candidatos con puntuación y campos para confirmar en SQL.
    """
    texto = (texto or "").strip()
    if not texto:
        return {
            "estado": "error",
            "tipo": "argumento_invalido",
            "mensaje": "Se requiere un texto de búsqueda.",
        }
    terminos = _expandir(texto)
    conn = conectar(ruta)
    try:
        filas = conn.execute(
            """SELECT codigo, nombre, categoria,
                      precio_venta,
                      (SELECT COALESCE(SUM(l.stock), 0)
                       FROM lotes_inventario l WHERE l.producto_codigo = p.codigo) AS stock
               FROM productos p
               ORDER BY nombre ASC"""
        ).fetchall()
    finally:
        conn.close()

    candidatos: list[dict[str, Any]] = []
    for f in filas:
        nombre_n = _normalizar(f["nombre"])
        nombre_t = set(re.findall(r"[a-z0-9]{2,}", nombre_n))
        categoria_t = set(re.findall(r"[a-z0-9]{2,}", _normalizar(f["categoria"] or "")))
        puntos = len(terminos & nombre_t) * 3 + len(terminos & categoria_t) * 2
        if len(terminos & nombre_t) > 0 or texto.strip().lower() in nombre_n:
            if texto.strip().lower() in nombre_n:
                puntos += 5
            candidatos.append(
                {
                    "codigo": f["codigo"],
                    "nombre": f["nombre"],
                    "categoria": f["categoria"],
                    "stock": f["stock"],
                    "puntuacion": puntos,
                    "es_candidato": True,
                    "confirmacion": f"consultar_producto('{f['codigo']}') o consultar_existencias('{f['codigo']}')",
                }
            )
    candidatos.sort(key=lambda c: c["puntuacion"], reverse=True)
    return {
        "estado": "ok",
        "busqueda": texto,
        "candidatos": candidatos[:limite],
        "total_candidatos": len(candidatos),
        "regla": "Los candidatos son aproximados. Confirma códigos y cantidades con SQLite (herramientas exactas) antes de usarlos como hechos.",
        "fuente": "SQLite · índice de nombres y categorías + coincidencia de significado",
    }