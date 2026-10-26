# Spec delta: pos-orderline-foreign-display

## ADDED Requirements

### Requirement: El monto en divisa de un combo se muestra en la línea padre

El sistema SHALL mostrar, en la línea padre de un combo, como monto en divisa
la suma de los montos de sus líneas hijas convertida una sola vez: con impuestos si
`pos.config.iface_tax_included` es `'total'` y sin impuestos en caso
contrario, igual que el precio local que muestra el core. Cada línea hija SHALL
mostrar su parte del precio, en la moneda de la caja y en divisa, como una
línea normal (el core no les pinta precio). Los totales foráneos de la orden
no SHALL cambiar.

#### Scenario: Combo con impuestos incluidos

- **GIVEN** un PdV con `iface_tax_included = 'total'`
- **WHEN** se agrega un combo cuyas hijas valen 464 Bs y 216 Bs con impuestos,
  a 0,025 $/Bs
- **THEN** la línea padre muestra $ 17,00 y las hijas su parte: Bs 464,00 /
  $ 11,60 y Bs 216,00 / $ 5,40

#### Scenario: Combo con impuestos separados

- **GIVEN** un PdV con `iface_tax_included = 'subtotal'`
- **WHEN** se agrega el mismo combo (400 Bs y 200 Bs sin impuestos)
- **THEN** la línea padre muestra $ 15,00

#### Scenario: Reembolso de un combo

- **GIVEN** un combo vendido a 0,02 $/Bs y la tasa del día en 0,025 $/Bs
- **WHEN** se reembolsa
- **THEN** la línea padre del reembolso muestra la suma de sus hijas a la tasa
  de la venta original ($ 13,60), no a la del día

#### Scenario: Orden sincronizada en la pantalla de órdenes

- **GIVEN** un combo vendido a 0,03 $/Bs y la tasa del día en 0,025 $/Bs
- **WHEN** se abre la orden en la pantalla de órdenes
- **THEN** la línea padre muestra la suma de sus hijas a la tasa congelada de
  la orden ($ 20,40)

#### Scenario: Cambios en las hijas

- **GIVEN** un combo en la orden
- **WHEN** cambia el precio, el descuento o la lista de precios de sus hijas
- **THEN** el monto en divisa de la línea padre se recalcula con los montos
  vigentes de las hijas
