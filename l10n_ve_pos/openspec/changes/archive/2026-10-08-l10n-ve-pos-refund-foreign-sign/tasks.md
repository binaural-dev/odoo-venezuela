# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_refund_foreign_sign.py`: guarda del servidor (signo
      invertido, consistente, venta, monto foráneo en 0)
- [x] 1.2 `static/tests/unit/pos_order_refund_sign.test.js`: totales con
      signo, conversiones, tasa positiva, orden mixta, netos opuestos
- [x] 1.4 `static/tests/unit/payment_model.test.js`: signo y excedente del pago
      foráneo en un reembolso con tasa agregada
- [x] 1.3 Batería e2e de `binaural_pos_multicurrency`: los `assertKnownBug` de
      H1 pasan a aserciones

## 2. Corrección

- [x] 2.1 `pos_order.js`: `_sumForeignLines` × `orderSign`
- [x] 2.2 `pos_order.js`: quitar los `Math.abs` de
      `get_effective_foreign_multiplier` (cae a la tasa viva si la proporción
      no es positiva) y `get_display_rate`
- [x] 2.3 `pos_order.py`: `_align_foreign_signs` desde `_process_saved_order`
- [x] 2.5 `payment_model.js`: signo del reembolso en la rama sin tasa exacta
- [x] 2.6 Migración 1.20: `_align_foreign_signs` en las órdenes de sesiones no
      cerradas (probada en posv19 con odoo shell y rollback)
- [x] 2.4 Manifiesto 1.20

## 3. Verificación

- [x] 3.1 Tests de `l10n_ve_pos` (84/84, rojo antes del fix: 1 fallo) y batería e2e en verde; tours 3/3
- [x] 3.2 Navegador (posv19, sesión 472): reembolso en la Caja VES pagado con efectivo $ (−11,60), esperado del cajón 149,80 $, cierre sin diferencia ni error
- [x] 3.3 (trasladada a integra-addons PR #2896) NC con la máquina fiscal en base foránea (`l10n_ve_pos_mf`): la MF todavía no funciona en las cajas en otra moneda; se valida al implementarla en integra-addons PR #2896 (tasks 2c.1 de `pos-multicurrency-e2e-pruebas`)
