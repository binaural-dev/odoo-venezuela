# Fix: el Kiosko conserva el cliente identificado en la orden (ti 16110)

## Why

Ticket 16110 (referencia #16148, Monfarmacia): en el Autopago, el cliente se
identifica por cédula (o se crea en el Kiosko con su cédula), pero al elegir un
método de pago Megasoft aparece "Cliente sin cédula — No se pudo obtener la
cédula del cliente identificado…" y no deja pagar. En el staging de Monfarmacia
(30/10/2026, Autopago CCCT 1) el contacto quedó creado con su cédula, pero las
órdenes del Kiosko se guardaron sin `partner_id`.

En Odoo 19 el core del Kiosko solo acepta como `partner_id` de la orden un id
firmado (`"<id>-<hmac>"`, `pos.order._get_signed_self_partner_id`):
`_check_pos_order` lo valida con `_get_self_partner_from_token` y descarta
cualquier otro valor. Las rutas `identify`, `identify/create` y `set_phone`
devolvían el id numérico. Al sincronizar, `/pos-self-order/process-order`
guardaba la orden sin cliente y el Kiosko pisaba su orden local con esa
respuesta (`connectNewData`), así que:

- `binaural_megasoft_self_order` no encontraba `order.partner_id.vat` y
  bloqueaba el pago;
- la factura del Kiosko (siempre `to_invoice`) y el payload fiscal de
  `l10n_ve_pos_mf_self_order` se quedaban sin cliente.

## What Changes

- `controllers/orders.py`: las tres rutas de identificación devuelven el
  partner con el `id` firmado (`_ve_partner_payload`), igual que
  `/pos-self-order/validate-partner` del core. Los demás campos (`name`,
  `vat`, `prefix_vat`) y el resto del contrato (sin `phone`, `has_phone`,
  rate-limit) no cambian.
- El JS de la pantalla de identificación no cambia: `assignPartner` conecta el
  partner con ese id, como el popup nativo, y la orden lo manda tal cual en
  `partner_id`. La respuesta de `process-order` trae el mismo id firmado, así
  que el partner (con su cédula) sigue en la orden local.

## Capabilities

### Modified Capabilities

- `pos-self-order-kiosk-identification`: el partner identificado se devuelve
  con el id firmado y queda en la orden que guarda el servidor.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` (`controllers/orders.py` y
  `tests/test_kiosk_public_routes.py`). Versión `19.0.1.5.0` → `19.0.1.7.0`
  (la `1.6.0` la usa el PR del ticket 16064, #1545: el que se mergee segundo
  debe revisar su versión).
- **Despliegue**: `-u l10n_ve_pos_self_order` (o reinicio: el cambio es solo
  Python). Sin cambio de esquema.
- **Fuera de alcance**: `session_orders` (panel de órdenes del Kiosko) sigue
  devolviendo ids numéricos de partner y de orden; son órdenes ya pagadas que
  no vuelven a `process-order`.
