"""Asistente de inventario (CLI).

Flujo: pregunta del usuario -> identificación de intención -> validación de
argumentos -> ejecución de herramienta -> consulta de datos -> respuesta ->
procedencia/evidencia.

Límite de seguridad: NINGUNA conversación modifica inventario. Las solicitudes
de escritura se rechazan.
"""

from __future__ import annotations

import re
import sys
from typing import Any

from src import buscador, herramientas

PATRON_CODIGO = re.compile(r"\b([A-Z]{2,4}-\d{3,5})\b", re.IGNORECASE)

ACCIONES_ESCRITURA = [
    "registra", "registrar", "actualiza", "actualizar", "modifica",
    "modificar", "aumenta", "agregar", "agrega", "descarga", "descuenta",
    "compra", "comprar", "vende", "vender", "inserta", "insertar",
    "migra clientes", "libro diario", "nuevo lote", "ajustar stock",
]

INTENCIONES = [
    ("bajo_minimo", ["bajo", "mínimo", "reponer primero", "urgente", "por debajo"]),
    ("proximos_vencer", ["vencer", "vencimiento", "vence", "caduca", "caducidad", "expira"]),
    ("vencidos", ["vencido", "vencidos"]),
    ("reposicion", ["reponer", "reposición", "cuánto reponer", "cuanto reponer", "propuesta", "necesito reponer"]),
    ("existencias", ["existencia", "existencias", "stock", "cuánto hay", "cuanto hay", "disponible", "inventario de"]),
    ("producto", ["ficha", "precio", "producto", "código", "codigo", "datos del", "consulta el"]),
    ("buscar", ["buscar", "buscá", "que es", "qué es", "cuáles", "cuales", "encuentra", "hay algún"]),
]


def _clasificar(pregunta: str) -> str:
    q = pregunta.lower()
    for accion in ACCIONES_ESCRITURA:
        if accion in q:
            return "escritura_no_autorizada"
    for intencion, claves in INTENCIONES:
        for clave in claves:
            if clave in q:
                return intencion
    return "buscar"


def _extraer_codigo(pregunta: str) -> str | None:
    m = PATRON_CODIGO.search(pregunta)
    return m.group(1).upper() if m else None


def _extraer_dias(pregunta: str) -> int:
    texto = PATRON_CODIGO.sub(" ", pregunta)  # ignora dígitos dentro de códigos
    m = re.search(r"\b(\d+)\s*(d[ií]as|meses)?\b", texto)
    if not m:
        return 15
    valor = int(m.group(1))
    if m.group(2):
        return valor * 30 if m.group(2).startswith("mes") else valor
    return valor


def _formatear(resultado: dict[str, Any]) -> str:
    estado = resultado.get("estado")
    if estado == "error":
        return f"[{resultado['tipo']}] {resultado['mensaje']}"
    if estado == "no_encontrado":
        return f"[{resultado['tipo']}] {resultado['mensaje']}  · Fuente: {resultado.get('fuente', '-')}"
    if estado == "rechazado":
        return f"[rechazado] {resultado['mensaje']}\nFuente: {resultado.get('fuente', '-')}"
    caso = {
        "consultar_producto": lambda r: (
            f"Producto: {r['producto']['nombre']} ({r['producto']['codigo']})\n"
            f"Categoría: {r['producto']['categoria']}  · Proveedor: {r['producto']['razon_social']}\n"
            f"Precio costo: ${r['producto']['precio_costo']:,.0f}  · Precio venta: ${r['producto']['precio_venta']:,.0f}"
        ),
        "consultar_existencias": lambda r: (
            f"{r['producto']} ({r['codigo']})\n"
            f"Existencias: {r['stock_total']}  · Mínimo: {r['stock_minimo']}\n"
            f"Lotes: " + ", ".join(
                f"{l['lote']} ({l['stock']} u., {l['ubicacion'] or 'sin ubicación'}, vence {l['fecha_vencimiento'] or 'N/A'})"
                for l in r['lotes']
            ) + "\nCorte de datos: " + r["corte"]
        ),
        "listar_bajo_minimo": lambda r: (
            f"{r['total']} productos bajo el mínimo. Los 10 primeros:\n" +
            "\n".join(
                f"- {p['nombre']} ({p['codigo']}, {p['categoria']}) stock {p['stock']} < mínimo {p['stock_minimo']}"
                for p in r['productos'][:10]
            )
        ),
        "listar_proximos_vencer": lambda r: (
            f"Con corte en {r['corte']}:\n"
            f"- Por vencer en {r['horizonte_dias']} días: {len(r['por_vencer'])} lote(s)\n" +
            "\n".join(
                f"  · {v['nombre']} ({v['producto_codigo']}) lote {v['lote']}, vence {v['fecha_vencimiento']} (faltan {v['dias_al_vencimiento']} días)"
                for v in r['por_vencer'][:10]
            ) +
            f"\n- Vencidos (separados del disponible): {len(r['vencidos'])}" +
            ("\n  · " + "\n  · ".join(
                f"{v['nombre']} ({v['producto_codigo']}) lote {v['lote']}, vence {v['fecha_vencimiento']}"
                for v in r['vencidos'][:5]
            ) if r['vencidos'] else "")
        ),
        "calcular_reposicion": lambda r: (
            f"Propuesta de reposición:\n"
            f"Producto: {r['producto']} ({r['codigo']})\n"
            f"Existencias: {r['existencias']}  · Mínimo configurado: {r['stock_minimo']}\n"
            f"Cantidad propuesta: {r['cantidad_propuesta']} unidades\n"
            f"Fuente: {r['fuente']}\n"
            f"Estado: {r['estado_propuesta']}. No se registró ninguna compra."
        ),
        "buscar_productos": lambda r: (
            f"Búsqueda por significado: '{r['busqueda']}' -> {r['total_candidatos']} candidato(s).\n" +
            "\n".join(
                f"- {c['nombre']} ({c['codigo']}, {c['categoria']}) stock {c['stock']}, puntuación {c['puntuacion']} | confirma con {c['confirmacion']}"
                for c in r['candidatos'][:8]
            ) + "\n" + r['regla']
        ),
    }
    return caso.get(resultado.get("herramienta", ""), lambda r: str(r))(resultado) + f"\nFuente: {resultado.get('fuente', '-')}"


