## Why

El SENIAT exige un único Libro de Ventas y un único Libro de Compras por RIF y período. Pedrera Santa Rosa C.A. opera con una matriz y dos sucursales nativas de Odoo 19 (Carucieña y Cal) con el mismo RIF, pero el asistente de libros solo tomaba la compañía activa, por lo que obligaba a presentar libros separados por sede (ticket #15790). Producción de las sucursales arranca el 20/10/2026.

## What Changes

- `l10n_ve_invoice`: `wizard.accounting.reports` detecta las sucursales (hijas por `parent_id`) con el mismo RIF y agrega `has_branches`, `branch_scope` (`all` consolidado por defecto / `main` solo matriz / `branch` una sucursal), `branch_company_id` y `report_company_ids` (limitado a las compañías del usuario). `_get_domain` filtra por `company_id in report_company_ids`. Cabecera con la matriz (o la sucursal en alcance `branch`). El selector solo se muestra si hay sucursales del mismo RIF. Compañías con otro RIF nunca se incluyen.
- `l10n_ve_invoice` (controlador): las rutas de descarga reciben `wizard_id` en lugar de tomar el último wizard de la base; se valida que pertenezca al usuario y a una compañía a la que tiene acceso. Se mantiene la firma `generate_*_book(company_id)` por compatibilidad con `binaural_operative`.
- `l10n_ve_payment_extension`: `_get_retention_domain` filtra por `report_company_ids`, de modo que las retenciones de IVA y su total del resumen se consolidan igual que las facturas.
- `l10n_ve_igtf`: las columnas IGTF leen `not_show_igtf_*` de `company_id` del wizard y no de `env.company`.
- Bump de versión: `l10n_ve_invoice` 19.0.1.0.24 → 19.0.1.1.0, `l10n_ve_payment_extension` 19.0.2.1.0 → 19.0.2.2.0, `l10n_ve_igtf` 19.0.1.2.18 → 19.0.1.2.19.

## Non-goals

- `l10n_ve_pos_mf` (libro de ventas POS, otra vertical) y `binaural_operative` (otro repositorio) no se modifican; el POS requiere su propio PR.
- `l10n_ve_iot_mf` no cambia: solo hereda `_get_domain`.

## Impact

- Specs: `l10n_ve_invoice`, `l10n_ve_payment_extension`, `l10n_ve_igtf`.
- Tests: `l10n_ve_invoice/tests/test_accounting_reports_branches.py` (12), `l10n_ve_payment_extension/tests/test_accounting_reports_branches_moves.py` (9, con documentos y retención reales en sucursales nativas); se ajustaron dos asserts existentes del dominio y de la URL de descarga.
