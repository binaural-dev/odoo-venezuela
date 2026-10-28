# Fix: `pos.order.foreign_amount_total` NOT NULL al crear pedidos desde el Kiosko/Autopedido (`pos_self_order`)

## Why

Al activar el modo Kiosko nativo de Odoo (`pos_self_order`, `pos.config.self_ordering_mode = 'kiosk'`) en la caja "Kiosko" de la BD `pos2` y registrar un pedido de prueba, el `INSERT` de `pos_order` falla en el servidor:

```
ERROR: null value in column "foreign_amount_total" of relation "pos_order" violates not-null constraint
```

### Causa raíz

`foreign_amount_total` (`models/pos_order.py:10-12`) es `fields.Float(required=True)` sin default. El único sitio que lo rellena es un patch JS —`static/src/overrides/models/pos_order.js:351-354`, método `serializeForORM()` parcheado sobre `PosOrder`— registrado **solo** en el bundle de assets `point_of_sale._assets_pos` (`__manifest__.py:39-43`), el bundle de la app de caja normal (`/odoo/point_of_sale`).

El Kiosko es una app OWL completamente distinta (`pos_self_order`, módulo nativo de Odoo) que carga su **propio** bundle, `pos_self_order.assets`. Ese bundle nunca incluye los overrides de `l10n_ve_pos`, así que el `serializeForORM()` que corre en el Kiosko es el nativo de Odoo, sin `foreign_amount_total`.

Arreglarlo solo en JS no habría sido suficiente: `pos_self_order/models/pos_order.py::_check_pos_order` reconstruye el payload que llega a `sync_from_ui` con un diccionario de campos **fijo y hardcodeado** — `foreign_amount_total` no está en esa lista, así que cualquier valor extra que el cliente mande se descarta antes del `create()`. El fix tiene que vivir en el servidor.

`foreign_currency_rate` (mismo modelo) y los campos foráneos de `pos.order.line` (`foreign_price`/`foreign_subtotal`/`foreign_total`) y `pos.payment` (`foreign_amount`/`foreign_rate`) **no** son `required=True` — no rompen el INSERT, pero para pedidos del Kiosko quedarán en `0` si no se corrigen (bug de datos silencioso, no crash). Confirmado con grep sobre `src/odoo-venezuela/l10n_ve_pos*/models/*.py` que `foreign_amount_total` es el único `required=True` relevante en la cadena de creación de un pedido.

## What Changes

- `l10n_ve_pos/models/pos_order.py`: nuevo override de `_complete_values_from_session` (hook oficial del core, `point_of_sale/models/pos_order.py:570-586`, llamado desde `create()` con la sesión ya resuelta — mismo patrón que usa `pos_sale/models/pos_order.py:20-23`). Con `values.setdefault(...)` se completan `foreign_amount_total`/`foreign_currency_rate` usando los métodos ya centralizados de `pos.config` (`_convert`/`_get_pos_conversion_rate`, `models/pos_config.py:76-154`) cuando el canal que crea el pedido no los mandó. Es un no-op para la caja normal (el JS ya los manda) y cubre cualquier canal futuro, no solo el Kiosko.
- Nuevo módulo `l10n_ve_pos_self_order` (`depends=["l10n_ve_pos", "pos_self_order"]`, `auto_install=True`, mismo patrón que el módulo nativo `pos_online_payment_self_order`): override de `recompute_prices()` (`pos_self_order/models/pos_order.py:241-261`, método que solo existe en `pos_self_order` — por eso no puede vivir dentro de `l10n_ve_pos` sin forzar esa dependencia a todos los clientes VE que no usan Kiosko). El controlador del Kiosko llama siempre a `recompute_prices()` tras crear/actualizar un pedido para recalcular `amount_total`/`amount_tax` de forma autoritativa contra el catálogo real (defensa contra manipulación del cliente); este override recalcula `foreign_amount_total`/`foreign_currency_rate` a partir de ese total ya correcto, con los mismos métodos de `pos.config`.

## Impact

- **Capability**: `pos-self-order-foreign-amount` (nueva).
- **Módulo**: `l10n_ve_pos` (`models/pos_order.py`, backend puro) + nuevo `l10n_ve_pos_self_order` (`models/pos_order.py`, backend puro). Ninguno de los dos toca assets JS ni vistas — requiere actualizar ambos módulos (`-u l10n_ve_pos,l10n_ve_pos_self_order` o Apps → Actualizar), no reinicio de worker aparte de la actualización normal de módulo.
- **Tests**: cobertura Python nueva en `l10n_ve_pos/tests/` cubriendo los 3 escenarios del spec (ver `specs/pos-self-order-foreign-amount/spec.md`). No se ejecuta en este pase (pendiente, el usuario la corre).
- **Riesgo de despliegue**: bajo. `_complete_values_from_session` usa `setdefault`, así que el flujo de la caja normal (que ya manda ambos valores desde JS) queda bit a bit igual. `recompute_prices()` solo lo invoca `pos_self_order`, no hay otro consumidor en el repo ni en `odoo/addons` (incluyendo los módulos enterprise `pos_self_order_iot`/`pos_self_order_preparation_display`, verificados sin definir ni llamar ese método).
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - `pos.order.line.foreign_price/foreign_subtotal/foreign_total` y `pos.payment.foreign_amount/foreign_rate` quedan en `0` para pedidos del Kiosko (no son `required=True`, no rompen nada, pero son incorrectos en recibos/reportes). Mismo patrón que `l10n-ve-pos-payment-foreign-amount-always-computed`, en un change aparte — pendiente de saber cómo se van a crear los pagos del Kiosko (ver siguiente punto).
  - La caja "Kiosko" de `pos2` todavía no tiene ningún método de pago con terminal soportado (Adyen/Stripe/Razorpay/Viva.com/Pine Labs) ni proveedor de pago en línea habilitado — bloqueador ya detectado en conversación previa, no relacionado con este bug. Este fix desbloquea la **creación** del pedido; el **pago** en el Kiosko seguirá fallando hasta resolver eso aparte.
  - Caveat menor de redondeo: el controlador del Kiosko (`pos_self_order/controllers/orders.py:23-27`) hace una segunda escritura de `amount_total` derivada de `_get_order_prices(order_ids.lines)` **después** de `recompute_prices()`, con un epsilon de redondeo potencialmente distinto al que usa `recompute_prices()` internamente. `foreign_amount_total` puede quedar calculado sobre un `amount_total` no *exactamente* el último persistido (magnitud de céntimos). No afecta la factura, que usa `foreign_currency_rate`, no `foreign_amount_total` (`_prepare_invoice_vals`, `l10n_ve_pos/models/pos_order.py`). Defecto preexistente del core, no introducido por este change.
