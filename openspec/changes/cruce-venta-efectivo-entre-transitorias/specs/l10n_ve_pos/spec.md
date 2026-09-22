## MODIFIED Requirements

### Requirement: Cross moves de compensación para métodos en divisa

Al cerrar la sesión (`action_pos_session_close` → `_validate_cross_move`), por cada método de pago que pase `_is_cross_move_eligible` —`is_foreign_currency`, tipo distinto de `pay_later`, `cross_account_journal` y `cross_journal` presentes Y una cuenta transitoria resoluble— el sistema DEBE (MUST) crear en `cross_account_journal` asientos EN BORRADOR (`state="draft"`) con `foreign_debit`/`foreign_credit`, `not_foreign_recalculate = True`, la tasa del pago (`foreign_rate`, también en el encabezado junto con `foreign_currency_id`) y una referencia (`ref`) que identifica sesión/orden/pago; el número secuencial (`name`) se deja vacío para que lo asigne el diario al contabilizar. Un método sin alguno de los dos diarios, o sin la cuenta que le corresponde, se omite en silencio. Bajo `use_suspense=True` la elegibilidad DEBE (MUST) exigir la cuenta transitoria de LOS DOS diarios —el del método y el `cross_journal`—, porque ambas patas salen de un `suspense_account_id`: con el destino vacío la línea se construiría con `account_id = False` y el insert violaría `account_move_line_check_accountable_required_fields` dentro de `action_pos_session_close`, tumbando el cierre de la sesión.

Las cuentas del asiento dependen del **tipo del método** y de **qué originó el saldo**:

- **Venta con método en efectivo** (`type == "cash"`): el asiento DEBE (MUST) cruzar **transitoria contra transitoria**, sin tocar la cuenta por defecto del diario del método ni la cuenta real de liquidez del `cross_journal`:

  | | Cuenta |
  |---|---|
  | DEBE | `payment_method.journal_id.suspense_account_id` (Cuenta transitoria del diario del método) |
  | HABER | `payment_method.cross_journal.suspense_account_id` (Cuenta transitoria del diario afectado) |

  Para un importe neto negativo (devoluciones que superan las ventas del método) el asiento DEBE (MUST) ser el espejo: DEBE la transitoria del `cross_journal`, HABER la del diario del método. La razón de negocio es que la cuenta por defecto del diario del método (la cuenta POS) ya la acredita la **salida de efectivo que el cajero registra al cerrar la sesión**; si el cruce también la acreditara, quedaría drenada dos veces, y las transitorias quedarían cargadas sin nada que las compense.

  `_validate_cross_move` DEBE (MUST) obtener ese asiento pasando `use_suspense=True` a `_is_cross_move_eligible` y a `_create_cross_move_for` para los métodos de tipo `cash` —la misma ruta que ya usa el cash in/out—, y NO DEBE (MUST NOT) modificar `_line_vals_move_cross_incoming`/`_outgoing`, que son compartidas con otros llamadores.

- **Venta con método de banco**: sin cambios. El asiento traslada el saldo de la cuenta transitoria que resuelve `_get_cross_transitory_account` (`outstanding_account_id` o, si está vacía, `journal_id.default_account_id`; como último recurso `company_id.account_default_pos_receivable_account_id`) hacia la cuenta real que resuelve `_get_cross_real_account` (la `payment_account_id` de las líneas de método de pago entrantes o salientes del `cross_journal` según el signo).

- **Llamadores externos**: la variante `use_suspense=True` (cash in/out de `binaural_pos_close`) sigue drenando `journal_id.suspense_account_id` hacia `cross_journal.suspense_account_id` invirtiendo el sentido del asiento, y las diferencias de apertura/cierre (`_post_foreign_statement_difference`, que llama sin `use_suspense`) siguen apuntando a la cuenta real de liquidez.

Que las dos cuentas transitorias de un método sean la misma cuenta es una configuración incompleta, no un error del sistema: el asiento DEBE (MUST) crearse igualmente con DEBE y HABER en esa cuenta, sin efecto contable, para que la configuración incompleta quede visible en vez de esconderse —el mismo criterio que ya aplica el cruce del cash in/out. Es además la configuración por defecto de Odoo, donde `account.journal.suspense_account_id` se computa desde `company.account_journal_suspense_account_id`.

#### Scenario: Venta en efectivo en divisa

- **WHEN** se cierra una sesión con ventas de un método `is_foreign_currency` de tipo `cash` con ambos diarios y ambas cuentas transitorias configuradas
- **THEN** se crea un asiento borrador en `cross_account_journal` que debita la Cuenta transitoria del diario del método y acredita la Cuenta transitoria del `cross_journal`, por el importe neto de sus pagos
- **AND** ni la cuenta por defecto del diario del método ni la cuenta real de liquidez del `cross_journal` aparecen en el asiento

#### Scenario: Neto negativo en efectivo

- **WHEN** las devoluciones del método en efectivo superan sus ventas en la sesión
- **THEN** el asiento sale invertido: debita la Cuenta transitoria del `cross_journal` y acredita la del diario del método

#### Scenario: Método de banco en divisa

- **WHEN** se cierra una sesión con pagos de un método `is_foreign_currency` de tipo `bank`
- **THEN** el asiento sigue acreditando la cuenta transitoria del método (`outstanding_account_id`) y debitando la cuenta real del `cross_journal`, sin cambios respecto al comportamiento anterior

#### Scenario: Diario sin cuenta transitoria

- **WHEN** al método en efectivo le falta `cross_account_journal`, `cross_journal`, o alguno de esos dos diarios no tiene Cuenta transitoria —incluido el caso de que solo falte la del `cross_journal`—
- **THEN** no se crea ningún cross move para ese método y el cierre de sesión no falla

#### Scenario: Las dos transitorias son la misma cuenta

- **WHEN** el diario del método y el `cross_journal` apuntan a la misma Cuenta transitoria (el defecto de Odoo)
- **THEN** el asiento se crea igual, con sus dos patas sobre esa cuenta y sin efecto contable
