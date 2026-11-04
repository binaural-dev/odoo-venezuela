## ADDED Requirements

### Requirement: Método de pago en una tercera moneda de cobro

Un método de pago DEBE (MUST) poder declararse en una tercera moneda de cobro (`tender_currency_id`), distinta de la moneda de la compañía y de la alterna. No DEBE (MUST) combinarse con `is_foreign_currency` ni con un método de crédito, DEBE (MUST) tener sus dos diarios de cruce, el real en esa moneda, y solo DEBE (MUST) usarse en cajas en la moneda de la compañía, porque sus tasas son contra esa moneda.

#### Scenario: Moneda de cobro igual a la de la compañía o a la alterna

- **WHEN** se le pone a un método como moneda de cobro la moneda de la compañía o la alterna
- **THEN** se rechaza con un error de validación

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

- **WHEN** se agrega un método con moneda de cobro a una caja cuya moneda no es la de la compañía, o se le pone la moneda de cobro a un método de esa caja
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

#### Scenario: Recibo de un pago anterior a un cambio del método

- **WHEN** después de cobrar en EUR se cambia o se quita la moneda de cobro del método y se reimprime el recibo
- **THEN** el recibo muestra la moneda y el monto con que se cobró, guardados en el pago

### Requirement: Cobro desde el backend en la moneda de cobro

Un pago con un método con moneda de cobro registrado desde el backend (`pos.make.payment`) DEBE (MUST) quedar con la moneda del método y su monto en esa moneda, igual que uno sincronizado desde el PdV: a la tasa del día de la caja, o en un reembolso a la de los cobros originales. Sin tasa del día de esa moneda, el cobro desde el backend DEBE (MUST) rechazarse con el aviso del PdV.

#### Scenario: Cobro de una orden desde el backend

- **WHEN** se cobra desde el backend una orden de 100.387,65 Bs con el método en EUR, a 1.003,8765 Bs/€
- **THEN** el pago queda con moneda EUR y 100 €, y su cajón y su cruce los cuentan

#### Scenario: Reembolso desde el backend

- **WHEN** la venta se cobró con 80 € y se reembolsa entera desde el backend con el método en EUR
- **THEN** el pago del reembolso queda en −80 €, aunque la tasa del día sea otra

#### Scenario: Cobro desde el backend sin tasa del día

- **WHEN** el EUR no tiene tasa del día y se cobra desde el backend una orden con el método en EUR
- **THEN** se rechaza con el mismo aviso del PdV y la orden sigue sin pagos; los demás métodos se cobran igual

#### Scenario: Orden sincronizada sin tasa del día

- **WHEN** llega al servidor una orden de un PdV con un bundle anterior, pagada en EUR sin `tender_amount` y sin tasa del día del EUR
- **THEN** se sincroniza igual, con 0 € en el pago y un aviso en el log del servidor

### Requirement: Reembolso a la tasa con la que se cobró la moneda de cobro

El reembolso de una orden pagada en una moneda de cobro DEBE (MUST) convertir esa moneda con la tasa con la que se cobraron en ella los pagos de las órdenes originales de todas sus líneas (`get_refund_tender_rates`), no con la del día, en el PdV y en el backend.

#### Scenario: Reembolso desde el backend de una venta de otro día

- **WHEN** una venta se cobró con 24,29 € a 1.399,75 Bs/€ y hoy el € vale 1.003,8765 Bs, y su reembolso se paga desde el backend con el método en EUR
- **THEN** el pago del reembolso queda en −24,29 € y no en −33,87 €

#### Scenario: Reembolso de un pago en euros

- **WHEN** la venta original se cobró a 1.000 Bs/€ y hoy el € vale 1.003,8765 Bs
- **THEN** reembolsar 8.000 Bs con el método en EUR devuelve 8 €

#### Scenario: Reembolso con líneas de dos ventas

- **WHEN** un reembolso armado fuera del PdV (`sync_from_ui` del core rechaza uno de varias órdenes) tiene líneas de dos ventas cobradas con 80 € y con 50 € a tasas distintas, y se paga entero desde el backend con el método en EUR
- **THEN** devuelve 130 €, a la tasa de las dos ventas, y no 120 € a la de la primera

### Requirement: El cruce de la moneda de cobro lleva lo cobrado en esa moneda

