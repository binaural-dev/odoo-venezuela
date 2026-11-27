## Why

El ticket 15399 pide validaciones al crear o editar un método de pago del PdV (`pos.payment.method`):

1. **Cuentas transitorias iguales.** Nada impide que el diario del método (`journal_id`) y su diario afectado de
   banco o efectivo (`cross_journal`) tengan la misma cuenta transitoria (`suspense_account_id`). Es además lo
   que pasa por defecto: Odoo le pone a todo diario de banco y efectivo la transitoria de la compañía
   (`company.account_journal_suspense_account_id`). En un método en moneda alterna o con moneda de cobro, el
   cruce de la venta en efectivo va de una transitoria a la otra (change `cruce-venta-efectivo-entre-transitorias`,
   ticket 15219). Con la misma cuenta en los dos lados, el asiento no mueve nada y el dinero nunca pasa del
   diario del método al real. Hoy eso se ve recién en la contabilidad, después de cerrar sesiones.
2. **Diario en otra moneda que la caja.** El método se guarda con un diario cuya moneda no es la de su caja
   (p. ej. un diario en USD en una caja en Bs). El error del core («All payment methods must be in the same
   currency as the Sales Journal…», `pos.config._check_currencies`) aparece solo al guardar la caja o al abrir la
   sesión, no al guardar el método.
3. **Diarios de cruce faltantes.** Un método marcado en moneda alterna se puede guardar sin alguno de
   esos diarios. Si falta uno, el cruce se omite al cierre.

## What Changes

- `l10n_ve_pos` (`pos.payment.method`): un método en moneda alterna (`is_foreign_currency`) o con moneda de cobro
  (`tender_currency_id`) no se guarda si su diario y su diario afectado tienen la misma cuenta transitoria.
- `l10n_ve_pos` (`account.journal`, modelo nuevo en el módulo): la misma regla se revisa al cambiar la cuenta
  transitoria de un diario, que es donde se edita, para todos los métodos que lo usan como diario o como diario
  afectado.
- `l10n_ve_pos` (`pos.payment.method`): un método no se guarda si su diario tiene una moneda distinta de la de
  alguna de sus cajas. Un diario sin moneda se acepta. Es la regla del core, revisada también desde el método.
- `l10n_ve_pos` (`pos.payment.method`): al marcar moneda alterna, el formulario pide ambos diarios de cruce.
  El modelo exige ambos al activar la opción o cambiar cualquiera de esos diarios.
- Traducciones `es_VE` de los mensajes nuevos.
- Pruebas nuevas en `l10n_ve_pos`, y una prueba existente del cruce se ajusta (ver tasks.md, 4.2).
- Versión de `l10n_ve_pos`: el siguiente parche disponible en `19.0`.

El código inicial vino de un parche probado en el staging `19posconsultoria` (shell con rollback). Ese parche exigía
que el diario de un método en moneda alterna o con moneda de cobro estuviera en la moneda de la
compañía aunque el método no tuviera caja. Este change la quita (design.md, D3).

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `l10n_ve_pos`: tres requisitos nuevos de validación del método de pago. El escenario «Las dos transitorias son
  la misma cuenta» del change abierto `cruce-venta-efectivo-entre-transitorias` se aclara: sigue valiendo para
  los métodos guardados antes de esta regla.

## Non-goals y limitaciones

- **La caja no se hace obligatoria en el método** (design.md, D1).
- **Lo ya guardado no se revalida.** Un método que hoy tiene las dos transitorias iguales, o un diario en otra
  moneda que su caja, sigue funcionando hasta que se le cambie un diario, la moneda alterna, la moneda de cobro o
  la caja (design.md, D4).
- Los métodos en moneda alterna guardados antes de la regla siguen omitiendo el cruce si les falta un diario.
  El modelo exige completarlos cuando se vuelve a activar la moneda alterna o se cambia uno de los diarios.
- **Cambio de moneda de un diario.** Si se cambia la moneda de un diario que ya usa un método, el método no se
  revalida. Lo sigue atajando el core al guardar la caja o al abrir la sesión, como hoy.

## Impact

- **Código:** `l10n_ve_pos/models/pos_payment_method.py`,
  `l10n_ve_pos/models/account_journal.py` (archivo nuevo), `l10n_ve_pos/models/__init__.py`,
  `l10n_ve_pos/views/pos_payment_method.xml` y `l10n_ve_pos/i18n/es_VE.po`. Sin datos, JS ni migración.
- **Pruebas:** archivo nuevo `l10n_ve_pos/tests/test_pos_payment_method_validations.py`. Se ajusta
  `test_cash_sale_emits_the_move_even_when_both_suspense_accounts_match` en
  `l10n_ve_pos/tests/test_pos_session_cross_account_move.py`.
- **Usuarios:** quien configura métodos en moneda alterna o con moneda de cobro tiene que crear una cuenta
  transitoria para cada diario. Con la configuración por defecto de Odoo, el método no se guarda hasta hacerlo.
- **Change abierto `cruce-venta-efectivo-entre-transitorias`:** se aclara su escenario de transitorias iguales
  (no se archiva aquí, le quedan pruebas funcionales abiertas).
- **Despliegue:** `-u l10n_ve_pos`, sin migración.
