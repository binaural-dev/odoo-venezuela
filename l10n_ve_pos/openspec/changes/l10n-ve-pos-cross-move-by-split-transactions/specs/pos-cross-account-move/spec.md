# Spec delta: pos-cross-account-move

## ADDED Requirements

### Requirement: Trazabilidad del asiento de cruce

El sistema SHALL construir el `ref` del asiento de cruce de forma que
identifique unívocamente qué está cruzando, porque `name` no puede llevar ese
texto (es el número de secuencia, asignado por el diario al postear) y es el
único campo que distingue un borrador de otro en la lista de asientos.

- Con granularidad split, el `ref` SHALL bajar hasta el `pos.payment`
  individual, no quedarse en la orden: una orden puede tener varios pagos del
  mismo método, y el nombre de la orden solo volvería a repetirse. Se usa
  `pos.payment.name` cuando existe (solo lo llenan los terminales de pago) y
  el id del registro como discriminador de último recurso.
- Con granularidad combine, el `ref` SHALL nombrar la sesión, que es la
  granularidad que cubre ese asiento.

El sistema SHALL además fijar `partner_id` en la cabecera del asiento bajo
granularidad split, para que la columna "Socio" de la lista de asientos no
salga vacía. Bajo granularidad combine SHALL dejarse vacío, porque un mismo
asiento agrupa pagos de varios clientes.

#### Scenario: Dos pagos del mismo método en la misma orden

- **GIVEN** una orden con dos pagos del mismo método elegible con
  `split_transactions=True`, ambos por el mismo importe
- **WHEN** se cierra la sesión
- **THEN** se crean dos asientos con `ref` distintos, ambos nombrando la orden,
  distinguidos por el pago concreto

#### Scenario: Asiento split en la lista de asientos

- **GIVEN** un pago split de un cliente cuya compañía es compatible con la de
  la sesión
- **WHEN** se crea el asiento de cruce
- **THEN** la cabecera del asiento lleva ese `partner_id`

#### Scenario: Asiento combinado

- **GIVEN** un método elegible con `split_transactions=False` y pagos de varios
  clientes en la sesión
- **WHEN** se cierra la sesión
- **THEN** el `ref` del único asiento nombra la sesión y la cabecera queda sin
  `partner_id`

### Requirement: Un cliente de otra compañía no bloquea el cierre

El sistema SHALL omitir el `partner_id` de la cabecera del asiento de cruce
cuando el cliente pertenece a una compañía distinta de la de la sesión.

`account.move.partner_id` es `check_company=True` mientras que
`account.move.line.partner_id` no lo es, y `pos.order.partner_id` no tiene
chequeo de compañía alguno — Odoo acepta una orden cuyo cliente sea de otra
compañía. Propagar ese cliente a la cabecera lanzaría `UserError` y
bloquearía el cierre completo de la sesión, a cambio de una mejora de
legibilidad.

#### Scenario: Orden con cliente de otra compañía

- **GIVEN** una orden cuyo cliente pertenece a una compañía distinta de la de
  la sesión, con un método de pago elegible y `split_transactions=True`
- **WHEN** se cierra la sesión
- **THEN** el asiento de cruce se crea igual, con la cabecera sin `partner_id`
  y las líneas conservando el cliente, sin lanzar ninguna excepción

## MODIFIED Requirements

### Requirement: Elegibilidad del cruce por `is_foreign_currency`

El sistema SHALL disparar el cruce automático para todo `pos.payment.method`
con `is_foreign_currency=True`, `type != 'pay_later'`, ambos diarios de cruce
(`cross_account_journal` y `cross_journal`) configurados y una cuenta
transitoria resoluble. El sistema SHALL NOT requerir ningún interruptor
adicional: el campo `apply_one_cross_move` queda eliminado del modelo, de la
vista y de `_load_pos_data_fields`.

Un método que no cumpla alguna de esas condiciones SHALL omitirse en silencio,
sin lanzar excepción.

#### Scenario: Método en divisa con ambos diarios configurados

- **GIVEN** un método de pago con `is_foreign_currency=True` y
  `cross_account_journal` + `cross_journal` configurados
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** se crean los asientos de cruce correspondientes, sin depender de
  ningún otro flag

#### Scenario: Método que no es en divisa

- **GIVEN** un método de pago con `is_foreign_currency=False` y ambos diarios
  de cruce configurados
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** no se crea ningún asiento de cruce

#### Scenario: Falta un diario de cruce

- **GIVEN** un método con `is_foreign_currency=True` pero solo uno de
  `cross_account_journal`/`cross_journal` configurado
- **WHEN** se cierra la sesión
- **THEN** no se crea ningún asiento de cruce y no se lanza ninguna excepción

#### Scenario: Método de tipo `pay_later`

- **GIVEN** un método `pay_later` con `is_foreign_currency=True` y ambos
  diarios de cruce configurados
- **WHEN** se evalúa su elegibilidad
- **THEN** el método queda excluido por su tipo, aunque el fallback de cuenta
  transitoria sí resolvería una cuenta

### Requirement: Granularidad del cruce según `split_transactions`

