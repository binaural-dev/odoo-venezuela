# QC Report: `l10n_ve_accountant` — Fix `action_post()` batch-posting crash

## Contexto

Fix puntual de un bug real, descubierto y confirmado durante la investigación del error de producción
"No puede editar el diario de un movimiento de cuenta si se ha publicado una vez" en `contryclub-stg-2`.
Ver `specs/spec.md` para el alcance exacto y `specs/plan.md` para el análisis técnico completo.

## Hallazgo (bug confirmado, no hipotético)

`l10n_ve_accountant/models/account_move.py::action_post()`, línea 907 (antes del fix):
```python
'context': {'default_move_id': self.id},
```
`self.id` sobre un recordset de 2+ registros lanza `ValueError: Expected singleton` en este Odoo 17 —
confirmado empíricamente en `odoo shell` antes de escribir el test formal:
```
>>> batch._ids
(225, 226)
>>> batch.id
ValueError: Expected singleton: account.move(225, 226)
```

**Impacto real**: cualquier intento de postear 2+ facturas de venta juntas (ej. multi-selección "Publicar"
desde la vista de lista) crashea con un error de servidor no controlado, en vez de mostrar el wizard de
alerta para la primera — perdiendo silenciosamente el procesamiento del resto del lote.

## Cambio aplicado

- `models/account_move.py:907`: `self.id` → `move.id`.
- `tests/test_account_move_post_batch.py` (nuevo): 2 tests.
- `tests/__init__.py`: registrado el nuevo archivo.

## Evidencia de validación (TDD real, RED confirmado antes del fix)

| Paso | Resultado |
|---|---|
| RED (antes del fix) — `test_action_post_batch_of_two_invoices_crashes_on_self_id` | ✅ confirmado: `ValueError: Expected singleton` reproducido tal cual, con `assertRaises(ValueError)` |
| GREEN (después del fix) — renombrado a `test_action_post_batch_of_two_invoices_returns_wizard_for_first_move` | ✅ PASS: sin excepción, `res['context']['default_move_id'] == invoice_1.id`, ninguna factura posteada |
| Sanity check — `test_action_post_single_invoice_returns_wizard_with_its_own_id` | ✅ PASS antes y después del fix (comportamiento sin cambios para un solo registro, E1) |
| Pre-commit (pylint_odoo) | ✅ 0 hallazgos en los 2 archivos modificados — los hallazgos reportados al correr sobre el módulo completo son preexistentes en archivos no tocados (`payment_report.py`, `account_journal.py`, `all_payment_report.py`, `__manifest__.py`) |
| Suite completa `l10n_ve_accountant` en BD fresca (`tests_l10nve_fix_check`) | ✅ **175/175 tests, 0 fallos, 0 errores** (confirmado también ANTES del fix, en otra BD fresca: los mismos 175/0/0, descartando contaminación de estado de la BD reutilizada de sesiones previas como causa de fallos vistos en un paso intermedio) |
| `country_sale_subscription` (junto con el fix) | ✅ 116 tests, mismas 2 fallas preexistentes de siempre (`test_297_foreign_rates_recompute_via_alternate`, `test_910_account_payment_create_foreign_currency`), 0 nuevas |
| `country_sale_subscription_fees` (junto con el fix) | ✅ sin fallos |
| `country_basic_payments` en su configuración real de dependencias (aislado, sin `l10n_ve_accountant` — no es su dependencia) | ✅ **14/14 tests, 0 fallos, 0 errores** |

**Nota sobre un falso positivo de regresión**: al validar `country_basic_payments` en la MISMA base que
ya tenía `l10n_ve_accountant` instalado (combinación de módulos que no cohabitan en la configuración real
de `depends` de ningún módulo), 3 de sus tests fallaron (`test_action_post_confirms_pending_transaction`,
`test_action_post_does_not_touch_unrelated_invoices`, `test_action_post_reuses_the_receipt_stored_on_the_transaction`)
porque el wizard de `l10n_ve_accountant` intercepta `action_post()` de forma incondicional para cualquier
`out_invoice`, algo que esos tests no anticipan (asumen un posteo directo). Se confirmó que esto es un
artefacto de la metodología de verificación, no una regresión del fix: `country_basic_payments` corrido
en su configuración real y aislada (sin `l10n_ve_accountant`, que no es su dependencia) pasa 14/14 limpio.

## Estado