Un método con moneda de cobro y sus dos diarios de cruce DEBE (MUST) cruzar como un método en divisa, y la línea del diario real DEBE (MUST) llevar como `amount_currency` lo cobrado en esa moneda (`tender_amount`), con el debe/haber en la moneda de la compañía y los montos alternos de los pagos.

#### Scenario: Venta en efectivo en euros

- **WHEN** se cierra una sesión con una venta de 116 USD pagada con 100 € en el efectivo en EUR
- **THEN** el cruce lleva 116 en la transitoria del método y en la de la caja en EUR, con `amount_currency` de 100 € en esta última

#### Scenario: Método sin moneda de cobro

- **WHEN** se cruza un método en la alterna
- **THEN** su cruce no cambia y no recibe el argumento nuevo

#### Scenario: Llamador sin el monto en la moneda de cobro

- **WHEN** un módulo crea el cruce de un método con moneda de cobro sin pasar `currency_amount`
- **THEN** la línea del diario real lleva la conversión del monto a la tasa del día de la caja, no el monto en la moneda de la caja

### Requirement: El efectivo de la caja es el de su moneda

La apertura de una sesión DEBE (MUST) rechazarse si el primer método de efectivo de la caja tiene moneda de cobro: en ese método el core registra el vuelto y el arqueo.

#### Scenario: Efectivo en euros primero en la lista

- **WHEN** el método en EUR es el primer método de efectivo de la caja
- **THEN** no se puede abrir la sesión y el mensaje pide moverlo después del efectivo de la caja

## MODIFIED Requirements

### Requirement: Granularidad del cross move según split_transactions

La granularidad de los cross moves DEBE (MUST) seguir el flag nativo `split_transactions` del método: verdadero, un asiento por cada `pos.payment` (con su orden y pago en la referencia); falso, un único asiento por método y sesión con una pata de entradas y otra de salidas, cada una con el neto de sus pagos, y ninguno si los netos en la caja, la alterna y la moneda de cobro son todos cero. Si el partner de un pago es de otra compañía, se omite del encabezado.

#### Scenario: Método identificando cliente

- **WHEN** el método tiene `split_transactions` activo y la sesión registró tres pagos con él
- **THEN** se crean tres asientos borrador, cada uno con la referencia de su pago

#### Scenario: Neto cero combinado

- **WHEN** el método no divide transacciones y las ventas y devoluciones del método se anulan entre sí en la caja, en la alterna y en la moneda de cobro
- **THEN** no se crea ningún asiento para ese método

#### Scenario: Venta y devolución en divisa a tasas distintas

- **WHEN** el método no divide transacciones y la sesión tiene una venta de 40 a 50 por unidad y una devolución de 60 a 10 (neto −20 en la caja y +1.400 en la alterna)
- **THEN** se crea un asiento con dos pares de líneas, la venta y la devolución, cada línea con saldo y `amount_currency` del mismo signo, y el diario real recibe −20 y +1.400

#### Scenario: Venta y reembolso en euros a tasas distintas

- **WHEN** el método en EUR no divide transacciones y la sesión tiene una venta de 20 € por 1.000 Bs y un reembolso de 25 € por 750 Bs
- **THEN** se crea un asiento con dos pares de líneas y la caja real en EUR recibe −250 Bs con +5 € en `amount_currency`, sin que el cierre choque con `account_move_line_check_amount_currency_balance_sign`

#### Scenario: Neto cero en la caja con divisas de diferencia

- **WHEN** las ventas y reembolsos del método suman cero en la caja pero no en la alterna o en euros
- **THEN** se crea el asiento y la diferencia en esa moneda pasa al diario real

#### Scenario: Tasa de cada pata

- **WHEN** el reembolso de la sesión se valoró a la tasa de su venta original y la venta a la del día
- **THEN** las líneas de cada pata se arman con la tasa de sus pagos; es informativa, porque la línea guardada toma la del asiento y sus montos alternos son los de sus pagos

### Requirement: Conversión centralizada con tasa completa y redondeo solo del resultado

