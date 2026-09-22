# Feature: toda orden del Kiosko emite factura (l10n_ve_pos_self_order)

## Why

`l10n_ve_pos` exige que **toda** venta del PdV emita factura fiscal (SENIAT).
En la caja normal eso se garantiza con un patch JS que fuerza `to_invoice=true`
en el modelo `PosOrder` del cliente
(`l10n_ve_pos/static/src/overrides/models/pos_order.js` — `setup` línea 23-25 y
`serializeForORM`). Ese patch vive en el bundle del **cajero**
(`point_of_sale._assets_pos`).

El Kiosko/Autopedido (`pos_self_order`) carga un bundle **distinto**
(`pos_self_order.assets`) que nunca incluye ese patch. Rastreando el camino
real de una orden de Kiosko en este despliegue (pago con Megasoft VPOS, ver
[[binaural-megasoft-self-order-kiosk]]), aparecen **dos** huecos que dejan la
orden del Kiosko SIN factura:

1. **`to_invoice` llega `False`.** El cliente del Kiosko no manda el campo, y
   el core `pos_self_order.pos.order._check_pos_order`
   (`pos_self_order/models/pos_order.py:230`) lo copia tal cual del payload
   (`'to_invoice': order.get('to_invoice')`). Nadie lo fuerza server-side.

2. **Aunque `to_invoice` fuera `True`, nadie genera la factura.** La
   finalización de pago del Kiosko de Megasoft
   (`binaural_megasoft_self_order.pos.payment.method._payment_request_from_kiosk`)
   llamaba solo a `action_pos_order_paid()`, que únicamente pone
   `state='paid'` (`point_of_sale/models/pos_order.py:857-885`). Nunca llamaba a
   `_process_saved_order` ni a `_generate_pos_order_invoice`. El patrón correcto
   está en el core: `pos_online_payment/models/payment_transaction.py:63-64`
   cierra la orden de autopedido con `pos_order._process_saved_order(False)`,
   que internamente hace `action_pos_order_paid` + `_create_order_picking` +
   costo + `_generate_pos_order_invoice()` cuando `to_invoice=True`.

Lo que **ya estaba correcto** (no se toca): los montos foráneos del pago. El
path de Megasoft ya registra el pago con
`foreign_amount = order.foreign_amount_total` y
`foreign_rate = order.foreign_currency_rate`, y
`l10n_ve_pos.pos.payment._create_payment_moves` los usa para escribir
`foreign_debit`/`foreign_credit` en el asiento de pago. El total foráneo de la
orden ya lo garantizan `l10n_ve_pos.pos.order._complete_values_from_session` +
el override `recompute_prices()` de este módulo (ver
[[l10n-ve-pos-self-order-foreign-amount-fix]]), y `_prepare_invoice_vals`
inyecta el `foreign_rate` en la factura. **Todo ese cálculo foráneo solo se
dispara si la factura efectivamente se genera** — que es justo lo que faltaba.

## What Changes

### Reparto de responsabilidades (por qué cada fix vive donde vive)

- **Forzar `to_invoice` = regla l10n genérica** → vive en
  `l10n_ve_pos_self_order`, independiente del método de pago. Cubre TODOS los
  caminos de finalización del Kiosko (Megasoft y el path core de orden en \$0,
  que ya llama `_process_saved_order(False)` directo desde
  `pos_self_order.process_order`).
- **Disparar la factura tras el pago = específico del proveedor** → cada
  integración de terminal decide *cuándo* la orden queda pagada
  (`_payment_request_from_kiosk`). Para Megasoft (verificación síncrona en el
  navegador) la finalización es inmediata y vive en
  `binaural_megasoft_self_order`.

### `l10n_ve_pos_self_order/models/pos_order.py`

Override de `_check_pos_order` (el método del core que arma los vals de la
orden del Kiosko): fuerza `vals["to_invoice"] = True` cuando
`pos_config.self_ordering_mode == 'kiosk'`.

Gateado a `kiosk` (mismo alcance que la identificación por cédula —
[[pos-self-order-kiosk-identification]]— que es lo que garantiza un
`partner_id` real que facturar). El flujo `mobile`/QR de mesas NO tiene esa
garantía y no debe forzarse a facturar contra el consumidor genérico.

### `binaural_megasoft_self_order/models/pos_payment_method.py`

En `_payment_request_from_kiosk`, se reemplaza `action_pos_order_paid()` por la
finalización completa, espejo de `pos_online_payment`:

```
if not order.account_move:
    if order.state == "draft" and order._is_pos_order_paid():
        order._process_saved_order(False)
elif order.state == "draft":
    order.write({"state": "done" if order.to_invoice else "paid"})
```

Idempotencia frente al reintento (`process_order` reabre la orden a `draft` en
CADA llamada): el pago ya estaba protegido por la existencia de la línea de
pago (`already_paid`); la factura se protege por la existencia de
`account_move`. Si la orden ya se facturó pero se perdió la respuesta,
`process_order` la reabrió a `draft` y aquí se restaura su estado final sin
volver a facturar.

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-invoicing`: toda orden completada en el Kiosko emite
  factura fiscal (SENIAT), con los montos en moneda foránea
  (`foreign_debit`/`foreign_credit`) correctos en el asiento de pago.

## Impact

- **Módulos**: `l10n_ve_pos_self_order` (`models/pos_order.py` — override de
  `_check_pos_order`), `binaural_megasoft_self_order`
  (`models/pos_payment_method.py` — finalización de `_payment_request_from_kiosk`).
- **No toca** `l10n_ve_pos`, `pos_self_order` ni el core.
- **Depende de** que la orden llegue con `partner_id` (garantizado por
  [[pos-self-order-kiosk-identification]]) y de que `pos.config` tenga
  `invoice_journal_id` configurado (precondición del core:
  `_process_saved_order` levanta `UserError` "No invoice journal configured"
  si falta — igual que en la caja normal).
- **Tests**: cobertura Python en ambos módulos (ver `tasks.md`). No se ejecutan
  en el mismo pase (convención del repo: el usuario los corre).
- **Riesgo de despliegue**: medio. Facturar en el path síncrono del kiosko
  añade el posteo del `account.move` a la RPC de pago (mismo trabajo que hace
  la caja por orden). Probar en navegador con `megasoft_kiosk_test_mode`
  (modo simulación, sin VPOS) antes de dar por bueno.
- **Fuera de alcance**:
  - Otros proveedores de pago del kiosko (adyen/stripe/etc.): no se usan en VE;
    su finalización nativa (terminal asíncrono) sigue su propio camino. Si
    alguno se activara, requeriría el mismo espejo de `_process_saved_order`.
  - Orden del Kiosko en \$0: el path core ya la factura con `to_invoice=True`
    forzado; un `account.move` en \$0 es un borde improbable en el Kiosko y no
    se trata aquí.

References: Tarea 78767 (Autopago POS V19),
https://binaural.odoo.com/odoo/action-341/78767
