# Spec delta: exchange-difference-note (residual en divisa, tasa del widget y cuotas)

## ADDED Requirements

### Requirement: La nota de diferencial no reduce el residual en divisa

El parcial que cierra una ND/NC de diferencial contra la línea con el residual
(factura o pago en moneda extranjera) SHALL tener monto en divisa 0 del lado de
esa línea, de modo que su `amount_residual_currency` y el `amount_residual` de
la factura (en su moneda) no cambien por la nota; solo cambia el balance en
moneda de la compañía.

#### Scenario: Pago parcial con tasa distinta (nota del lado de la factura)

- **GIVEN** una factura de 100 USD y un pago de 50 USD con una tasa distinta
- **WHEN** se concilia y se emite la nota de diferencial
- **THEN** el `amount_residual` de la factura SHALL ser 50 USD y su `payment_state` `partial`

#### Scenario: Pago mayor que la factura (nota del lado del pago)

- **GIVEN** una factura de 100 USD y un pago de 150 USD con una tasa distinta
- **WHEN** se concilia y se emite la nota de diferencial
- **THEN** a la línea del pago SHALL sobrarle exactamente 50 USD

#### Scenario: Línea en moneda de compañía

- **WHEN** la línea cerrada está en moneda de la compañía (factura en VEF pagada con USD)
- **THEN** el parcial SHALL conservar su monto sin cambios (cubierto por `test_exchange_difference_settled_paying_ves_invoice_with_usd` en `tests/test_exchange_note_reversal.py`)

#### Scenario: Conciliación anidada sin línea de nota

- **GIVEN** el contexto de cierre de nota (`l10n_ve_exchange_closing_note`) todavía activo
- **WHEN** se concilian dos líneas ninguna de las cuales es de una nota
- **THEN** SHALL NOT dejarse en 0 el monto en divisa del parcial (solo se neutraliza si una de las dos líneas es de nota)

### Requirement: La nota cierra por su monto exacto con un único parcial

La nota SHALL cerrar completa y con un único parcial por su monto en moneda de
la compañía, sea cual sea la tasa contable de la línea que cierra, incluso si
esa tasa es más favorable (más divisa por Bs) que la de la fecha de la nota. La
línea de la nota SHALL NOT ofrecer residual en la divisa de la contraparte
mientras se cierra.

#### Scenario: Tasa contable de la línea más favorable que la de la nota

- **GIVEN** una factura a 30 Bs/USD y una nota de 200 Bs fechada con tasa de 36 Bs/USD
- **WHEN** se cierra la nota contra la línea de la factura
- **THEN** la nota SHALL quedar con residual 0 y UN solo parcial, y el residual en USD de la factura SHALL permanecer en 100 USD

### Requirement: El widget de pagos devuelve la nota como una fila de diferencial

En los datos del widget de pagos de la factura, las ND/NC de diferencial cambiario (y sus
reversiones) SHALL devolverse como filas de diferencial (`is_exchange`), en moneda de la
compañía y por el monto en Bs del parcial.

#### Scenario: Factura con un pago parcial y su nota de diferencial

- **GIVEN** una factura con un pago parcial y su nota de diferencial
- **WHEN** se lee `invoice_payments_widget`
- **THEN** la fila de la nota SHALL llevar `is_exchange`, `currency_id` de la compañía y `amount` igual al monto de la nota
- **AND** la fila del pago SHALL permanecer sin marcar y en la moneda del pago

#### Scenario: Nota que cierra contra la línea del pago

- **GIVEN** un pago con tasa mayor que la de la factura (pago de más valor en Bs), de modo que la ND cierra contra la línea del PAGO y no contra la de la factura
- **WHEN** se lee `invoice_payments_widget`
- **THEN** la nota SHALL aparecer como fila de diferencial (`is_exchange`), en moneda de la compañía y por el monto en Bs de su parcial, igual que el diferencial nativo, sin repetirse
- **AND** al desconciliar el pago la nota SHALL revertirse y su fila SHALL dejar de verse

### Requirement: Una nota por cuota con residual

Como el asiento de diferencial nativo, el flujo SHALL emitir una nota por cada
cuota (línea por cobrar de la factura) con residual, sin importar de qué lado --
factura o pago -- quede el residual: una factura con varias cuotas SHALL recibir
una nota por cuota, cada una cerrada con un único parcial y ligada a su cuota en
`l10n_ve_exchange_line_id`. Al romper un parcial, SHALL revertirse solo la(s)
nota(s) de su cuota (y las notas sin línea, por par factura/pago).

#### Scenario: Factura con dos cuotas, residual del lado de la factura

- **GIVEN** una factura de 100 USD en dos cuotas de 50 y un pago de 100 USD con una tasa que deja residual en cada cuota de la factura
- **WHEN** se concilia
- **THEN** SHALL emitirse dos notas, cada una con residual 0 y un único parcial, y ninguna cuota ni el pago SHALL quedar con residual

