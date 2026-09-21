"""Pruebas del asistente de inventario (Módulo 3).

Cubre los nueve casos obligatorios:
1. código válido; 2. nombre ambiguo; 3. producto inexistente; 4. stock bajo;
5. lote vencido; 6. proveedor inválido; 7. segunda importación; 8. columna ausente;
9. escritura no autorizada; más el comportamiento normal de cada herramienta.
"""

from __future__ import annotations

import pytest
from conftest import construir_xlsm

from scripts import importar_excel
from src import app as asistente
from src import buscador, herramientas


# --- Caso 1: código válido ---
def test_codigo_valido_devuelve_producto(base):
    r = herramientas.consultar_producto("FER-0001", base)
    assert r["estado"] == "ok"
    assert r["producto"]["nombre"] == "Martillo de uña Forte Mini"
    assert r["producto"]["proveedor_id"] == "PRV-001"
    assert "SQLite" in r["fuente"]


# --- Caso 2: nombre ambiguo -> candidatos, no hechos exactos ---
def test_busqueda_por_significado_presenta_candidatos(base):
    r = buscador.buscar_productos("martillo", ruta=base)
    assert r["estado"] == "ok"
    assert r["total_candidatos"] >= 1
    candidato = r["candidatos"][0]
    assert candidato["es_candidato"] is True
    # Cada candidato debe confirmarse con SQLite (herramienta exacta)
    confirmado = herramientas.consultar_producto(candidato["codigo"], base)
    assert confirmado["estado"] == "ok"
    # Una búsqueda aproximada nunca se presenta como hecho exacto
    assert "Confirma códigos y cantidades" in r["regla"]


# --- Caso 3: producto inexistente ---
def test_producto_inexistente_no_inventa_datos(base):
    r = herramientas.consultar_existencias("ZZZ-9999", base)
    assert r["estado"] == "no_encontrado"
    assert r["tipo"] == "producto_inexistente"


# --- Caso 4: stock bajo -> propuesta reproducible ---
def test_stock_bajo_produce_propuesta_reproducible(base):
    existencias = herramientas.consultar_existencias("FER-0001", base)
    assert existencias["stock_total"] == 8
    assert existencias["stock_minimo"] == 22
    propuesta = herramientas.calcular_reposicion("FER-0001", base)
    assert propuesta["cantidad_propuesta"] == 14  # 22 - 8
    assert propuesta["estado_propuesta"] == "propuesta_pendiente"
    assert "no se registró ninguna compra" in propuesta["nota"].lower()


def test_listar_bajo_minimo(base):
    r = herramientas.listar_bajo_minimo(base)
    codigos = {p["codigo"] for p in r["productos"]}
    assert "FER-0001" in codigos
    assert "ABA-0001" not in codigos  # 50 >= mínimo 10


# --- Caso 5: lote vencido ---
def test_lote_vencido_se_separa(base):
    r = herramientas.listar_proximos_vencer(15, base)
    por_vencer = {v["lote"] for v in r["por_vencer"]}
    vencidos = {v["lote"] for v in r["vencidos"]}
    assert "LT-2430339" in por_vencer  # vence 2026-09-10, dentro de 15 días del corte
    assert "LT-VENCIDO" in vencidos  # vence 2025-04-28, antes del corte


# --- Caso 6: proveedor inválido -> bloqueado, va a pendientes ---
def test_proveedor_invalido_se_bloquea_y_se_reporta(base_con_proveedor_invalido):
    db, _importados, _t_prov, _t_prod, _t_inv, _bajo, rel_invalidas, errores = base_con_proveedor_invalido
    from src.db import conectar

    conn = conectar(db)
    codigos = {f["codigo"] for f in conn.execute("SELECT codigo FROM productos").fetchall()}
    conn.close()
    assert "XZZ-0001" not in codigos  # no se importó
    assert "FER-0001" in codigos  # el resto sí
    assert any("Proveedor inválido" in e[3] for e in errores)
    # El error queda documentado en el CSV de errores
    assert (db.parent / "errores_importacion.csv").exists()


# --- Caso 7: segunda importación idempotente ---
def test_segunda_importacion_no_duplica(tmp_path):
    xlsm = construir_xlsm(tmp_path / "prueba2.xlsm")
    db = tmp_path / "repetida.db"
    _r1 = importar_excel.construir_base(xlsm, db)
    conteos_1 = _r1[2:6]
    _r2 = importar_excel.construir_base(xlsm, db)
    conteos_2 = _r2[2:6]
    assert conteos_1 == conteos_2
    assert 0 not in conteos_1  # nada vacío
    from src.db import conectar

    conn = conectar(db)
    total = conn.execute("SELECT COUNT(*) FROM lotes_inventario").fetchone()[0]
    conn.close()
    assert total == 3  # ninguna fila duplicada


# --- Caso 8: columna ausente detiene la carga ---
def test_columna_ausente_detiene_carga(tmp_path):
    xlsm = construir_xlsm(tmp_path / "sin_columna.xlsm", columna_ausente=True)
    with pytest.raises(ValueError, match="[Aa]usente"):
        importar_excel.construir_base(xlsm, tmp_path / "nunca.db")
    assert not (tmp_path / "inventario.db.tmp").exists()
    assert not (tmp_path / "nunca.db").exists()


# --- Caso 9: escritura no autorizada ---
def test_escritura_no_autorizada_se_rechaza(base):
    r = asistente.resolver("Registra 20 unidades más de FER-0001", base)
    assert r["estado"] == "rechazado"
    assert "no está autorizada" in r["mensaje"].lower()


# --- Comportamiento normal de cada herramienta y del asistente ---
def test_asistente_consulta_producto(base):
    r = asistente.resolver("¿Cuál es la ficha del producto FER-0001?", base)
    assert r["herramienta"] == "consultar_producto"
    assert r["estado"] == "ok"


def test_asistente_bajo_minimo(base):
    r = asistente.resolver("¿Qué productos están bajo el mínimo?", base)
    assert r["herramienta"] == "listar_bajo_minimo"
    assert r["total"] >= 1


def test_asistente_reposicion_con_codigo(base):
    r = asistente.resolver("¿Cuánto hay que reponer de FER-0001?", base)
    assert r["herramienta"] == "calcular_reposicion"
    assert r["cantidad_propuesta"] == 14


def test_asistente_busqueda(base):
    r = asistente.resolver("buscar martillos de ferretería", base)
    assert r["herramienta"] == "buscar_productos"
    assert r["total_candidatos"] >= 1


def test_consultar_existencias_con_lotes(base):
    r = herramientas.consultar_existencias("ABA-0001", base)
    assert r["estado"] == "ok"
    assert len(r["lotes"]) == 2
    assert r["stock_total"] == 62


def test_calcular_reposicion_producto_inexistente(base):
    r = herramientas.calcular_reposicion("NNN-0000", base)
    assert r["estado"] == "no_encontrado"


def test_validacion_de_codigo_vacio(base):
    r = herramientas.consultar_producto("", base)
    assert r["estado"] == "error"
    assert r["tipo"] == "argumento_invalido"