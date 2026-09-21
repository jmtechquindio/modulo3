# Esquema SQLite — inventario.db

Archivo de esquema: `src/schema.sql` (aplicado por `scripts/importar_excel.py`).

## Tablas

### proveedores
Maestro de proveedores (hoja `Proveedores`, datos desde fila 5).

| Columna | Tipo | Notas |
|---|---|---|
| id | TEXT PK | `PRV-001` |
| razon_social | TEXT NOT NULL | |
| nit | TEXT | |
| categoria_principal | TEXT | |
| contacto, telefono, celular, correo | TEXT | |
| direccion, ciudad, departamento | TEXT | |
| condiciones_pago, medio_preferido, estado | TEXT | |

### productos
Catálogo maestro (hoja `Productos`, datos desde fila 5).

| Columna | Tipo | Notas |
|---|---|---|
| codigo | TEXT PK | `FER-0001` |
| nombre | TEXT NOT NULL | |
| categoria | TEXT NOT NULL | Usada por la búsqueda por significado |
| proveedor_id | TEXT NOT NULL → proveedores(id) | Relación validada |
| unidad | TEXT | |
| precio_costo | REAL, CHECK (precio_costo >= 0) | |
| precio_venta | REAL, CHECK (precio_venta >= 0) | |
| fecha_vencimiento | TEXT | Solo 500 productos lo tienen |

### lotes_inventario
Inventario/lotes (hoja `Inventario`, datos desde fila 5).

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| producto_codigo | TEXT NOT NULL → productos(codigo) | Relación validada |
| lote | TEXT NOT NULL | `LT-2430339` |
| ubicacion | TEXT | |
| stock | INTEGER NOT NULL, CHECK (stock >= 0) | |
| stock_minimo | INTEGER NOT NULL, CHECK (stock_minimo >= 0) | |
| fecha_vencimiento | TEXT | Para vencimientos |
| ultimo_movimiento, observaciones | TEXT | |
| — | UNIQUE (producto_codigo, lote) | Evita duplicados de importación |

### importaciones
Procedencia trazable (archivo, hoja, fila) de cada registro importado.

### metadata
Claves del proyecto: `fecha_corte` (`2026-09-04`, corte reproducible), `origen`, `hash_excel`.

## Índices
`proveedores(razon_social)`, `productos(nombre, categoria, proveedor_id)`,
`lotes_inventario(fecha_vencimiento, stock)`.

## Cálculos reproducibles (no almacenados)
- Valor inventario: `stock × precio_costo` (consulta).
- Días al vencimiento y estado: calculados contra `fecha_corte` (consulta).
- Bajo el mínimo: `SUM(stock) < MAX(stock_minimo)` (consulta).

## Reglas
- No se importan las hojas Ventas, Clientes, Libro diario, ni otras.
- Las macros permanecen solo en el XLSM original; no se convierten ni ejecutan.
- Ninguna inconsistencia se completa por intuición: se envía a errores/pendientes.