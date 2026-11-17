Una tarea por unidad de trabajo del módulo.

## T0. [FIX] tasa del documento según la moneda de la compañía
- **Estado**: ✅ Hecho. `_compute_donation_amounts`, REQ-DON-026, tests `test_23b` a `test_23d`.

## T1. [REF] Recibo de donación de las donaciones otorgadas
- **Estado**: ✅ Hecho
- **Archivos**: `report/donation_receipt_*.xml`, `data/donation_receipt_paperformat.xml`, `models/account_move.py`, `models/stock_picking.py`, vistas, tests
- **Done when**: REQ-DON-006, 016, 018, 019 cubiertos.

## T2. [IMP] cuentas de donaciones recibidas y su dirección
- **Estado**: ✅ Hecho
- **Archivos**: `models/res_company.py`, `res_config_settings.py`, `account_move.py`, `views/res_config_setting_views.xml`, `tests/test_received_donation.py`
- **Done when**: REQ-DON-020 y 021 cubiertos; sin cuentas, la suite existente no cambia.

## T3. [FEAT] certificado de donación recibida en dinero
- **Estado**: ✅ Hecho
- **Archivos**: `models/account_move.py`, `report/donation_certificate_*.xml`, `views/account_move_views.xml`, tests
- **Done when**: REQ-DON-022 y 023 cubiertos, incluido el diario con hash.

## T4. [FEAT] recepción de donaciones de mercancía
- **Estado**: ✅ Hecho
- **Archivos**: `models/stock_picking.py`, `report/donation_certificate_*.xml`, `views/stock_picking_views.xml`, `tests/test_received_donation.py`
- **Done when**: REQ-DON-024 y 025 cubiertos, con un asiento de valoración real contra el core 19.

## T5. [FIX] validaciones, guardas y casos límite
- **Estado**: ✅ Hecho
- **Archivos**: `models/` (`account_move.py`, `stock_picking.py`, `res_company.py`, `res_config_settings.py`), plantillas de los documentos, vistas, tests
- **Done when**: recepción inerte sin cuentas; monto y equivalente de un picking; certificado en USD; validación del donante en `_post`; `check_company` y bloqueo del cambio de cuentas; guardas de impresión y reversiones sin documento; beneficiario hijo y marcar la donación después; RIF del contacto comercial; mensajes de la recepción (REQ-DON-020, 022, 024, 025, 027, 028).

## T6. [I18N] texto fuente en inglés y es_VE.po
- **Estado**: ✅ Hecho: plantillas, botones y mensajes en inglés, un solo `es_VE.po` sin `msgstr` vacíos y con el mismo vocabulario.

## T7. [DOCS] openspec
- **Estado**: ✅ Hecho: este change y la spec vigente (REQ-DON-018 a 028).

## Seguimiento en otros módulos
- `higea_donation`: paciente/médico, extras del Recibo, texto legal y forma de pago; elimina lo que pasó al módulo compartido.
- Producto: forma de pago/banco/referencia.
- `integra-addons` (`binaural_subsidiary_stock`, `binaural_stock_dispatch_note`, `l10n_ve_inventory_book`): ver el informe a Producto.
