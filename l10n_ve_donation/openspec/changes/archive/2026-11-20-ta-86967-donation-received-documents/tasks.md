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
- **Estado**: ✅ Hecho: este change y la spec vigente (REQ-DON-018 a 034).

## T8. [FIX] ajustes de la validación funcional (staging, 19/11)
- **Estado**: ✅ Hecho
- **Archivos**: `models/` (`account_move.py`, `account_move_line.py`, `stock_move.py`, `stock_picking.py`, `res_company.py`, `res_config_settings.py`, `res_partner.py`), `report/`, `views/`, `security/res_groups.xml`, `i18n/es_VE.po`, tests
- **Migración**: `migrations/19.0.3.0.1/post-migration.py` (versión `19.0.3.0.1`): mueve el grupo Gestor a su privilegio propio y pasa el Certificado a carta si sigue en A4.
- **Done when**: REQ-DON-029 a 034 cubiertos: cuentas de gasto, asiento de la recepción marcado, donación por el extracto, formato de los documentos, nota de crédito en moneda extranjera, botón de reverso y grupo Gestor.

## Seguimiento en otros módulos
- Módulo propio del cliente: paciente/médico, extras del Recibo, texto legal y forma de pago; elimina lo que pasó al módulo compartido.
- Producto: forma de pago/banco/referencia.
- `integra-addons` (`binaural_subsidiary_stock`, `binaural_stock_dispatch_note`, `l10n_ve_inventory_book`): ver el informe a Producto.
