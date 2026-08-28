# El cruce de ventas apunta siempre a la Cuenta Transitoria del `cross_journal`

## Why

El cruce automático (capability `pos-cross-account-move`) mandaba las **ventas**
a la cuenta de **liquidez confirmada** del `cross_journal`
(`inbound/outbound_payment_method_line_ids.payment_account_id`), mientras que las
**entradas y salidas de efectivo** (`use_suspense=True`, ver capability
`pos-close-foreign-cash`) aterrizan en la **Cuenta Transitoria** del mismo diario
(`cross_journal.suspense_account_id`), pendientes de conciliar contra un extracto
bancario real.

Se decidió que las ventas terminen **siempre** en la misma cuenta transitoria que
cash in/out, para que todo el efectivo foráneo de la sesión (ventas + movimientos
de caja) se acumule en una sola cuenta pendiente de conciliar contra el banco real,
en vez de darse por confirmado de una vez. **No es opcional ni configurable**: es
el comportamiento del cruce de ventas.

Lo que **no** cambia — y por qué no puede ser un simple `use_suspense=True` en
ventas — es la pata de **origen**. En una venta, el nativo fija una contrapartida
explícita (POS por cobrar) y deja el dinero en `journal_id.default_account_id` (la
cuenta de tránsito del método), **no** en `suspense_account_id`. Vaciar la suspense
en ventas descuadraría (drenaría una cuenta sin saldo). El origen, por tanto, se
queda tal cual (`default_account_id`), y tampoco hay inversión de polaridad: solo
cambia la cuenta de la pata del `cross_journal`.

## What Changes

- **`_validate_cross_move` (ventas) pasa siempre `real_to_suspense=True`** a
  `_create_cross_move_for`, en ambas granularidades (split y combine).
- **Parámetro `real_to_suspense=False`** en `_get_cross_real_account`,
  `_line_vals_move_cross_incoming`/`_outgoing` y `_create_cross_move_for`. Con
  `real_to_suspense=True`, `_get_cross_real_account` devuelve
  `cross_journal.suspense_account_id` **solo para esta pata real**, dejando
  intactos `_get_cross_transitory_account` (origen) y la polaridad
  débito/crédito del asiento. El parámetro existe para **acotar el cambio a
  ventas**: es el único discriminador entre el llamador de ventas y el de
  diferencias, que también van por `use_suspense=False`.
- **Alcance: solo ventas.** Ningún otro llamador pasa el parámetro. Las
  diferencias de apertura/cierre de `binaural_pos_close`
  (`_post_foreign_statement_difference`) siguen apuntando a la liquidez
  confirmada, y cash in/out sigue por `use_suspense=True` (que ya devuelve la
  suspense; el nuevo parámetro es indiferente ahí).
- **Sin campo de configuración.** No se agrega ningún flag al método de pago ni a
  la compañía: el comportamiento es único.
- **Sin cambios de decisión de negocio**: el asiento sigue naciendo en
  `state="draft"` desde `_create_cross_move` (su posteo depende del entorno, no de
  este cambio) y toma la secuencia del `cross_account_journal` al postearse.

## Impact

- **Capability**: `pos-cross-account-move` (modifica la pata destino de ventas
  respecto de los change previos).
- **Módulo**: `l10n_ve_pos` — `models/pos_session.py`, `__manifest__.py`
  (1.10 → 1.11).
- **Cambio de esquema**: ninguno (no se agrega ni elimina campo). En bases donde
  una versión anterior de este change llegó a crear la columna
  `cross_sales_to_suspense`, Odoo no la borra; queda huérfana e inofensiva.
- **Cambio contable en ventas de métodos foráneos**: los métodos con cruce
  (`is_foreign_currency` + ambos diarios) pasan a cruzar sus ventas contra
  `cross_journal.suspense_account_id` en vez de la cuenta de liquidez. Afecta a
  todo cliente de `l10n_ve_pos` con métodos de cruce configurados. Requiere
  `-u l10n_ve_pos`. Revisar con contabilidad antes de desplegar en clientes ya en
  producción con cruce activo.
