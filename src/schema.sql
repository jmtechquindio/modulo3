PRAGMA foreign_keys = ON;

CREATE TABLE proveedores (
    id                TEXT PRIMARY KEY,
    razon_social      TEXT NOT NULL,
    nit               TEXT,
    categoria_principal TEXT,
    contacto          TEXT,
    telefono          TEXT,
    celular           TEXT,
    correo            TEXT,
    direccion         TEXT,
    ciudad            TEXT,
    departamento      TEXT,
    condiciones_pago  TEXT,
    medio_preferido   TEXT,
    estado            TEXT
);

CREATE INDEX idx_proveedores_razon_social ON proveedores(razon_social);

CREATE TABLE productos (
    codigo           TEXT PRIMARY KEY,
    nombre           TEXT NOT NULL,
    categoria        TEXT NOT NULL,
    proveedor_id     TEXT NOT NULL REFERENCES proveedores(id),
    unidad           TEXT,
    precio_costo     REAL NOT NULL CHECK (precio_costo >= 0),
    precio_venta     REAL NOT NULL CHECK (precio_venta >= 0),
    fecha_vencimiento TEXT
);

CREATE INDEX idx_productos_nombre ON productos(nombre);
CREATE INDEX idx_productos_categoria ON productos(categoria);
CREATE INDEX idx_productos_proveedor ON productos(proveedor_id);

CREATE TABLE lotes_inventario (
    id                 INTEGER PRIMARY KEY,
    producto_codigo   TEXT NOT NULL REFERENCES productos(codigo),
    lote              TEXT NOT NULL,
    ubicacion         TEXT,
    stock             INTEGER NOT NULL CHECK (stock >= 0),
    stock_minimo      INTEGER NOT NULL CHECK (stock_minimo >= 0),
    fecha_vencimiento TEXT,
    ultimo_movimiento TEXT,
    observaciones     TEXT,
    UNIQUE (producto_codigo, lote)
);

CREATE INDEX idx_lotes_vencimiento ON lotes_inventario(fecha_vencimiento);
CREATE INDEX idx_lotes_stock ON lotes_inventario(stock);

CREATE TABLE importaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo     TEXT NOT NULL,
    hoja        TEXT NOT NULL,
    fila        INTEGER NOT NULL,
    tipo        TEXT NOT NULL,
    referencia  TEXT,
    detalle     TEXT
);

CREATE TABLE metadata (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);