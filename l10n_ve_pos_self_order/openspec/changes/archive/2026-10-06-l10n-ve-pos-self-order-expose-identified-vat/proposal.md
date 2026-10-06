# Feature: exponer la cédula identificada al cliente del Kiosko

## Why

El change [[l10n-ve-pos-self-order-kiosk-partner-identification]] identifica al
cliente por cédula/RIF al iniciar el Kiosko y le asigna el `partner_id` a la
orden, pero la cédula (`vat`/`prefix_vat`) NO queda disponible en el cliente
del Kiosko:

- Los endpoints `identify`/`identify/create` devolvían solo `id`/`name`/`phone`.
- El core lee del partner únicamente `id`/`name`/`write_date`/
  `property_product_pricelist` (`pos_self_order.res.partner.
  _load_pos_self_data_read`).

Las integraciones de pago que necesitan la cédula del cliente —hoy Megasoft
(`binaural_megasoft_self_order`), que la manda al VPOS igual que el cajero
(`partner.vat`)— no tenían de dónde leerla en el kiosko y tendrían que volver a
pedirla, duplicando la identificación que el cliente ya hizo al arrancar.

## What Changes

- `controllers/orders.py`: los endpoints `identify` y `identify/create`
  devuelven también `vat` y `prefix_vat`. No es una fuga de datos: es la
  cédula que el propio cliente acaba de teclear para identificarse.
- `models/res_partner.py` (nuevo): `_load_pos_self_data_read` inyecta
  `vat`/`prefix_vat` sobre lo que devuelve el core (mismo patrón que
  `l10n_ve_pos.pos.order._load_pos_data_read`), para que sobrevivan a
  re-sincronizaciones del partner, no solo al momento de identificarse.

El cliente del kiosko YA reconoce estos campos en el esquema de `res.partner`
(el esquema sale de `_load_pos_self_data_fields` → `_load_pos_data_fields`, que
incluye `vat`/`phone` del core y `prefix_vat` de `l10n_ve_pos`), así que
`connectNewData` los acepta sin el error "field does not exist" del motor
`related_models`.

## Capabilities

### Modified Capabilities

- `pos-self-order-kiosk-identification`: la cédula identificada
  (`vat`/`prefix_vat`) queda disponible en el partner de la orden del cliente
  del Kiosko, para reuso por integraciones de pago sin re-pedirla.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` — `controllers/orders.py` (reads de los
  dos endpoints), nuevo `models/res_partner.py`, `models/__init__.py`.
- **No toca** `l10n_ve_pos` ni `pos_self_order`.
- **Consumidor**: `binaural_megasoft_self_order` (change
  `binaural-megasoft-self-order-kiosk`) lee `order.partner_id.vat` en vez de un
  popup de cédula propio.
- Sin migración de datos. Requiere upgrade del módulo (endpoints + modelo).

References: Tarea 78767 (Autopago POS V19).