def resolver(pregunta: str, ruta: str | None = None) -> dict[str, Any]:
    """Ejecuta el flujo completo de una pregunta y devuelve la evidencia."""
    intencion = _clasificar(pregunta)
    codigo = _extraer_codigo(pregunta)
    dias = _extraer_dias(pregunta)

    if intencion == "escritura_no_autorizada":
        return {
            "estado": "rechazado",
            "intencion": intencion,
            "mensaje": "Operación rechazada: la conversación no está autorizada para escribir o modificar inventario.",
            "herramienta": None,
            "fuente": "Regla de seguridad · AGENTS.md",
        }

    if intencion == "bajo_minimo":
        r = herramientas.listar_bajo_minimo(ruta)
        r["herramienta"] = "listar_bajo_minimo"
        return r

    if intencion in ("proximos_vencer", "vencidos"):
        r = herramientas.listar_proximos_vencer(dias, ruta)
        r["herramienta"] = "listar_proximos_vencer"
        return r

    if intencion == "reposicion" and codigo:
        r = herramientas.calcular_reposicion(codigo, ruta)
        r["herramienta"] = "calcular_reposicion"
        return r
    if intencion == "reposicion":
        return {
            "estado": "rechazado",
            "intencion": intencion,
            "mensaje": "Indica el código del producto para reponer (p. ej. '¿cuánto hay que reponer de FER-0001?').",
            "herramienta": None,
            "fuente": "Validación de argumentos",
        }

    if intencion == "existencias" and codigo:
        r = herramientas.consultar_existencias(codigo, ruta)
        r["herramienta"] = "consultar_existencias"
        return r

    if intencion == "producto" and codigo:
        r = herramientas.consultar_producto(codigo, ruta)
        r["herramienta"] = "consultar_producto"
        return r

    if intencion == "producto" and not codigo:
        return {
            "estado": "rechazado",
            "intencion": intencion,
            "mensaje": "Indica el código del producto (p. ej. 'ficha del producto FER-0001').",
            "herramienta": None,
            "fuente": "Validación de argumentos",
        }

    r = buscador.buscar_productos(pregunta, ruta=ruta)
    r["herramienta"] = "buscar_productos"
    return r


def conversar(pregunta: str, ruta: str | None = None) -> str:
    resultado = resolver(pregunta, ruta)
    num = resultado.get("total")
    resultado_evidencia = {
        "pregunta": pregunta,
        "intencion": resultado.get("intencion", resultado.get("herramienta")),
        "estado": resultado.get("estado"),
        "herramienta": resultado.get("herramienta"),
        "fuente": resultado.get("fuente"),
        "detalle_numérico": num,
    }
    return _formatear(resultado)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(conversar(" ".join(argv)))
        return
    print("Asistente de inventario (Módulo 3). Escribe una pregunta o 'salir'.")
    while True:
        try:
            pregunta = input("> ")
        except EOFError:
            break
        if pregunta.strip().lower() in ("salir", "exit", "quit"):
            break
        print(conversar(pregunta), end="\n\n")


if __name__ == "__main__":
    main()