#### Scenario: Factura con dos cuotas, residual del lado del pago

- **GIVEN** la misma factura y un pago con una tasa que deja el residual de cada cuota del lado del pago (ambas notas cierran contra la misma línea del pago)
- **WHEN** se concilia
- **THEN** SHALL emitirse igualmente una nota por cuota

#### Scenario: Un parcial deja diferencial en la factura y en el pago

- **GIVEN** una factura en VEF y un pago en USD mayor, cruzado desde el widget con el flujo de ND/NC activo
- **WHEN** el mismo parcial deja diferencial en la línea de la factura y en la del pago
- **THEN** SHALL emitirse una nota por cada línea (la guarda de duplicados solo reconoce la nota cerrada contra la misma línea) y el pago SHALL quedar con el residual de su propia tasa

#### Scenario: Romper el parcial de una cuota

- **WHEN** se rompe el parcial de UNA cuota
- **THEN** SHALL revertirse solo la nota de esa cuota y la otra SHALL seguir vigente

#### Scenario: Romper la conciliación del pago

- **WHEN** se rompe toda la conciliación del pago
- **THEN** SHALL revertirse todas las notas

### Requirement: El cruce desde el widget genera el diferencial como el flujo nativo

Cuando el cruce desde el widget (que aplica el monto mostrado, ver el change
`outstanding-widget-applies-shown-amount` de `l10n_ve_igtf`) deja una diferencia
entre lo aplicado y el balance del pago, esa diferencia SHALL generarse como
cualquier diferencial cambiario nativo, o sea, con el flujo de ND/NC activo,
como una nota que cierra completa y sin descontar divisa.

#### Scenario: Pago en VEF anterior a la factura en USD

- **WHEN** se cruza desde el widget
- **THEN** lo aplicado SHALL igualar lo mostrado y las notas que surjan SHALL cerrar completas con un parcial

#### Scenario: Pago en USD contra factura en VEF

- **GIVEN** una factura de 4.000 Bs y un pago anterior de 80 USD (balance 3.200 Bs; el widget muestra 2.880 Bs)
- **WHEN** se cruza desde el widget
- **THEN** SHALL aplicarse 2.880 Bs y emitirse UNA nota de 320 Bs, cerrada, dejando el pago en cero

#### Scenario: Pago en una tercera moneda

- **WHEN** se cruza un pago en EUR contra una factura en USD
- **THEN** lo aplicado SHALL igualar lo mostrado y el pago y las notas SHALL quedar cerrados

### Requirement: La ND se emite cuando sube la tasa y la NC cuando baja, ligadas a la factura

Si la tasa SUBE al cobrar, el cliente entrega más Bs que los de la factura y la diferencia SHALL
documentarse con una Nota de Débito; si BAJA, con una Nota de Crédito. Cada nota SHALL quedar ligada a
la factura de origen (`debit_origin_id` / `reversed_entry_id`) y el pago SHALL extinguir ambas cuentas por
cobrar (la de la factura y la de la nota). Al desconciliar el pago la nota SHALL revertirse.

#### Scenario: Sube la tasa al cobrar

- **GIVEN** una factura de $100 del 01-01 a 36 Bs/$ (3.600 Bs) y un pago de $100 del 01-08 a 40 Bs/$ (4.000 Bs)
- **WHEN** se cruza el pago
- **THEN** SHALL emitirse una ND de 400 Bs ligada a la factura (`debit_origin_id`)
- **AND** el pago SHALL quedar aplicado: 3.600 Bs contra la factura y 400 Bs contra la ND, con saldo 0
- **AND** al desconciliar el pago la ND SHALL revertirse y el pago SHALL quedar disponible por 4.000 Bs

#### Scenario: Baja la tasa al cobrar

- **GIVEN** una factura de $100 del 01-01 a 40 Bs/$ y un pago parcial de $50 del 01-08 a 36 Bs/$
- **WHEN** se cruza el pago
- **THEN** SHALL emitirse una NC por el diferencial, cerrada contra la línea de la factura, y el residual en divisa de la factura SHALL ser $50

### Requirement: Vínculo de la nota con la factura

La nota SHALL seguir ligada a su factura (`debit_origin_id` para la ND,
`reversed_entry_id` para la NC) y SHALL seguir apareciendo en los libros de
compra y venta. Digitalizar o no una nota de diferencial es una decisión
administrativa y `l10n_ve_invoice_digital` no la restringe.

Las notas de diferencial SHALL llevar el impuesto de venta exento por diseño: el producto de la nota
(`l10n_ve_exchange_note_product_id`) debe tener el impuesto exento por defecto
(`_check_l10n_ve_exchange_note_product_id`).