- **Sin commit** — cambio vive únicamente en el working tree de
  `src/custom/test-countryclub17/odoo-venezuela` (repo git separado), a la espera de:
  1. Confirmación en el ambiente real (`contryclub-stg-2` o donde corresponda) de si este fix ayuda con
     el problema principal reportado.
  2. Autorización explícita del usuario (Gate 6) antes de cualquier commit.

**Veredicto**: PASS (a nivel de este fix aislado). Pendiente confirmación de campo y Gate 6.

## Addendum: Fix real confirmado — fuga de `default_move_id` (causa raíz del error de producción)

**Contexto**: el fix anterior (`self.id`→`move.id`) no resolvió el error reportado en `contryclub-stg-2`.
Se instrumentó `account.move.write()` con un log temporal de diagnóstico (WARNING + stack completo
cuando `journal_id in vals` y `posted_before=True` con valor distinto) para capturar la PRÓXIMA
ocurrencia real, en vez de seguir adivinando. **Se capturó exitosamente** — traceback completo con la
causa exacta, no una hipótesis.

**Causa raíz**: `move_action_post_alert_views.py::action_confirm()` llamaba a
`self.move_id.with_context(move_action_post_alert=True).action_post()` sin limpiar el `default_move_id`
que el propio wizard heredó al abrirse (`context: {'default_move_id': move.id}`, seteado por
`account_move.py::action_post()`). Cuando esa llamada desencadena una reconciliación de pago real
(`_reconcile_after_done()` → `_create_payment()` → `account.payment.create()`), el ORM aplica el
`default_move_id` filtrado como valor implícito del campo `move_id` — y como `account.payment` usa
`_inherits` hacia `account.move`, el núcleo (`odoo/models.py:4632-4645`) trata esto como "el padre ya
existe" y escribe los campos del pago (incluyendo su `journal_id`, el banco del proveedor) sobre la
factura ya posteada, dsiparando el guard.

**Fix**: `action_confirm()` ahora limpia el contexto con `clean_context()` (utilidad del núcleo, ya usada
en este mismo repo para el mismo propósito) antes de llamar `action_post()`.

**Evidencia de validación**:

| Validación | Resultado |
|---|---|
| Instrumentación de diagnóstico | ✅ Capturó el stack real en producción — `account.payment.create()` → `odoo/models.py:4645 parent.write()` → `l10n_ve_invoice/account_move.py:330` → `l10n_ve_accountant/account_move.py:375`, exactamente como se documentó en `plan.md` |
| Tests nuevos (`test_move_action_post_alert_wizard.py`, 3 tests) | ✅ 3/3 PASS — incluyendo la reproducción directa del bug (`assertRaises(UserError)` con el MISMO log de diagnóstico disparándose en el test, confirmando 1:1 el mecanismo de producción) y la confirmación de que el contexto limpio lo evita |
| Regresión completa `l10n_ve_accountant` (BD fresca `tests_l10nve_wizfix_check`) | ✅ **178/178 tests, 0 fallos, 0 errores** |
| Pre-commit | Pendiente de correr sobre el diff final (instrumentación de diagnóstico + fix + tests) antes de cualquier commit |

**Confirmación en producción**: tras desplegar el fix (recargado en el proceso vivo a las 18:11:24), se
monitorearon los logs de `contryclub-stg-2` esperando una nueva reproducción real del escenario. El
usuario confirmó explícitamente que, al reintentar la acción que antes disparaba el error de forma
consistente, **ya no ocurre** — ni el error original ni el marcador de diagnóstico volvieron a aparecer.
Esto cierra el ciclo de confirmación de campo, además de la evidencia de tests y regresión ya
documentada arriba.

**Instrumentación de diagnóstico retirada**: ya cumplió su propósito (capturó la causa real en
producción) y el fix quedó confirmado — se eliminó el bloque de log temporal de `account.move.write()`.
Regresión completa re-ejecutada tras retirarla en BD fresca (`tests_l10nve_final_check`): **178/178
tests, 0 fallos, 0 errores** — idéntico resultado, confirmando que la instrumentación no dejó ningún
residuo de comportamiento.

**Estado**: el fix real (`clean_context()`) está confirmado funcionando en producción, con la
instrumentación de diagnóstico ya retirada. Sin commit — el usuario prefiere esperar más confirmación
antes de autorizar Gate 6.

**Veredicto**: PASS. Confirmado en producción. Pendiente Gate 6 (autorización de commit).
