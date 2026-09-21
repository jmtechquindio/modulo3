"""Importador idempotente y transaccional del XLSM de Comercial La Esquina a SQLite.

Uso:
    uv run python scripts/importar_excel.py datos/original/operacion_comercial_app.xlsm datos/procesados/inventario.db

Reglas:
- No modifica el Excel original.
- Lee solo las hojas Proveedores, Productos e Inventario (encabezados fila 4, datos fila 5).
- Crea las tablas relacionadas con restricciones.
- Importa dentro de una transacción sobre un archivo temporal; solo al terminar
  correctamente reemplaza la base final (evita bases parcialmente cargadas).
- Las filas inconsistentes van a importaciones/errores; nunca se completan por intuición.
- Una segunda ejecución no duplica productos ni lotes.
- Genera reporte_importacion.md, errores_importacion.csv y datos/procesados/inventario.db.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import sqlite3
import sys
from pathlib import Path

import openpyxl

HojasAutorizadas = {"Proveedores", "Productos", "Inventario"}
FECHA_CORTE = "2026-09-04"
FECHA_CORTE_DT = dt.date.fromisoformat(FECHA_CORTE)

ENCABEZADOS = {
    "Proveedores": [
        "ID proveedor", "Razón social", "NIT", "Categoría principal", "Contacto",
        "Teléfono", "Celular", "Correo", "Dirección", "Ciudad", "Departamento",
        "Condiciones de pago", "Medio preferido", "Estado",
    ],
    "Productos": [
        "Código", "Nombre", "Categoría", "ID proveedor", "Proveedor", "Unidad",
        "Precio costo", "Precio venta", "Margen %", "Fecha vencimiento",
    ],
    "Inventario": [
        "Código", "Producto", "Categoría", "Proveedor", "Ubicación", "Lote", "Stock",
        "Stock mínimo", "Precio costo", "Valor inventario", "Fecha vencimiento",
        "Días al vencimiento", "Estado", "Último movimiento", "Observaciones",
    ],
}


def fecha_a_texto(valor) -> str | None:
    """Convierte una celda fecha/datetime a YYYY-MM-DD (reproducible)."""
    if valor is None:
        return None
    if isinstance(valor, dt.datetime):
        return valor.date().isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, str) and valor.strip():
        try:
            return dt.date.fromisoformat(valor.strip()).isoformat()
        except ValueError:
            return valor.strip()
    return None


def validar_encabezados(hoja, nombre: str) -> tuple[bool, list[str]]:
    """Valida que los encabezados esperados estén en la fila 4. Devuelve (ok, faltantes)."""
    fila4 = [str(c).strip() if c is not None else "" for c in next(hoja.iter_rows(min_row=4, max_row=4, values_only=True))]
    faltantes = [h for h in ENCABEZADOS[nombre] if h not in fila4]
    if faltantes:
        return False, faltantes
    return True, []


def ecu(a) -> str:
    return "" if a is None else str(a).strip()


def num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def entero(v) -> int | None:
    f = num(v)
    if f is None:
        return None
    return int(f)


def construir_base(origen: Path, destino: Path) -> sqlite3.Connection:
    """Crea archivo temporal, aplica esquema, importa en transacción y reemplaza destino."""

    # --- Validaciones previas a la carga ---
    if not origen.exists():
        sys.exit(f"ERROR: no existe {origen}. Coloca el XLSM en datos/original/ y reintenta.")

    wb = openpyxl.load_workbook(origen, read_only=True, data_only=True)
    faltantes_hojas = HojasAutorizadas - set(wb.sheetnames)
    if faltantes_hojas:
        sys.exit(f"ERROR: faltan hojas autorizadas: {sorted(faltantes_hojas)}.")

    errores = []  # filas/referencia -> problema
    importados = {"Proveedores": 0, "Productos": 0, "Inventario": 0}

    temporal = destino.with_name(destino.name + ".tmp")
    if destino.exists():
        temporal.unlink(missing_ok=True)
    conn = sqlite3.connect(temporal)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(Path(__file__).parent.parent.joinpath("src", "schema.sql").read_text())

    try:
        conn.execute("BEGIN")
        # --- Proveedores ---
        ws = wb["Proveedores"]
        ok, falt = validar_encabezados(ws, "Proveedores")
        if not ok:
            raise ValueError("Columna(s) ausente(s) en Proveedores: " + ", ".join(falt))
        for fila_idx, r in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
            if not r or not ecu(r[0]):
                continue
            pid = ecu(r[0])
            if conn.execute("SELECT 1 FROM proveedores WHERE id = ?", (pid,)).fetchone():
                errores.append(("Proveedores", fila_idx, pid, "ID proveedor duplicado"))
                continue
            conn.execute(
                """INSERT INTO proveedores
                   (id, razon_social, nit, categoria_principal, contacto, telefono,
                    celular, correo, direccion, ciudad, departamento, condiciones_pago,
                    medio_preferido, estado)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, ecu(r[1]), ecu(r[2]), ecu(r[3]), ecu(r[4]), ecu(r[5]), ecu(r[6]),
                 ecu(r[7]), ecu(r[8]), ecu(r[9]), ecu(r[10]), ecu(r[11]), ecu(r[12]), ecu(r[13])),
            )
            conn.execute(
                "INSERT INTO importaciones(archivo, hoja, fila, tipo, referencia) VALUES (?,?,?,?,?)",
                (origen.name, "Proveedores", fila_idx, "proveedor", pid),
            )
            importados["Proveedores"] += 1

        # --- Productos ---
        ws = wb["Productos"]
        ok, falt = validar_encabezados(ws, "Productos")
        if not ok:
            raise ValueError("Columna(s) ausente(s) en Productos: " + ", ".join(falt))
        for fila_idx, r in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
            if not r or not ecu(r[0]):
                continue
            codigo = ecu(r[0])
            if conn.execute("SELECT 1 FROM productos WHERE codigo = ?", (codigo,)).fetchone():
                errores.append(("Productos", fila_idx, codigo, "Código de producto duplicado"))
                continue
            prov_id = ecu(r[3])
            if not conn.execute("SELECT 1 FROM proveedores WHERE id = ?", (prov_id,)).fetchone():
                errores.append(("Productos", fila_idx, codigo, "Proveedor inválido: " + prov_id))
                continue
            if num(r[6]) is None or num(r[7]) is None:
                errores.append(("Productos", fila_idx, codigo, "Precio faltante o no numérico"))
                continue
            if num(r[6]) < 0 or num(r[7]) < 0:
                errores.append(("Productos", fila_idx, codigo, "Precio negativo"))
                continue
            if not ecu(r[1]):
                errores.append(("Productos", fila_idx, codigo, "Nombre de producto ausente"))
                continue
            conn.execute(
                """INSERT INTO productos
                   (codigo, nombre, categoria, proveedor_id, unidad, precio_costo, precio_venta, fecha_vencimiento)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (codigo, ecu(r[1]), ecu(r[2]), prov_id, ecu(r[5]), num(r[6]), num(r[7]),
                 fecha_a_texto(r[9])),
            )
            conn.execute(
                "INSERT INTO importaciones(archivo, hoja, fila, tipo, referencia) VALUES (?,?,?,?,?)",
                (origen.name, "Productos", fila_idx, "producto", codigo),
            )
            importados["Productos"] += 1

        # --- Inventario (lotes) ---
        ws = wb["Inventario"]
        ok, falt = validar_encabezados(ws, "Inventario")
        if not ok:
            raise ValueError("Columna(s) ausente(s) en Inventario: " + ", ".join(falt))
        for fila_idx, r in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
            if not r or not ecu(r[0]):
                continue
            codigo = ecu(r[0])
            lote = ecu(r[5])
            stock = entero(r[6])
            minimo = entero(r[7])
            # Validación de stock
            if stock is None or minimo is None:
                errores.append(("Inventario", fila_idx, codigo, "Stock o stock mínimo faltante"))
                continue
            if stock < 0 or minimo < 0:
                errores.append(("Inventario", fila_idx, codigo, f"Cantidad negativa (stock={stock}, mínimo={minimo})"))
                continue
            if not conn.execute("SELECT 1 FROM productos WHERE codigo = ?", (codigo,)).fetchone():
                errores.append(("Inventario", fila_idx, codigo, "Relación inválida: producto no existe en catálogo"))
                continue
            # El proveedor de la fila debe coincidir con el del catálogo
            maestro = conn.execute("SELECT p.proveedor_id, p.nombre, pr.razon_social FROM productos p JOIN proveedores pr ON pr.id = p.proveedor_id WHERE p.codigo = ?", (codigo,)).fetchone()
            if maestro and ecu(r[3]) and ecu(r[3]) != maestro["razon_social"]:
                errores.append(("Inventario", fila_idx, codigo, "Relación inválida: proveedor no coincide con el catálogo"))
                continue
            if conn.execute("SELECT 1 FROM lotes_inventario WHERE producto_codigo = ? AND lote = ?", (codigo, lote)).fetchone():
                errores.append(("Inventario", fila_idx, codigo, "Combinación producto/lote duplicada"))
                continue
            conn.execute(
                """INSERT INTO lotes_inventario
                   (producto_codigo, lote, ubicacion, stock, stock_minimo, fecha_vencimiento,
                    ultimo_movimiento, observaciones)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (codigo, lote, ecu(r[4]), stock, minimo, fecha_a_texto(r[10]),
                 fecha_a_texto(r[13]), ecu(r[14])),
            )
            conn.execute(
                "INSERT INTO importaciones(archivo, hoja, fila, tipo, referencia) VALUES (?,?,?,?,?)",
                (origen.name, "Inventario", fila_idx, "lote", codigo),
            )
            importados["Inventario"] += 1

        # --- Reconciliación ---
        total_prov = conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
        total_prod = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        total_inv = conn.execute("SELECT COUNT(*) FROM lotes_inventario").fetchone()[0]
        bajo_min = conn.execute(
            "SELECT COUNT(*) FROM lotes_inventario WHERE stock < stock_minimo"
        ).fetchone()[0]
        rel_invalidas = len([e for e in errores if e[3].startswith("Relación inválida")])

        conn.execute(
            "INSERT OR REPLACE INTO metadata(clave, valor) VALUES ('fecha_corte', ?), ('origen', ?), ('hash_excel', ?)",
            (FECHA_CORTE, origen.name, hashlib.md5(origen.read_bytes()).hexdigest()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        temporal.unlink(missing_ok=True)
        raise
    finally:
        wb.close()

    # --- Reemplazo seguro de la base final ---
    conn.close()
    if destino.exists():
        destino.unlink()
    temporal.rename(destino)

    # --- Salvada de errores ---
    if errores:
        with open(destino.parent / "errores_importacion.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["hoja", "fila", "referencia", "problema"])
            w.writerows(errores)

    return destino, importados, total_prov, total_prod, total_inv, bajo_min, rel_invalidas, errores


def escribir_reportes(destino: Path, importados, total_prov, total_prod, total_inv,
                      bajo_min, rel_invalidas, errores):
    destino.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Reporte de importación",
        "",
        f"- Origen: `{destino.name}`",
        f"- Fecha de corte: {FECHA_CORTE}",
        "",
        "## Resultado",
        "",
        "| Hoja | Importados | Esperado | Estado |",
        "|---|---|---|---|",
        f"| Proveedores | {total_prov} | 75 | {'OK' if total_prov == 75 else 'DIFERENTE'} |",
        f"| Productos | {total_prod} | 1250 | {'OK' if total_prod == 1250 else 'DIFERENTE'} |",
        f"| Inventario | {total_inv} | 827 | {'OK' if total_inv == 827 else 'DIFERENTE'} |",
        f"| Bajo el mínimo | {bajo_min} | 73 | {'OK' if bajo_min == 73 else 'DIFERENTE'} |",
        f"| Relaciones inválidas | {rel_invalidas} | 0 | {'OK' if rel_invalidas == 0 else 'DIFERENTE'} |",
        "",
        f"## Errores y pendientes: {len(errores)}",
        "",
    ]
    if errores:
        lineas += ["| Hoja | Fila | Referencia | Problema |", "|---|---|---|---|"]
        lineas += [f"| {e[0]} | {e[1]} | {e[2]} | {e[3]} |" for e in errores]
        lineas.append("")
        lineas += ["Los errores no se ocultan. Ninguna inconsistencia se completa por intuición.",
                   "El detalle completo está en `datos/procesados/errores_importacion.csv`."]
    else:
        lineas += ["Sin errores ni pendientes."]
    reporte = destino.parent / "reporte_importacion.md"
    reporte.write_text("\n".join(lineas), encoding="utf-8")

    for k, v in importados.items():
        print(f"{k}: {v}")
    print(f"Base creada: {destino}")
    print(f"Proveedores: {total_prov} (esperado: 75)")
    print(f"Productos: {total_prod} (esperado: 1250)")
    print(f"Inventario: {total_inv} (esperado: 827)")
    print(f"Bajo el mínimo: {bajo_min} (esperado: 73)")
    print(f"Relaciones inválidas: {rel_invalidas} (esperado: 0)")


def main(argv: list[str] | None = None) -> None:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        sys.exit("Uso: uv run python scripts/importar_excel.py <origen.xlsm> <destino.db>")
    origen = Path(argv[0])
    destino = Path(argv[1])
    _db, importados, t_prov, t_prod, t_inv, bajo, rel, errores = construir_base(origen, destino)
    escribir_reportes(destino, importados, t_prov, t_prod, t_inv, bajo, rel, errores)


if __name__ == "__main__":
    main()