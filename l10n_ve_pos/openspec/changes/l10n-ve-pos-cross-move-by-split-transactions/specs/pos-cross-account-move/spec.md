# Spec delta: pos-cross-account-move

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
