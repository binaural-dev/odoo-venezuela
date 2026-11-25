## ADDED Requirements

### Requirement: Precio alterno completado en el servidor para las líneas del PdV

Una línea del PdV con precio unitario distinto de cero y sin precio alterno DEBE (MUST) completarse en el servidor, al crearla o actualizarla, con precio unitario × tasa del PdV estampada en la orden (`pos.order.foreign_currency_rate`; en un reembolso, la de la venta original), con su signo y la precisión "Foreign Product Price". El sistema NO DEBE (MUST NOT) cambiar un alterno presente, salvo las excepciones de los escenarios.

#### Scenario: Línea liquidada desde una orden de venta

- **GIVEN** una orden de venta con dos líneas de 600 Bs y una caja con tasa 600 Bs/USD
- **WHEN** el cajero liquida la orden de venta en el PdV y las líneas se sincronizan sin precio alterno
- **THEN** cada línea queda con precio alterno 1,00 USD, sin importar el orden en que el PdV cargó los parches de `pos_sale` y `l10n_ve_pos`

#### Scenario: Orden de venta con tasa distinta a la del PdV

- **GIVEN** una orden de venta con su propia tasa (p. ej. 700 Bs/USD) liquidada en un PdV cuya orden estampó 600 Bs/USD
- **WHEN** las líneas se sincronizan sin precio alterno y se factura
- **THEN** el precio alterno de la línea y de la factura sale con la tasa del PdV (600), no con la de la orden de venta ni la del día

#### Scenario: Línea de precio negativo

- **WHEN** se sincroniza sin precio alterno una línea de -1.200 Bs (anticipo descontado o descuento) en una orden con tasa 600 Bs/USD
- **THEN** la línea queda con precio alterno -2,00 USD

#### Scenario: Caja en la moneda alterna

- **WHEN** la moneda de la caja es la moneda alterna de la compañía, la orden estampa tasa 1 y una línea llega sin precio alterno
- **THEN** su precio alterno es su precio unitario (× 1), redondeado a la precisión "Foreign Product Price"
- **AND** si la orden no trae tasa y la caja es alterna, también es su precio unitario
- **AND** si la orden no trae tasa y la caja no es alterna, el precio alterno no se completa

#### Scenario: Precio cuyo alterno redondea a 0

- **GIVEN** la precisión "Foreign Product Price" en 2 y una orden a 600 Bs/USD
- **WHEN** se sincroniza una línea de 2 Bs sin precio alterno (2 / 600 = 0,0033)
- **THEN** la línea queda con precio alterno 0,00 y la orden se guarda sin error: un alterno en 0 producto del redondeo es válido
- **AND** si luego su precio cambia a 600 Bs, el alterno pasa a 1,00 USD, y si vuelve a 2 Bs, a 0,00 USD

#### Scenario: Precio alterno ya presente

- **WHEN** una línea llega con precio alterno distinto de cero (calculado por el PdV o copiado de la línea original de un reembolso)
- **THEN** el servidor lo conserva sin cambios

#### Scenario: Excepciones al precio alterno presente

- **WHEN** se actualiza una línea con un precio nuevo sin un precio alterno nuevo (requirement "Precio alterno recalculado al cambiar el precio sin precio alterno nuevo"), o se trata de la línea del descuento global de `pos_discount` (#16547)
- **THEN** el precio alterno se recalcula, aunque hubiera uno presente

#### Scenario: Reembolso de una venta sin precio alterno

- **GIVEN** una venta a tasa R1 cuya línea quedó guardada sin precio alterno
- **WHEN** se reembolsa a tasa R2 y la línea de reembolso tampoco trae precio alterno
- **THEN** la línea de reembolso queda con su precio unitario × R1, la tasa de la venta original

#### Scenario: Sin tasa o sin precio

- **WHEN** la orden no tiene tasa, o el precio unitario de la línea es cero
- **THEN** el precio alterno de la línea queda como llegó

#### Scenario: Borrador sincronizado de nuevo

- **WHEN** el PdV sincroniza otra vez una orden en borrador y la actualización de una línea trae precio alterno 0 con precio distinto de cero
- **THEN** la línea queda con el precio alterno calculado, no en 0

### Requirement: Precio alterno recalculado al cambiar el precio sin precio alterno nuevo

Cuando una actualización de una línea del PdV cambia su precio unitario y no trae un precio alterno distinto del guardado, el sistema DEBE (MUST) recalcular el precio alterno con el cálculo de "Precio alterno completado en el servidor para las líneas del PdV". Si la actualización trae un precio alterno distinto del guardado, el sistema DEBE (MUST) conservar el que llegó.

#### Scenario: Precio editado después de sincronizar un borrador

- **GIVEN** una línea liquidada desde una orden de venta, sincronizada en borrador y con precio alterno 1,00 USD (600 Bs a 600 Bs/USD)
- **WHEN** el cajero cambia el precio de la línea a 900 Bs y la orden se sincroniza con el precio alterno anterior
- **THEN** la línea queda con precio alterno 1,50 USD

#### Scenario: Cambio de precio con su precio alterno

- **WHEN** una actualización cambia el precio unitario y trae un precio alterno distinto del guardado
- **THEN** la línea queda con el precio alterno que llegó

## MODIFIED Requirements

### Requirement: La factura del PdV hereda la tasa de la orden

La factura generada por una orden del PdV DEBE (MUST) crearse con `foreign_rate` y `foreign_inverse_rate` iguales a `foreign_currency_rate` de la orden y `manually_set_rate = True` (`_prepare_invoice_vals`), y cada línea de factura recibir el `foreign_price` de su línea de orden (`_get_invoice_lines_values`), o el que completa el servidor si la línea no lo tiene y su precio no es cero, de modo que `l10n_ve_accountant` no recalcule la tasa con la del día.

(Antes: cada línea de factura recibía el `foreign_price` de su línea de orden tal cual, aunque fuera 0.)

#### Scenario: Facturación de la orden

- **WHEN** el backend factura una orden del PdV
- **THEN** la factura lleva la tasa congelada de la orden y sus líneas el precio alterno de la venta

#### Scenario: Factura de una orden de venta liquidada en el PdV

- **GIVEN** una orden del PdV a 600 Bs/USD que liquida dos líneas de 600 Bs de una orden de venta, con impuestos de 48 y 132 Bs, y un total alterno cobrado de 2,30 USD
- **WHEN** se genera su factura
- **THEN** cada línea de producto lleva precio alterno 1,00 USD, subtotal alterno 1,00 USD y crédito alterno 1,00 USD, y la CxC lleva 2,30 USD, igual al total alterno cobrado

#### Scenario: Línea de orden guardada sin precio alterno

- **GIVEN** una orden sincronizada antes de este cambio, con una línea de 600 Bs guardada sin precio alterno, a tasa 600 Bs/USD
- **WHEN** se factura
- **THEN** la línea de factura lleva precio alterno 1,00 USD y no 0,00, aunque la línea de orden siga sin él