El sistema SHALL determinar cuántos asientos de cruce crea a partir del campo
nativo `split_transactions` del método de pago, replicando la clave de
agrupación que usa `_accumulate_amounts` en el pipeline nativo:

- Con `split_transactions=True`, SHALL crear un `account.move` por cada
  `pos.payment` de la sesión de ese método.
- Con `split_transactions=False`, SHALL crear un único `account.move` por
  método y sesión, con el importe neto de todos los pagos de ese método.

El sistema SHALL usar `_validate_cross_move()` como único punto de entrada
para ambas granularidades, enganchado en `action_pos_session_close` tras
`super()`. El sistema SHALL NOT disparar el cruce desde
`_create_combine_account_payment`.

#### Scenario: Método combinado con varios pagos en la sesión

- **GIVEN** un método elegible con `split_transactions=False` y tres pagos en
  la sesión
- **WHEN** se cierra la sesión
- **THEN** se crea exactamente **un** `account.move` de cruce, cuyo importe es
  la suma de los tres pagos

#### Scenario: Método con "Identificar cliente" activo

- **GIVEN** un método elegible con `split_transactions=True` y tres pagos en
  la sesión
- **WHEN** se cierra la sesión
- **THEN** se crean **tres** `account.move` de cruce, uno por pago, cada uno
  por el importe de su propio pago

#### Scenario: Métodos con distinta granularidad en la misma sesión

- **GIVEN** una sesión con un método combinado (2 pagos) y otro split (2 pagos),
  ambos elegibles
- **WHEN** se cierra la sesión
- **THEN** se crean 3 asientos: 1 del método combinado y 2 del método split

#### Scenario: Neto cero en un método combinado

- **GIVEN** un método elegible con `split_transactions=False` cuyos pagos de la
  sesión suman cero (una venta y su devolución por el mismo importe)
- **WHEN** se cierra la sesión
- **THEN** no se crea ningún asiento de cruce

#### Scenario: Neto negativo en un método combinado

- **GIVEN** un método elegible con `split_transactions=False` cuyos pagos suman
  un importe negativo
- **WHEN** se cierra la sesión
- **THEN** se crea un único asiento por la rama saliente, con el valor absoluto
  del neto: debita la cuenta transitoria y acredita la cuenta de pago saliente
  del `cross_journal`

### Requirement: Cuenta transitoria según el tipo de método de pago

El sistema SHALL resolver la pata transitoria del cruce según el tipo del
método de pago, apuntando a la cuenta donde el pipeline nativo dejó
efectivamente el saldo al cerrar la sesión:

- Método `cash`: `payment_method.journal_id.default_account_id`.
- Método `bank`: `payment_method.outstanding_account_id`, o
  `payment_method.journal_id.default_account_id` si el primero está vacío.

En ambos casos, si no se resuelve ninguna cuenta, el sistema SHALL usar
`company.account_default_pos_receivable_account_id` como último recurso, de
modo que una configuración incompleta degrade en un cruce omitido y no en un
error de base de datos por `account_id` nulo.

#### Scenario: Método de pago en efectivo

- **GIVEN** un método `cash` elegible (su `outstanding_account_id` está vacío,
  como en todo método cash — ese campo es `invisible="type != 'bank'"` en la
  vista nativa)
- **WHEN** se cierra la sesión con un pago de ese método
- **THEN** la pata transitoria del asiento cae sobre
  `journal_id.default_account_id`, y **no** sobre
  `company.account_default_pos_receivable_account_id`, que el statement line
  nativo ya dejó saldada en cero

#### Scenario: Método de pago bancario

- **GIVEN** un método `bank` elegible con `outstanding_account_id` configurado
- **WHEN** se cierra la sesión con un pago de ese método
- **THEN** la pata transitoria del asiento cae sobre `outstanding_account_id`

## REMOVED Requirements

### Requirement: Cruce automático combine entrante

**Razón**: el cruce de la ruta combine ya no se dispara desde
`_create_combine_account_payment` ni depende de `account.payment.origin_payment_id`.
Queda absorbido por "Granularidad del cruce según `split_transactions`", que
cubre ambas granularidades desde `_validate_cross_move` leyendo `pos.payment`
directamente — lo que además hace que los métodos `cash` combinados, que nunca
pasan por `_create_combine_account_payment`, queden cubiertos.

**Migración**: los métodos `_create_cross_move_payment` y
`_line_vals_move_cross_payment_incoming` se eliminan de `pos_session.py`.

### Requirement: Cuenta transitoria con fallback para métodos sin `outstanding_account_id`

**Razón**: superado por "Cuenta transitoria según el tipo de método de pago".
El fallback plano a `account_default_pos_receivable_account_id` evitaba el
error de base de datos pero apuntaba a la cuenta contable equivocada en
métodos `cash`: el statement line nativo deja la POS receivable saldada en
cero y el dinero en `journal_id.default_account_id`.

**Migración**: los asientos de cruce ya generados sobre métodos `cash` cruzaron
contra la POS receivable. Revisar con contabilidad si hay que corregirlos.

### Requirement: Sin cruce cuando no aplica

**Razón**: superado por "Elegibilidad del cruce por `is_foreign_currency`",
que redefine las condiciones de omisión. El campo `apply_one_cross_move` que
este requisito nombraba ya no existe.
