# El cruce automático se rige por `split_transactions` y aplica a todo método `is_foreign_currency`

## Why

El cruce automático (change `l10n-ve-pos-cross-account-move`) quedó operativo
pero con tres problemas de fondo que el usuario detectó probando en producción:

1. **El interruptor equivocado.** El flujo solo se dispara con
   `apply_one_cross_move=True`, un flag propio que se añade encima de
   `is_foreign_currency`. Pero el cruce *es* la contrapartida contable de un
   método en divisa: todo método con `is_foreign_currency=True` (y sus dos
   diarios de cruce configurados) debería cruzar, sin un segundo opt-in que
   solo sirve para dejar el flujo silenciosamente apagado.

2. **`split_transactions` no tenía ningún efecto.** El usuario probó activar y
   desactivar "Identificar cliente" y en ambos casos obtuvo un asiento por
   cada pago. La causa es que el flujo tenía **dos disparadores
   independientes**:

   - `_validate_cross_move()`, enganchado en `action_pos_session_close`,
     iteraba `session.order_ids.payment_ids` **sin mirar
     `split_transactions`** — un asiento por pago, siempre.
   - `_create_cross_move_payment()`, disparado desde dentro de
     `_create_combine_account_payment` — un asiento agregado por método.

   Para un método **bank combinado** ambos disparaban: `N + 1` asientos. Para
   un método **cash combinado** solo disparaba el primero (el efectivo nunca
   pasa por `_create_combine_account_payment`; `_create_bank_payment_moves`
   solo recorre métodos bank, `point_of_sale/models/pos_session.py:1057`), así
   que quedaban `N` asientos. En los dos casos el flag "Identificar cliente"
   era invisible.

3. **La cuenta transitoria de los métodos `cash` apuntaba a la cuenta
   equivocada.** `_get_cross_transitory_account` devolvía
   `outstanding_account_id or account_default_pos_receivable_account_id`. Para
   `bank` es correcto (el `account.payment` nativo deja el saldo en la
   outstanding, `pos_session.py:1104`). Para `cash` no: el statement line
   nativo debita `journal_id.default_account_id` y acredita la POS receivable
   (`_get_combine_statement_line_vals`, nativo línea 1452), dejando la POS
   receivable **saldada en cero** y el dinero en la cuenta del diario. Cruzar
   contra la POS receivable descuadraba una cuenta ya en cero y nunca drenaba
   el efectivo. El fallback introducido por el bug #4 del change anterior
   evitaba la violación de `NOT NULL` en Postgres, pero contablemente apuntaba
   mal.

## What Changes

- **Un solo disparador.** `_validate_cross_move()` pasa a ser el único punto
  de entrada, para ambas granularidades, enganchado en
  `action_pos_session_close` después de `super()`. Se elimina la llamada a
  `_create_cross_move_payment` desde `_create_combine_account_payment`, que
  conserva solo su contrato de `foreign_rate`/`foreign_debit`/`foreign_credit`.
- **Granularidad por `split_transactions`**, replicando cómo el nativo agrupa
  sus propias líneas en `_accumulate_amounts`
  (`point_of_sale/models/pos_session.py:892`):
  - `split_transactions=True` → un asiento por `pos.payment`.
  - `split_transactions=False` → un asiento por método y sesión, neteando
    todos sus pagos. Neto cero no crea nada; neto negativo sale por la rama
    saliente, que la ruta combine legacy nunca tuvo.
- **Elegibilidad por `is_foreign_currency`.** Nuevo helper
  `_is_cross_move_eligible(payment_method)`: `is_foreign_currency` +
  `type != 'pay_later'` + ambos diarios de cruce + cuenta transitoria
  resoluble. El campo `apply_one_cross_move` se **elimina** del modelo, la
  vista, `_load_pos_data_fields` y el `.po`.
- **Cuenta transitoria por tipo de método.** `_get_cross_transitory_account`
  ramifica: `cash` → `journal_id.default_account_id`; `bank` →
  `outstanding_account_id or journal_id.default_account_id`; en ambos casos la
  POS receivable de la compañía queda como último recurso, para que una
  configuración incompleta degrade en un cruce omitido y no en un error de
  base de datos.
- **Líneas parametrizadas.** `_line_vals_move_cross_incoming`/`_outgoing`
  reciben `(payment_method, amount, foreign_amount, foreign_rate, partner)` en
  vez de un `pos.payment`, para servir a las dos granularidades. Nuevo
  `_create_cross_move_for` que elige la rama por el signo del importe.
  `_create_cross_move_payment` y `_line_vals_move_cross_payment_incoming` se
  eliminan (quedan muertos), y con ellos la dependencia del renombre
  `payment_id` → `origin_payment_id` en este flujo.
- **Sin cambios de decisión de negocio**: el asiento sigue naciendo en
  `state="draft"`, sin postear, y sigue tomando la secuencia de
  `cross_account_journal` al postearse a mano.

## Impact

- **Capability**: `pos-cross-account-move` (modifica la del change
  `l10n-ve-pos-cross-account-move`, que queda superado en sus requisitos de
  disparo y de cuenta transitoria).
- **Módulo**: `l10n_ve_pos` — `models/pos_session.py`,
  `models/pos_payment_method.py`, `views/pos_payment_method.xml`,
  `i18n/es_VE.po`, `tests/test_pos_session_cross_account_move.py`.
- **Cambio de esquema**: se elimina el campo `apply_one_cross_move`. Odoo no
  borra la columna al desinstalar el campo; queda huérfana e inofensiva.
  Requiere `-u l10n_ve_pos` para que el registro se sincronice.
- **Riesgo de despliegue**: el universo de métodos que cruzan cambia de
  "`apply_one_cross_move=True`" a "`is_foreign_currency=True` **y** ambos
  diarios de cruce". Auditar antes de desplegar:

  ```python
  env["pos.payment.method"].search([
      ("is_foreign_currency", "=", True),
      ("cross_account_journal", "!=", False),
      ("cross_journal", "!=", False),
  ])
  ```

  Un método que salga ahí empieza a cruzar en el próximo cierre aunque tuviera
  `apply_one_cross_move=False`. Métodos `is_foreign_currency=True` sin diarios
  de cruce siguen sin hacer nada, que es el caso mayoritario.
- **Cambio contable en métodos `cash`**: los que ya cruzaban contra la POS
  receivable pasan a cruzar contra la cuenta de su diario de caja. Revisar con
  contabilidad si hay asientos previos que corregir.
