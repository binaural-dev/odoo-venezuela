## MODIFIED Requirements

### Requirement: Método de pago en una tercera moneda de cobro

Un método de pago DEBE (MUST) poder declararse en una tercera moneda de cobro (`tender_currency_id`), distinta de la moneda de la compañía. No DEBE (MUST) combinarse con `is_foreign_currency` ni con un método de crédito y DEBE (MUST) tener sus dos diarios de cruce, el real en esa moneda. Lo que depende de la caja lo DEBE (MUST) validar cada caja del método (`pos.config._get_tender_currency_error`): aquí, solo una caja en la moneda de la compañía y sin la alterna.

#### Scenario: Moneda de cobro igual a la de la compañía o a la alterna

- **WHEN** se le pone a un método como moneda de cobro la moneda de la compañía, o se agrega a una caja en la moneda de la compañía un método con la alterna como moneda de cobro
- **THEN** se rechaza con un error de validación: en esa caja la alterna se cobra con `is_foreign_currency`

#### Scenario: Método sin caja con la alterna

- **WHEN** se crea un método con la alterna como moneda de cobro que todavía no está en ninguna caja
- **THEN** se acepta, y lo valida cada caja a la que se agregue

#### Scenario: Método en divisa con moneda de cobro

- **WHEN** un método tiene a la vez `is_foreign_currency` y una moneda de cobro
- **THEN** se rechaza con un error de validación

#### Scenario: Diario de cruce en otra moneda

- **WHEN** el diario de cruce de un método con moneda de cobro no está en esa moneda
- **THEN** se rechaza con un error de validación

#### Scenario: Método sin diarios de cruce

- **WHEN** a un método con moneda de cobro le falta el diario de cruce o el diario de la cuenta de cruce
- **THEN** se rechaza con un error de validación: sin ellos el cruce se omitiría y los euros no llegarían a la caja real

#### Scenario: Caja en otra moneda

- **WHEN** se agrega un método con moneda de cobro a una caja cuya moneda no es la de la compañía, o se le pone la moneda de cobro a un método de esa caja, y ningún módulo extiende el gancho
- **THEN** se rechaza con un error de validación

### Requirement: El cruce de la moneda de cobro lleva lo cobrado en esa moneda

Un método con moneda de cobro y sus dos diarios de cruce DEBE (MUST) cruzar como un método en divisa, y la línea del diario real DEBE (MUST) llevar como `amount_currency` lo cobrado en esa moneda (`tender_amount`), con el debe/haber en la moneda de la compañía y los montos alternos de los pagos. Sin `currency_amount`, DEBE (MUST) convertir el debe/haber, que está en la moneda de la compañía, a la tasa del día de la caja.

#### Scenario: Venta en efectivo en euros

- **WHEN** se cierra una sesión con una venta de 116 USD pagada con 100 € en el efectivo en EUR
- **THEN** el cruce lleva 116 en la transitoria del método y en la de la caja en EUR, con `amount_currency` de 100 € en esta última

#### Scenario: Método sin moneda de cobro

- **WHEN** se cruza un método en la alterna
- **THEN** su cruce no cambia y no recibe el argumento nuevo

#### Scenario: Llamador sin el monto en la moneda de cobro

- **WHEN** un módulo crea el cruce de un método con moneda de cobro sin pasar `currency_amount`
- **THEN** la línea del diario real lleva la conversión del debe/haber desde la moneda de la compañía a la tasa del día de la caja, no el debe/haber como si fuera esa moneda

## ADDED Requirements

### Requirement: La línea transitoria del cruce en la moneda del diario del método

Si el llamador pasa `transitory_amount_currency` y el diario del método tiene moneda, la línea transitoria del cruce DEBE (MUST) ir en esa moneda y con ese monto, con el signo de su debe/haber, para que la transitoria quede en cero también en ella. Sin él, la línea DEBE (MUST) seguir en la moneda de la compañía. En el cruce combinado, cada pata DEBE (MUST) llevar el suyo y el neto en esa moneda cuenta para no crear el asiento.

#### Scenario: Diario transitorio en la alterna

- **WHEN** se cruzan 100 € (116 de la caja) de un método cuyo diario está en la alterna, pasando `transitory_amount_currency` = 116
- **THEN** la línea transitoria va en la alterna con `amount_currency` 116 y la del diario real con 100 €, las dos con el mismo debe/haber en la moneda de la compañía

#### Scenario: Sin el monto en la moneda del diario

- **WHEN** se cruza el mismo método sin `transitory_amount_currency`
- **THEN** la línea transitoria va en la moneda de la compañía, como siempre

#### Scenario: Cruce combinado con venta y reembolso

- **WHEN** el cruce combinado de ese método tiene una venta (116) y un reembolso (−58) en la moneda del diario
- **THEN** cada pata lleva su línea transitoria en esa moneda con su monto
