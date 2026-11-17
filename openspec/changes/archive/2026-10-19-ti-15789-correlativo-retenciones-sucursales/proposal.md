## Why

Las sucursales nativas de Odoo 19 que comparten el RIF de la matriz creaban una secuencia de retenciones propia desde 1 (`retention.iva/islr/municipal.control.number`) al confirmar facturas, duplicando comprobantes respecto al correlativo único del agente de retención (ticket #15789, Pedrera Santa Rosa).

## What Changes

- `l10n_ve_payment_extension`: nuevo booleano `res.company.use_parent_retention_sequence` (default `False`, sin migración: el comportamiento nativo no cambia). Con él activo y mismo RIF que la matriz, `get_sequence_retention` busca/crea la secuencia con `company_id` de la matriz (`_get_retention_sequence_company`, lectura con `sudo()`); aplica a IVA, ISLR y municipal. Check en Ajustes > Localización Venezuela, visible solo en sucursales. Traducciones en `es_VE.po`.
- Sin cambios en `binaural_subsidiary_payment_extension`: la secuencia municipal por subsidiaria analítica conserva su prioridad.
- Bump `l10n_ve_payment_extension` 19.0.2.1.0 → 19.0.2.1.1.

## Impact

- Specs: `l10n_ve_payment_extension`.
- Tests: `test_retention_sequence_branch.py` y `test_retention_sequence_branch_flow.py`.
- Fuera de alcance: Libro de Ventas/Compras consolidado por sucursales (requerimiento distinto del mismo ticket).
