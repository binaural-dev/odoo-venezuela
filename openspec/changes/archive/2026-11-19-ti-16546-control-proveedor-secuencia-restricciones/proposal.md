## Why

Tres reglas de integridad del número de control y de las restricciones de base de datos quedaron mal en v19 (ticket #16546):

- Las facturas de proveedor emitidas por máquina fiscal repiten el número de control entre facturas distintas del mismo proveedor. La validación comparaba solo proveedor y control, por lo que no dejaba registrar la segunda factura; y como corría solo al guardar el control, dos borradores idénticos entraban como duplicados exactos al confirmarse.
- Una compañía podía tener dos secuencias `invoice.correlative` activas (se perdió `check_sequence_exists` de v17). `get_sequence` fallaba con "Expected singleton" y la compañía no podía publicar facturas.
- Odoo 19 ya no lee `_sql_constraints`: se perdían los UNIQUE y CHECK de ciudades, tipos de retención, actividades económicas, ramas económicas y conceptos de pago.

## What Changes

- `l10n_ve_invoice`: en facturas y notas de crédito de proveedor, un duplicado es el mismo proveedor, el mismo número de factura (`name`) y el mismo control. La búsqueda abarca todo el árbol de compañías de la matriz (con `sudo()`, para que un usuario restringido a una sucursal detecte el duplicado de otra) y solo cuenta documentos publicados. `_check_correlative` corre también al cambiar `name`, y `_check_vendor_correlative_before_post` valida al confirmar (antes de publicar y también entre documentos confirmados en un mismo lote). Las ventas y los diarios de contingencia no cambian.
- `l10n_ve_invoice`: nuevo `ir.sequence.check_sequence_exists` (una sola secuencia `invoice.correlative` activa por compañía) y `get_sequence` toma la más antigua para no fallar en bases con duplicados.
- `l10n_ve_location` y `l10n_ve_payment_extension`: las restricciones pasan de `_sql_constraints` a `models.Constraint` (ciudad, tipo de retención, actividad económica, rama económica, concepto de pago) con los mismos nombres y mensajes.
- `l10n_ve_accountant`: se eliminan los dos `_sql_constraints` vacíos de `account.move`, sin efecto en v19 (el índice por proveedor sigue creándose en `_auto_init`).
- Fuera de alcance: `account_fiscal_year_closing` (migración a v19 sin terminar) y la corrección de duplicados ya cargados en las bases.

## Impact

- Specs afectadas: `l10n_ve_invoice` (secuencia única por compañía y unicidad del control de proveedor), `l10n_ve_location` y `l10n_ve_payment_extension` (redacción de las restricciones).
- Versiones de manifest: `l10n_ve_invoice` 19.0.1.0.29, `l10n_ve_payment_extension` 19.0.2.2.9, `l10n_ve_location` 19.0.1.2.1, `l10n_ve_accountant` 19.0.1.0.45.
- Sin migración de datos. En una base que ya tenga duplicados, la creación de la restricción puede omitirse con aviso; las secuencias duplicadas existentes no se desactivan solas.
- Pendiente de otra parte: definir con el área fiscal si el serial de la máquina fiscal pasa a un campo propio.
