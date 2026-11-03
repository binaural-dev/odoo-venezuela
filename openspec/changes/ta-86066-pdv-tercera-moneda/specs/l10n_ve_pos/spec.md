## ADDED Requirements

### Requirement: Método de pago en una tercera moneda de cobro

Un método de pago DEBE (MUST) poder declararse en una tercera moneda de cobro (`tender_currency_id`), distinta de la moneda de la compañía y de la alterna. No DEBE (MUST) combinarse con `is_foreign_currency` ni con un método de crédito, y su diario de cruce DEBE (MUST) estar en esa moneda.

#### Scenario: Moneda de cobro igual a la de la compañía o a la alterna

- **WHEN** se le pone a un método como moneda de cobro la moneda de la compañía o la alterna
- **THEN** se rechaza con un error de validación

#### Scenario: Método en divisa con moneda de cobro

- **WHEN** un método tiene a la vez `is_foreign_currency` y una moneda de cobro
- **THEN** se rechaza con un error de validación

#### Scenario: Diario de cruce en otra moneda

- **WHEN** el diario de cruce de un método con moneda de cobro no está en esa moneda
- **THEN** se rechaza con un error de validación

### Requirement: Conversión con la tasa del día de la moneda de cobro

El motor de conversión (`pos.config._get_pos_conversion_rate` y su espejo `_getPosConversionRate`) DEBE (MUST) convertir entre la moneda de cobro y la caja con las tasas de `tender_currency_rates` (`compute_rate` a la fecha del usuario, moneda → caja la grande y caja → moneda la chica), y entre la moneda de cobro y la alterna pasando por la caja sin redondear la tasa. Los pares sin moneda de cobro NO DEBEN (MUST NOT) cambiar. Sin tasa del día la conversión DEBE (MUST) dar 0.

#### Scenario: Euros a bolívares

- **WHEN** la tasa del día del EUR es 1.003,8765 Bs y se convierten 100 €
- **THEN** el resultado es 100.387,65 Bs

#### Scenario: Euros a dólares

- **WHEN** se convierte de EUR a USD
- **THEN** la tasa es la del EUR → Bs multiplicada por la de Bs → USD, sin redondear

#### Scenario: Sin tasa del día

- **WHEN** el EUR no tiene tasa en la fecha del usuario
- **THEN** la conversión da 0 y el PdV no agrega la línea del método, con un aviso

### Requirement: La moneda de cobro llega al PdV

El PdV DEBE (MUST) cargar las monedas de cobro de sus métodos, y `res.currency` DEBE (MUST) cargarse completo en cada carga, sin el filtro por `write_date`.

#### Scenario: Moneda de cobro agregada después de la última carga

- **WHEN** la caja tiene datos en caché y se agrega un método en EUR
- **THEN** la próxima carga trae el EUR

### Requirement: Cobro tecleado en la moneda de cobro

Al pagar con un método con moneda de cobro, el PdV DEBE (MUST) proponer lo adeudado en esa moneda y tomar lo tecleado en ella. Si lo tecleado cubre lo adeudado (comparado en esa moneda), la línea DEBE (MUST) valer en la caja exactamente el restante más el excedente convertido; si no, la conversión de lo tecleado. El pago DEBE (MUST) guardar lo cobrado en `tender_amount` con la moneda del método, y su `foreign_amount` se deriva del monto en la caja como en cualquier método.

#### Scenario: Pago exacto en euros

- **WHEN** la venta es de 8.500 Bs y el cajero cobra los 8,47 € propuestos
- **THEN** la línea vale 8.500 Bs, no queda restante y se puede validar

#### Scenario: Pago de más en euros

- **WHEN** la venta es de 8.500 Bs y el cajero teclea 10 €
- **THEN** la línea vale 8.500 Bs más 1,53 € convertidos y el vuelto sale en Bs

#### Scenario: Pago parcial en euros

- **WHEN** la venta es de 17.000 Bs y el cajero teclea 5 €
- **THEN** la línea vale la conversión de 5 € y el restante sigue en Bs, en USD y en euros

#### Scenario: Línea y recibo en la moneda de cobro

- **WHEN** se agrega una línea del método en EUR
- **THEN** la línea muestra "€ X / Bs Y" y el recibo muestra los euros junto al nombre del método

### Requirement: Reembolso a la tasa con la que se cobró la moneda de cobro

El reembolso de una orden pagada en una moneda de cobro DEBE (MUST) convertir esa moneda con la tasa con la que se cobraron los pagos originales en ella (`get_refund_tender_rates`), no con la del día.

#### Scenario: Reembolso de un pago en euros

- **WHEN** la venta original se cobró a 1.000 Bs/€ y hoy el € vale 1.003,8765 Bs
- **THEN** reembolsar 8.000 Bs con el método en EUR devuelve 8 €

### Requirement: El cruce de la moneda de cobro lleva lo cobrado en esa moneda

Un método con moneda de cobro y sus dos diarios de cruce DEBE (MUST) cruzar como un método en divisa, y la línea del diario real DEBE (MUST) llevar como `amount_currency` lo cobrado en esa moneda (`tender_amount`), con el debe/haber en la moneda de la compañía y los montos alternos de los pagos.

#### Scenario: Venta en efectivo en euros

- **WHEN** se cierra una sesión con una venta de 116 USD pagada con 100 € en el efectivo en EUR
- **THEN** el cruce lleva 116 en la transitoria del método y en la de la caja en EUR, con `amount_currency` de 100 € en esta última

#### Scenario: Método sin moneda de cobro

- **WHEN** se cruza un método en la alterna
- **THEN** su cruce no cambia y no recibe el argumento nuevo

### Requirement: El efectivo de la caja es el de su moneda

La apertura de una sesión DEBE (MUST) rechazarse si el primer método de efectivo de la caja tiene moneda de cobro: en ese método el core registra el vuelto y el arqueo.

#### Scenario: Efectivo en euros primero en la lista

- **WHEN** el método en EUR es el primer método de efectivo de la caja
- **THEN** no se puede abrir la sesión y el mensaje pide moverlo después del efectivo de la caja
