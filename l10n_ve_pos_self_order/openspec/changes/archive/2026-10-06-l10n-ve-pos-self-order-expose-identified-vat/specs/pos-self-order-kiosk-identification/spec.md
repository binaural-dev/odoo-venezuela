# Spec delta: pos-self-order-kiosk-identification

## MODIFIED Requirements

### Requirement: Búsqueda de contacto por cédula reutiliza el domain existente

El sistema SHALL buscar un `res.partner` por cédula usando el mismo domain
que `res.partner.check_duplicate_vat` (`prefix_vat` + `vat`), sin
reimplementar la lógica de coincidencia. La respuesta de identificación y de
creación SHALL incluir, además de `id`/`name`/`phone`, la cédula que el propio
cliente tecleó (`vat`/`prefix_vat`) — no es información nueva para él.

#### Scenario: Cédula ya registrada

- **GIVEN** un `res.partner` existente con `prefix_vat='V'`, `vat='12345678'`
- **WHEN** el cliente teclea esa combinación en la pantalla de
  identificación del Kiosko
- **THEN** el servidor lo encuentra y devuelve `id`, `name`, `phone`, `vat` y
  `prefix_vat`, y el cliente pasa directo al catálogo con ese `partner_id`
  asignado a la orden

#### Scenario: Cédula no registrada

- **GIVEN** ninguna combinación `prefix_vat`+`vat` coincidente
- **WHEN** el cliente teclea una cédula nueva
- **THEN** el servidor responde "no encontrado" y el cliente ve el
  formulario de creación (nombre, apellido, teléfono) sin perder la cédula
  ya tecleada

#### Scenario: El endpoint de creación devuelve la cédula tecleada

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos que la búsqueda (`id`,
  `name`, `phone`, `vat`, `prefix_vat`)

## ADDED Requirements

### Requirement: La cédula identificada queda disponible en el cliente del Kiosko

El sistema SHALL exponer `vat`/`prefix_vat` del partner al cliente del Kiosko
también en la carga self-data de `res.partner`
(`_load_pos_self_data_read`), no solo en la respuesta de identificación, para
que sobrevivan a re-sincronizaciones del partner y las integraciones de pago
(p. ej. Megasoft, `binaural_megasoft_self_order`) las reusen desde
`order.partner_id` sin volver a pedirlas.

#### Scenario: Una integración de pago lee la cédula del partner de la orden

- **GIVEN** un pedido del Kiosko cuyo cliente ya se identificó por cédula
- **WHEN** una integración de pago (Megasoft) necesita la cédula para su
  transacción
- **THEN** la lee de `order.partner_id.vat` en el cliente, sin abrir un popup
  ni un segundo flujo de identificación

#### Scenario: La cédula sobrevive a una re-sincronización del partner

- **GIVEN** un partner identificado presente en los modelos del cliente
- **WHEN** el kiosko vuelve a leer ese `res.partner` por la vía self-data
  (p. ej. al sincronizar la orden con el servidor)
- **THEN** el registro conserva `vat`/`prefix_vat`, porque
  `_load_pos_self_data_read` los inyecta en cada lectura
