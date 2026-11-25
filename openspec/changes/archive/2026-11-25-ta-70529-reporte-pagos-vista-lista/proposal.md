## Why

Al entrar a *Punto de venta > Reportes > Reporte de pagos* el cliente web muestra «No se encontró ninguna vista predeterminada de tipo 'tree'» y el wizard no abre. El formulario `l10n_ve_pos.pos_payment_report` declara `pos_config_ids` con `mode="tree"`; Odoo 19 eliminó el tipo de vista `tree` (ahora `list`), así que el cliente busca una vista que no existe.

## What Changes

- `wizard/payment_report.xml`: `pos_config_ids` pasa de `mode="tree"` a `mode="list"`.
- Prueba `tests/test_pos_payment_report_view.py`: verifica que el formulario no declare `mode="tree"` y que abra agregando una caja.
- Versión del manifest de `l10n_ve_pos` a `19.0.1.31.2`.

## Impact

- **Specs afectadas**: `l10n_ve_pos` (requisito «Reporte de métodos de pago del PdV»).
- **Código**: solo la vista del wizard. Sin migración, sin cambios de modelo ni textos nuevos.
- **Qué ve el usuario**: el menú Reporte de pagos vuelve a abrir el wizard; el reporte se genera igual que antes.
