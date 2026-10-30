## ADDED Requirements

### Requirement: El cliente identificado queda en la orden que guarda el servidor

Las rutas `identify`, `identify/create` y `set_phone` SHALL devolver el `id`
del partner firmado (`pos.order._get_signed_self_partner_id` de la caja), la
única forma que el core de Odoo 19 acepta como `partner_id` de una orden del
Kiosko. Así, la orden sincronizada con `process-order` SHALL guardarse con ese
cliente y la orden local SHALL conservarlo con su cédula.

#### Scenario: Cliente existente identificado por cédula

- **GIVEN** un `res.partner` con `prefix_vat='V'` y `vat='12345678'`
- **WHEN** el cliente se identifica con esa cédula en el Kiosko
- **THEN** `identify` devuelve el partner con el `id` firmado, que
  `pos.order._get_self_partner_from_token` resuelve a ese partner

#### Scenario: Cliente creado o completado desde el Kiosko

- **GIVEN** una cédula no registrada, o un cliente registrado sin teléfono
- **WHEN** el Kiosko lo crea (`identify/create`) o le completa el teléfono
  (`set_phone`)
- **THEN** la respuesta trae el partner con el `id` firmado, también cuando
  `identify/create` devuelve un contacto que ya existía (dedup)

#### Scenario: La orden del Kiosko se guarda con el cliente identificado

- **GIVEN** un cliente identificado en el Kiosko y una orden con productos
- **WHEN** el Kiosko sincroniza la orden con `process-order`
- **THEN** la `pos.order` queda con el `partner_id` del cliente y la orden
  local conserva el partner con su cédula, así que una integración de pago
  (Megasoft) la lee de `order.partner_id.vat` sin bloquear el pago

#### Scenario: Un id sin firmar no asigna cliente

- **GIVEN** una orden del Kiosko cuyo `partner_id` es un id numérico
- **WHEN** el servidor arma la orden (`_check_pos_order`)
- **THEN** el core no asigna ningún cliente; por eso las rutas de
  identificación nunca devuelven el id sin firmar
