## MODIFIED Requirements

### Requirement: Cross moves de compensación para métodos en divisa

Al cerrar la sesión (`_validate_cross_move`), por cada método que pase `_is_cross_move_eligible` (`is_foreign_currency` o una moneda de cobro, tipo distinto de `pay_later`, sus dos diarios de cruce y una transitoria resoluble), el sistema DEBE (MUST) crear en `cross_account_journal` asientos publicados que pasan el saldo de la transitoria del método a la cuenta real del `cross_journal`, con `foreign_debit`/`foreign_credit`, `not_foreign_recalculate` y una `ref` que empieza con la sesión y nombra el método (combinado) o la orden y el pago (split), que es también la etiqueta de sus líneas.

#### Scenario: Método en divisa completo

- **WHEN** se cierra una sesión con pagos de un método `is_foreign_currency` con ambos diarios configurados
- **THEN** se crean asientos publicados en `cross_account_journal` que acreditan la cuenta transitoria y debitan la cuenta real del `cross_journal` (o a la inversa para montos negativos), con la tasa del pago y `foreign_currency_id` también en el encabezado, sin `name` al crearlos: lo asigna el diario al publicarlos

#### Scenario: Configuración incompleta

- **WHEN** al método le falta `cross_account_journal` o `cross_journal`
- **THEN** no se crea ningún cross move para ese método y el cierre no falla (un método con moneda de cobro no se puede guardar así)

#### Scenario: Cuentas faltantes

- **WHEN** a un método con sus dos diarios le falta alguna cuenta que usa su cruce
- **THEN** la sesión no abre (change `l10n-ve-pos-cross-move-accounts-check`); en una sesión abierta antes, al cerrar, una transitoria que falte omite el cruce con un aviso en el log y una cuenta de las líneas de pago que falte da un error legible

#### Scenario: Cuentas del cruce

- **WHEN** se arma el cruce de un método
- **THEN** la transitoria es la que resuelve `_get_cross_transitory_account` (efectivo: `journal_id.default_account_id`; el resto: `outstanding_account_id` o la del diario; en ambos, como último recurso, la cuenta por cobrar del PdV de la compañía) y la real la `payment_account_id` de las líneas de pago entrantes o salientes del `cross_journal`, según el signo; con `use_suspense=True` el asiento va entre las cuentas transitorias de los dos diarios: una entrada/salida con el sentido invertido y una venta en efectivo como la salida que la lleva al diario real

#### Scenario: Método con moneda de cobro

- **WHEN** se cierra una sesión con pagos de un método con moneda de cobro y sus dos diarios
- **THEN** su cruce se crea como el de un método en divisa y la línea del diario real lleva como `amount_currency` lo cobrado en esa moneda

#### Scenario: Venta en efectivo en el diario de caja de la sesión

- **WHEN** se cierra una sesión con ventas en efectivo de un método en divisa cuyo diario es el de caja de la sesión (`cash_journal_id`, el que recibe las salidas de efectivo del core)
- **THEN** el cruce acredita la transitoria de ese diario (donde la salida de efectivo dejó el dinero en el debe) y debita la del `cross_journal`, y su línea de extracto entra al diario real

#### Scenario: Venta en efectivo en un diario al que no llegan salidas

- **WHEN** se cierra una sesión con ventas en efectivo de un método en divisa en otro diario (un segundo efectivo, o sin `binaural_pos_close`)
- **THEN** el cruce acredita la cuenta de ese diario, donde quedó la venta, y debita la transitoria del `cross_journal`; la cuenta del diario y su transitoria quedan en cero y la venta entra al diario real con su línea de extracto

#### Scenario: Cajero sin permisos contables

- **WHEN** el cruce lo dispara un usuario del PdV sin permisos contables
- **THEN** el asiento y su línea de extracto se crean y publican igual

#### Scenario: Etiqueta con la sesión

- **WHEN** se cierra la sesión `Caja 1/00050` con ventas combinadas de un método en divisa
- **THEN** la `ref` del cruce y la etiqueta de sus líneas son `Caja 1/00050 · Ventas · <método>`

### Requirement: Granularidad del cross move según split_transactions