La conversión del PdV DEBE (MUST) multiplicar el monto por la tasa cruda sin redondear y redondear solo el resultado con `to_currency.round()`: principal → alterna con `foreign_inverse_rate`, alterna → principal con `foreign_rate` y, con una moneda de cobro, las tasas de `tender_currency_rates`. Misma moneda devuelve el monto; sin tasa, `0.0`. El contrato está en espejo en `pos.config._convert` y en `PosOrder._convert` del frontend.

#### Scenario: Conversión de bolívares a divisa

- **WHEN** se convierte un monto en moneda principal hacia la moneda alterna
- **THEN** el resultado es `monto * foreign_inverse_rate` redondeado con el redondeo de la moneda alterna

#### Scenario: Sin tasa configurada

- **WHEN** ninguna de las dos monedas involucradas es la alterna ni una moneda de cobro de la caja, o la tasa operativa es cero
- **THEN** la conversión devuelve `0.0` (y el frontend registra una advertencia en consola una sola vez)

#### Scenario: Caja sin tasa del día

- **WHEN** `pos.config._compute_rate` se calcula un día sin tasa cargada para la moneda alterna
- **THEN** llama a `compute_rate` con `raise_if_not_found=False` y no lanza error (la configuración de la caja sigue accesible, aunque `l10n_ve_rate.compute_rate` lance `UserError` por defecto)

#### Scenario: Bolívares y una moneda de cobro

- **WHEN** se convierte entre la moneda principal y una moneda de cobro de los métodos de la caja con tasa del día
- **THEN** la conversión no da `0.0`: usa la tasa de esa moneda en `tender_currency_rates`

### Requirement: Cross moves de compensación para métodos en divisa

Al cerrar la sesión (`_validate_cross_move`), por cada método que pase `_is_cross_move_eligible` (`is_foreign_currency` o una moneda de cobro, tipo distinto de `pay_later`, sus dos diarios de cruce y una transitoria resoluble), el sistema DEBE (MUST) crear en `cross_account_journal` asientos en borrador que pasan el saldo de la transitoria del método a la cuenta real del `cross_journal`, con `foreign_debit`/`foreign_credit`, `not_foreign_recalculate` y una `ref` de sesión, orden o pago.

#### Scenario: Método en divisa completo

- **WHEN** se cierra una sesión con pagos de un método `is_foreign_currency` con ambos diarios configurados
- **THEN** se crean asientos borrador en `cross_account_journal` que acreditan la cuenta transitoria y debitan la cuenta real del `cross_journal` (o a la inversa para montos negativos), sin `name`: lo asigna el diario al contabilizar

#### Scenario: Configuración incompleta

- **WHEN** al método le falta `cross_account_journal` o `cross_journal`
- **THEN** no se crea ningún cross move para ese método y el cierre no falla (un método con moneda de cobro no se puede guardar así)

#### Scenario: Cuentas del cruce

- **WHEN** se arma el cruce de un método
- **THEN** la transitoria es la que resuelve `_get_cross_transitory_account` (efectivo: `journal_id.default_account_id`; el resto: `outstanding_account_id` o la del diario; en ambos, como último recurso, la cuenta por cobrar del PdV de la compañía) y la real la `payment_account_id` de las líneas de pago entrantes o salientes del `cross_journal`, según el signo; con `use_suspense=True` el asiento va entre las cuentas transitorias de los dos diarios, con el sentido invertido

#### Scenario: Método con moneda de cobro

- **WHEN** se cierra una sesión con pagos de un método con moneda de cobro y sus dos diarios
- **THEN** su cruce se crea como el de un método en divisa y la línea del diario real lleva como `amount_currency` lo cobrado en esa moneda

### Requirement: Monedas cargadas al PdV restringidas y ordenadas

El loader de `res.currency` DEBE (MUST) restringir las monedas enviadas al PdV a la moneda de la compañía, la de la caja, la alterna y las monedas de cobro de sus métodos (`_load_pos_data_domain`), exponer `inverse_rate` entre los campos y devolver la lista con la moneda de la compañía en primera posición (`_load_pos_data_read`).

#### Scenario: Compañía con moneda alterna

- **WHEN** se abre una caja de una compañía con moneda alterna configurada
- **THEN** al frontend llegan únicamente esas monedas, con la de la compañía primero

#### Scenario: Caja con un método en una moneda de cobro

- **WHEN** la caja tiene un método con moneda de cobro EUR
- **THEN** el EUR también llega al frontend, después de la moneda de la compañía
