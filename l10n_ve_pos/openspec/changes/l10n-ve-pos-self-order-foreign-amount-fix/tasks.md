# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducir el error a partir del log de creación de pedido en el Kiosko
      (`INSERT INTO "pos_order"` sin `foreign_amount_total` en la lista de
      columnas → `null value ... violates not-null constraint`)
- [x] 1.2 Rastrear `foreign_amount_total` hasta `l10n_ve_pos/models/pos_order.py:10-12`
      (`required=True`, sin default) y hasta el único punto que lo rellena
      (`static/src/overrides/models/pos_order.js::serializeForORM`)
- [x] 1.3 Confirmar que ese patch JS solo se registra en el bundle
      `point_of_sale._assets_pos` (`l10n_ve_pos/__manifest__.py:39-43`), no en
      `pos_self_order.assets` (bundle propio del Kiosko)
- [x] 1.4 Confirmar que un fix solo-JS sería insuficiente:
      `pos_self_order/models/pos_order.py::_check_pos_order` reconstruye el
      payload de `sync_from_ui` con un whitelist fijo que no incluye
      `foreign_amount_total`
- [x] 1.5 Grep de `required=True` en `l10n_ve_pos*/models/*.py`: confirmar que
      `foreign_amount_total` es el único campo foráneo bloqueante; los demás
      (`foreign_currency_rate`, `pos.order.line.foreign_*`,
      `pos.payment.foreign_amount/foreign_rate`) no rompen el INSERT

## 2. Implementación

- [x] 2.1 `l10n_ve_pos/models/pos_order.py`: override `_complete_values_from_session`,
      `values.setdefault(...)` con `pos.config._convert`/`_get_pos_conversion_rate`
- [x] 2.2 Scaffold del módulo `l10n_ve_pos_self_order`
      (`__init__.py`, `__manifest__.py` con `depends=["l10n_ve_pos","pos_self_order"]`,
      `auto_install=True`, `models/__init__.py`)
- [x] 2.3 `l10n_ve_pos_self_order/models/pos_order.py`: override `recompute_prices()`
      recalculando `foreign_amount_total`/`foreign_currency_rate` tras `super()`

## 3. Tests

- [x] 3.1 Test Python (`l10n_ve_pos/tests/test_self_order_foreign_amount.py`):
      creación de pedido sin `foreign_amount_total` en `vals` → se completa
      vía `_convert` (más el caso de compañía sin moneda foránea → `0.0`)
- [x] 3.2 Test Python (mismo fichero): creación de pedido con
      `foreign_amount_total` ya presente en `vals` → no se pisa
- [x] 3.3 Test Python (`l10n_ve_pos_self_order/tests/test_recompute_prices_foreign_amount.py`):
      `recompute_prices()` corrige `foreign_amount_total`/`foreign_currency_rate`
      tras cambiar `amount_total` de forma autoritativa
- [ ] 3.4 Correr la suite de tests Python de `l10n_ve_pos` /
      `l10n_ve_pos_self_order` en el contenedor `proj` — pendiente, no
      ejecutado en este pase (el usuario la corre)

## 4. Pendiente (fuera de alcance de este change, con seguimiento)

- [ ] 4.1 `pos.order.line.foreign_price/foreign_subtotal/foreign_total` en 0
      para pedidos del Kiosko — mismo patrón que
      `l10n-ve-pos-payment-foreign-amount-always-computed`, change aparte
- [ ] 4.2 `pos.payment.foreign_amount/foreign_rate` en 0 para pagos creados
      desde el Kiosko — depende de cómo se resuelva el método de pago (ver
      4.3), change aparte
- [ ] 4.3 Configurar un método de pago válido para el Kiosko (terminal
      soportado o proveedor de pago en línea habilitado) — bloqueador ya
      detectado en conversación previa, no relacionado con este bug
- [ ] 4.4 Epsilon de redondeo entre `recompute_prices()` y la segunda
      escritura de `amount_total` del controlador del Kiosko (ver
      `proposal.md`, "Fuera de alcance") — defecto preexistente del core, no
      introducido por este change

## 5. OpenSpec

- [x] 5.1 `openspec change validate l10n-ve-pos-self-order-foreign-amount-fix` → válido
