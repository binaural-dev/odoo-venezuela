## Why

Al instalar el módulo de Contabilidad de Binaural, los diarios de tipo Banco podían quedar sin cuenta contable asignada en sus métodos de pago (pagos entrantes y salientes) de forma inconsistente: Odoo permitía guardar el diario y registrar pagos con ese método sin cuenta en algunos flujos, pero bloqueaba en otros. Un pago confirmado sin cuenta nunca genera asiento contable, y una vez confirmado no puede corregirse después -- el asiento se pierde de forma permanente.

La spec de `l10n_ve_accountant` documentaba una sola validación (`_check_payment_method_line_accounts`, constrains del diario) que no cubría el problema completo: no existía ninguna garantía sobre `default_account_id` del diario en sí, la propagación automática a las líneas de método de pago no estaba documentada, el constrains del diario no se disparaba al escribir directo sobre una línea (API/importación), y el camino de confirmación del pago (`action_post`) no tenía ningún guard -- un pago podía confirmarse sin asiento y sin error cuando la app completa de Contabilidad está instalada (el core salta su propio fallback en ese caso).

## What Changes

- `l10n_ve_accountant`: `default_account_id` obligatorio en diarios `bank` (`_check_default_account_id_required_for_bank`, ya existía en código, no documentado).
- `l10n_ve_accountant`: propagación automática de `default_account_id` a `payment_account_id` en las líneas de método de pago, entrantes y salientes (`_fill_payment_account_id_from_default`), sin romper líneas agregadas manualmente al editar la cuenta de un diario ya guardado.
- `l10n_ve_accountant`: constrains nuevo en `account.payment.method.line` (`_check_payment_account_id_required_for_bank`) que cierra el camino de escritura directa sobre la línea, con `create()` rellenando la cuenta antes de validar para no romper la creación de diarios banco.
- `l10n_ve_accountant`: override de `_get_outstanding_account` y guard en `action_post` (`account.payment`) que bloquean confirmar un pago de banco sin cuenta, en vez de dejarlo sin asiento y sin error (o caer en el fallback genérico de `transfer_account_id`/chart template).
- `l10n_ve_accountant`: migración `19.0.1.0.28` para diarios banco existentes cuyas líneas quedaron sin cuenta.
- Documentación: se actualiza la spec para reflejar todo este comportamiento (antes solo documentaba el constrains del diario, sin mencionar `default_account_id`, la propagación automática, ni el bloqueo de confirmación).

## Impact

- Specs afectadas: `l10n_ve_accountant` (requirement "Métodos de pago bancarios con cuenta obligatoria" actualizado; 4 requirements nuevos: "Cuenta bancaria obligatoria en diarios tipo banco", "Propagación automática de la cuenta bancaria a los métodos de pago", "Bloqueo de confirmación de pagos de banco sin cuenta contable", "Migración de diarios banco existentes sin cuenta").
- Código: `l10n_ve_accountant/models/account_journal.py`, `l10n_ve_accountant/models/account_payment.py`, `l10n_ve_accountant/models/account_payment_method_line.py`, `l10n_ve_accountant/migrations/19.0.1.0.28/`.
- Fuera de alcance de este cambio (documentado como pendiente): la fuente automática de `default_account_id` mismo (de dónde sale la cuenta real, requisito 1 del ticket 81735) y la exención explícita de pagos de Punto de Venta en el guard de `action_post` -- `point_of_sale` no es dependencia de este módulo.

## Referencias

- Ticket: https://binaural.odoo.com/odoo/action-341/project.task/81735
- PR: https://github.com/binaural-dev/odoo-venezuela/pull/1344