La granularidad de los cross moves DEBE (MUST) seguir el flag nativo `split_transactions` del método: verdadero, un asiento por cada `pos.payment` (con su orden y pago en la referencia); falso, un único asiento por método y sesión con una pata de entradas y otra de salidas, cada una con el neto de sus pagos, y ninguno si los netos en la caja, la alterna y la moneda de cobro son todos cero. Si el partner de un pago es de otra compañía, se omite del encabezado.

#### Scenario: Método identificando cliente

- **WHEN** el método tiene `split_transactions` activo y la sesión registró tres pagos con él
- **THEN** se crean tres asientos publicados, cada uno con la referencia de su pago

#### Scenario: Neto cero combinado

- **WHEN** el método no divide transacciones y las ventas y devoluciones del método se anulan entre sí en la caja, en la alterna y en la moneda de cobro
- **THEN** no se crea ningún asiento para ese método

#### Scenario: Venta y devolución en divisa a tasas distintas

- **WHEN** el método no divide transacciones y la sesión tiene una venta de 40 a 50 por unidad y una devolución de 60 a 10 (neto −20 en la caja y +1.400 en la alterna)
- **THEN** se crea un asiento con dos pares de líneas, la venta y la devolución, cada línea con saldo y `amount_currency` del mismo signo, y el diario real recibe −20 y +1.400

#### Scenario: Venta y reembolso en euros a tasas distintas

- **WHEN** el método en EUR no divide transacciones y la sesión tiene una venta de 20 € por 1.000 Bs y un reembolso de 25 € por 750 Bs
- **THEN** se crea un asiento con dos pares de líneas y la caja real en EUR lleva +250 Bs con −5 € en `amount_currency` (salió más de lo que entró), sin que el cierre choque con `account_move_line_check_amount_currency_balance_sign`

#### Scenario: Neto cero en la caja con divisas de diferencia

- **WHEN** las ventas y reembolsos del método suman cero en la caja pero no en la alterna o en euros
- **THEN** se crea el asiento y la diferencia en esa moneda pasa al diario real

#### Scenario: Tasa de cada pata

- **WHEN** el reembolso de la sesión se valoró a la tasa de su venta original y la venta a la del día
- **THEN** las líneas de cada pata se arman con la tasa de sus pagos; es informativa, porque la línea guardada toma la del asiento y sus montos alternos son los de sus pagos

## ADDED Requirements

### Requirement: Línea de extracto del cruce en el diario real

Por cada línea de un cruce sobre la Cuenta transitoria del `cross_journal` el sistema DEBE (MUST) crear en ese diario una línea de extracto sin conciliar con el mismo monto en la moneda del diario, la misma alterna, el mismo socio, la fecha del cruce y su `ref` como etiqueta, para conciliarla uno a uno contra su cruce desde el tablero. NO DEBE (MUST NOT) crearla si esa transitoria es también la del diario del método.

#### Scenario: Salida de efectivo cruzada

- **WHEN** se cruza una salida de 70 $ del cajón a un `cross_journal` en USD con su propia Cuenta transitoria
- **THEN** el `cross_journal` tiene una línea de extracto de +70 $ con la etiqueta del cruce, sin conciliar
- **AND** su contrapartida en la Cuenta transitoria se concilia completa contra la línea del cruce

#### Scenario: Entrada y salida en la misma sesión

- **WHEN** se cruzan una entrada de 50 $ y una salida de 70 $
- **THEN** el `cross_journal` tiene dos líneas de extracto, −50 $ y +70 $, una por cruce

#### Scenario: Transitorias compartidas

- **WHEN** el diario del método y el `cross_journal` tienen la misma Cuenta transitoria
- **THEN** el cruce se crea y no se crea ninguna línea de extracto

### Requirement: Métodos que no cruzan sus ventas

`_validate_cross_move` DEBE (MUST) cruzar las ventas solo de los métodos para los que `_crosses_sales(payment_method)` es verdadero (siempre en este módulo). Un módulo que cruza cada entrada/salida de un cajón (`binaural_pos_close`) lo responde falso para el método de ese cajón: la salida que lo vacía ya lleva al diario real el dinero de las ventas.

#### Scenario: Método que no cruza sus ventas

- **WHEN** `_crosses_sales` es falso para el método de las ventas de la sesión
- **THEN** al cerrar no se crea su cruce de ventas ni su línea de extracto
