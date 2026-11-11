Una tarea por commit de la rama `19.0_feat-ta_86967_donation_module_1440_port`
(13 commits sobre `19.0`, `4a302c6ae`). Los hashes son los de la
rama; el commit de documentación cambia de hash cada vez que se actualiza.

## T1. [MIG] l10n_ve_donation: base 19 sin donación por scrap (`cff40ae82`)
- **Tipo**: `[MIG]`
- **Estado**: ✅ Hecho
- **Archivos**: `__manifest__.py` (19.0.3.0.0, reportes, csv, sin scrap), `models/__init__.py`, `models/stock_scrap.py` (eliminado), `views/stock_scrap_views.xml` (eliminado), `migrations/` (eliminada), `security/ir.model.access.csv`
- **Done when**: el módulo instala en una base 19 nueva y no queda código ni vistas de scrap.

## T2. [IMP] almacén de donación por compañía y sucursal (`8203868cb`)
- **Tipo**: `[IMP]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_warehouse.py`, `tests/common.py`, `tests/test_product_warehouse.py`
- **Done when**: REQ-DON-010 cubierto por tests.

## T3. [FIX] beneficiario real en la cabecera (`1d9ae9367`, port de `587245bb9`)
- **Tipo**: `[FIX]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`_check_partner_donation` solo apuntes `entry`), `models/sale_order.py`, `report/donation_certificate_template.xml`, `tests/test_sale_order.py`
- **Done when**: REQ-DON-011 cubierto por tests.

## T4. [REF] unifica la donación de pickings en `is_donation` (`cc90af515`, port de `9675a0f0c`)
- **Tipo**: `[REF]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_picking.py`, `models/stock_picking_type.py`, `views/stock_picking_views.xml`, `views/stock_picking_type_views.xml`
- **Done when**: REQ-DON-001, 002 y 008 cubiertos por tests.

## T5. [IMP] valida la configuración y bloquea devoluciones (`a2e9782f1`, port de `8de43e6ad`)
- **Tipo**: `[IMP]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_location.py` (`valuation_account_id`), `models/stock_picking.py`, `models/stock_return_picking.py`
- **Done when**: REQ-DON-003, 004, 007 y 009 cubiertos por tests, incluida la devolución de un pedido de donación sin el motivo 'Donación'.

## T6. [FIX] asiento de valoración de la donación de picking (`79c2bf344`, port de `0ee206105`, API 19)
- **Tipo**: `[FIX]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_move.py`, `tests/test_stock_move.py`
- **Done when**: REQ-DON-005 cubierto (cabecera, apuntes, referencia, lote mixto y `default_is_donation` filtrado al contexto).

## T7. [FEAT] certificado de entrega de donación (`f90aaf043`, port de `d7c5339c9`)
- **Tipo**: `[FEAT]`
- **Estado**: ✅ Hecho
- **Archivos**: `report/donation_delivery_certificate_*.xml`, `report/donation_product_table_template.xml`, `models/stock_picking.py` (también oculta "Crear factura"), `tests/test_stock_picking.py`
- **Done when**: REQ-DON-006, REQ-DON-015 y REQ-DON-017 cubiertos; el certificado se renderiza con el costo de `stock.move.value`.

## T8. [FIX] nota de crédito con API de 19 (`9ad625d9d`)
- **Tipo**: `[FIX]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`action_post` con guarda y por lote, `_reverse_moves` sin `skip_invoice_sync`, hook de exención), `tests/test_donation_credit_note_regression.py`, `tests/test_coverage_gaps.py`, `tests/test_sale_account_move.py`
- **Done when**: REQ-DON-012 y 013 cubiertos, incluidos el monto de la nota (misma base, impuesto y total), el lote de varias facturas y el lote mixto con facturas que no son de donación.

## T9. [FIX] asiento manual de donación (`f8f8ac19c`)
- **Tipo**: `[FIX]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`write`, `_fill_donation_entry_line_partner`, `action_post`), `models/account_move_line.py` (`create`), `views/account_move_views.xml`, `tests/test_sale_account_move.py`
- **Done when**: REQ-DON-014 cubierto: `is_donation` editable en un asiento nuevo, partner asignado en borrador (incluidos los apuntes que llegan con `partner_id: False`), publicar en un diario con hash sin errores y sin escribir en los apuntes.

## T10. [FIX] certificado de donación de dinero (`29517fe6e`)
- **Tipo**: `[FIX]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`is_stock_valuation_entry`, guarda en `print_donation_certificate`, `_get_donation_certificate_amounts`), `views/account_move_views.xml`, `report/donation_certificate_template.xml`, `tests/test_sale_account_move.py`, `tests/test_stock_move.py`
- **Done when**: REQ-DON-016 cubierto: el certificado del asiento dice "la suma de" con letras, monto, equivalente alterno y tasa; el asiento de valoración de un picking no ofrece el botón y la acción lo rechaza.

## T11. [CLN] quitar `_logger` sin usar (`00db75dbd`)
- **Tipo**: `[CLN]`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_picking.py`, `stock_move.py`, `account_move_line.py`, `stock_picking_type.py`, `product_template.py`
- **Done when**: no quedan `_logger` ni `import logging` sin uso en los modelos.

## T12. [I18N] regenera la traducción es_VE (`02e6ffb4e`)
- **Tipo**: `[I18N]`
- **Estado**: ✅ Hecho
- **Archivos**: `i18n/es_VE.po`
- **Done when**: sin entradas de scrap ni términos vacíos, y los textos nuevos salen en español (error de validación, certificado de entrega, menú Donaciones).

## T13. [DOCS] openspec de la migración
- **Tipo**: `[DOCS]`
- **Estado**: ✅ Hecho
- **Archivos**: este change, `openspec/specs/l10n_ve_donation/spec.md` (vigente)
- **Done when**: la spec vigente y el delta describen REQ-DON-001 a 017 y `STATE.md` refleja la verificación real.

## Conservado de V19 sin cambios
- Baja de activos con mensaje (`models/account_asset.py`, `tests/test_account_asset.py`).

## Pendientes fuera de la rama
- ✅ Destino del PR decidido: `19.0` (tronco de desarrollo; una tarea nace de `X.0-master`). Falta publicar la rama y abrir el PR.
- ⏳ PR en integra-addons: `binaural_stock_dispatch_note` (contacto readonly solo con pedido) y `l10n_ve_inventory_book` (`test_outgoing_with_donation` espera 'Donación').
- ⏳ Mensaje a Producto sobre `binaural_subsidiary_stock` (ver `STATE.md`).
- ⏳ Ajustes en `higea_donation` al migrarlo: `test_22` (espera el sufijo), restauración del donante tras publicar, líneas sin donante.
