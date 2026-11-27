Una tarea por unidad de trabajo del módulo.

## T1. [MIG] base 19 sin donación por scrap
- **Estado**: ✅ Hecho
- **Archivos**: `__manifest__.py` (19.0.3.0.0, reportes, csv, sin scrap), `models/__init__.py`, `models/stock_scrap.py` (eliminado), `views/stock_scrap_views.xml` (eliminado), `migrations/` (eliminada), `security/ir.model.access.csv`
- **Done when**: el módulo instala en una base 19 nueva y no queda código ni vistas de scrap.

## T2. [IMP] almacén de donación por compañía y sucursal
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_warehouse.py`, `tests/common.py`, `tests/test_product_warehouse.py`
- **Done when**: REQ-DON-010 cubierto por tests.

## T3. [FIX] beneficiario real en la cabecera
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`_check_partner_donation` solo apuntes `entry`), `models/sale_order.py`, `report/donation_certificate_template.xml`, `tests/test_sale_order.py`
- **Done when**: REQ-DON-011 cubierto por tests.

## T4. [REF] unifica la donación de pickings en `is_donation`
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_picking.py`, `models/stock_picking_type.py`, `views/stock_picking_views.xml`, `views/stock_picking_type_views.xml`
- **Done when**: REQ-DON-001, 002 y 008 cubiertos por tests.

## T5. [IMP] valida la configuración y bloquea devoluciones
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_location.py` (`valuation_account_id`), `models/stock_picking.py`, `models/stock_return_picking.py`
- **Done when**: REQ-DON-003, 004, 007 y 009 cubiertos por tests, incluida la devolución de un pedido de donación sin el motivo 'Donación'.

## T6. [FIX] asiento de valoración de la donación de picking
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_move.py`, `tests/test_stock_move.py`
- **Done when**: REQ-DON-005 cubierto (cabecera, apuntes, referencia, lote mixto y `default_is_donation` filtrado al contexto).

## T7. [FEAT] documento de la entrega de donación
- **Estado**: ✅ Hecho; el documento hoy es el Recibo de donación (`ta-86967-donation-received-documents`)
- **Archivos**: `report/donation_product_table_template.xml`, `models/stock_picking.py` (también oculta "Crear factura"), `tests/test_stock_picking.py`
- **Done when**: REQ-DON-006, REQ-DON-015 y REQ-DON-017 cubiertos; el documento se renderiza con el costo de `stock.move.value`.

## T8. [FIX] nota de crédito con API de 19
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`action_post` con guarda y por lote, `_reverse_moves` sin `skip_invoice_sync`, hook de exención), `tests/test_donation_credit_note_regression.py`, `tests/test_coverage_gaps.py`, `tests/test_sale_account_move.py`
- **Done when**: REQ-DON-012 y 013 cubiertos, incluidos el monto de la nota (misma base, impuesto y total), el lote de varias facturas y el lote mixto con facturas que no son de donación.

## T9. [FIX] asiento manual de donación
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py` (`write`, `_fill_donation_entry_line_partner`, `action_post`), `models/account_move_line.py` (`create`), `views/account_move_views.xml`, `tests/test_sale_account_move.py`
- **Done when**: REQ-DON-014 cubierto: `is_donation` editable en un asiento nuevo, partner asignado en borrador (incluidos los apuntes que llegan con `partner_id: False`), publicar en un diario con hash sin errores y sin escribir en los apuntes.

## T10. [FIX] documento de la donación de dinero
- **Estado**: ✅ Hecho; el documento de una donación otorgada es hoy el Recibo y el de una recibida el Certificado (`ta-86967-donation-received-documents`)
- **Archivos**: `models/account_move.py` (`is_stock_valuation_entry`, guarda de impresión), `views/account_move_views.xml`, `report/donation_certificate_template.xml`, `tests/test_sale_account_move.py`, `tests/test_stock_move.py`
- **Done when**: REQ-DON-016 cubierto: el documento de dinero enuncia el monto numérico, el equivalente alterno y la tasa; el asiento de valoración de un picking no ofrece el botón y la acción lo rechaza.

## T11. [CLN] quitar `_logger` sin usar
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_picking.py`, `stock_move.py`, `account_move_line.py`, `stock_picking_type.py`, `product_template.py`
- **Done when**: no quedan `_logger` ni `import logging` sin uso en los modelos.

## T12. [I18N] traducción es_VE
- **Estado**: ✅ Hecho
- **Archivos**: `i18n/es_VE.po`
- **Done when**: sin entradas de scrap ni términos vacíos, y los textos nuevos salen en español (error de validación, documento de la entrega, menú Donaciones).

## T13. [DOCS] openspec de la migración
- **Estado**: ✅ Hecho
- **Archivos**: este change, `openspec/specs/l10n_ve_donation/spec.md` (vigente)
- **Done when**: la spec vigente y el delta describen REQ-DON-001 a 017 y `STATE.md` refleja la verificación real.

## Conservado de V19 sin cambios
- Baja de activos con mensaje (`models/account_asset.py`, `tests/test_account_asset.py`).

## Seguimiento en otros módulos
- `binaural_stock_dispatch_note` (integra-addons): contacto de solo lectura solo con pedido.
- `l10n_ve_inventory_book` (integra-addons): `test_outgoing_with_donation` debe esperar 'Donación'.
- `binaural_subsidiary_stock` (integra-addons): ver el informe a Producto.
- Módulo propio del cliente (17): `test_22` (espera el sufijo), restauración del donante tras publicar y líneas sin donante, al migrarlo.
