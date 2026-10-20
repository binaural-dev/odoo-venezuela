## ADDED Requirements

### Requirement: Desglose por línea de factura en moneda de la compañía

El sistema DEBE (MUST) exponer, por cada línea de producto de una factura, un desglose en la moneda de la compañía (`account.move.company_currency_line_totals`, JSON indexado por id de línea) con precio unitario, cantidad, subtotal sin impuesto, subtotal con impuesto, monto de impuesto, monto y tipo de descuento, e impuestos aplicados (id, nombre, si el impuesto está incluido en el precio). El subtotal y el monto de impuesto de cada línea DEBEN (MUST) reconciliar exactamente con el `balance` real posteado en el asiento -- nunca una conversión de moneda independiente que pueda diferir del asiento por redondeo.

Cuando varias líneas comparten un mismo impuesto, su monto de impuesto DEBE (MUST) repartirse proporcionalmente al `balance` de cada línea, sin perder ni inventar ninguna unidad de la moneda. Los impuestos de tipo `group` DEBEN (MUST) resolverse por su jerarquía completa de impuestos hijos, no solo por coincidencia directa con `tax_ids` de la línea.

#### Scenario: Factura en moneda distinta a la de la compañía

- **WHEN** se crea una factura en USD o EUR con líneas de producto e impuestos
- **THEN** `company_currency_line_totals` contiene, para cada línea, los montos equivalentes en la moneda de la compañía, y la suma de esos montos coincide exactamente con los `balance` de las líneas de producto e impuesto del asiento

#### Scenario: Varias líneas bajo el mismo impuesto

- **WHEN** tres o más líneas de producto comparten la misma tasa de impuesto
- **THEN** el monto de impuesto de cada línea es proporcional a su propio `balance`, y la suma de los montos por línea coincide exactamente con el `balance` de la línea de impuesto del asiento

#### Scenario: Impuesto de tipo grupo

- **WHEN** una línea lleva un impuesto compuesto (`amount_type='group'`) con varios impuestos hijos
- **THEN** el monto de impuesto de la línea incluye la suma de todos los impuestos hijos del grupo, no se descarta
