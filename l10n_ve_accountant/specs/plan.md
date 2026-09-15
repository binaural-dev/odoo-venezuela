# Plan: `l10n_ve_accountant` — Fix `action_post()` batch-posting crash

## Codebase Research

`l10n_ve_accountant/models/account_move.py`, líneas 896-928 (antes del fix):

```python
def action_post(self):
    if not self.env.context.get("move_action_post_alert"):
        for move in self:
            if move.move_type in ("out_invoice", "out_refund"):
                return {
                    'name': _('Alert'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'move.action.post.alert.wizard',
                    'view_mode': 'form',
                    'view_id': False,
                    'target': 'new',
                    'context': {'default_move_id': self.id},   # <- bug
                }
    for invoice in self:
        if (invoice.company_id.account_use_credit_limit
                and invoice.partner_id.use_partner_credit_limit):
            ...
    return super().action_post()
```

**Hallazgo empírico** (confirmado en `odoo shell`, no solo por inspección): `recordset.id` sobre un
recordset con más de un registro lanza `ValueError: Expected singleton` en este Odoo 17
(`odoo/fields.py:5200`, el descriptor `Id` no tiene el mismo trato especial que otros métodos
"multi-record-safe" como `.ids`). Esto significa que la primera vez que `action_post()` encuentra un
`out_invoice`/`out_refund` dentro de un `self` con 2+ registros, el `return {...: self.id}` no retorna
silenciosamente el id equivocado — **crashea** antes de construir el dict.

**Wizard relacionado** (`wizard/move_action_post_alert_views.py`) — no requiere cambios, ya usa
`self.move_id` (un `Many2one`, singleton por diseño del wizard transitorio) correctamente.

**Cadena de dependencias verificada**: este método es llamado por el flujo estándar del botón "Confirmar"
de Odoo (`account.move.action_post()` del núcleo → override de este módulo primero en el MRO para
`out_invoice`/`out_refund`), y también indirectamente por `country_sale_subscription/models/
payment_transaction.py::_reconcile_after_done()` (que pasa `move_action_post_alert=True`, evitando esta
rama por completo) y por `country_basic_payments/models/account_move.py::action_post()` (que llama
`super().action_post()` primero — si `l10n_ve_accountant` está en el MRO y NO se pasó el flag, recibe el
dict del wizard en vez de un posteo real; comportamiento preexistente, sin cambios por este fix).

## Implementation Strategy

Cambio de una sola línea: `'context': {'default_move_id': self.id}` → `'context': {'default_move_id':
move.id}`. `move` ya está disponible en el scope (variable de iteración del `for move in self:`
inmediatamente superior) — no requiere ninguna variable nueva, importación, ni cambio de firma.

Efecto: para un `self` de un solo registro, `move` y `self` son el mismo registro (mismo `.id`) — cero
cambio de comportamiento (E1). Para un `self` de 2+ registros, la iteración se detiene en el primer
`out_invoice`/`out_refund` encontrado, y el wizard ahora referencia correctamente ESE registro específico
en vez de intentar leer `.id` sobre el recordset completo (E2/E3).

## Testing Strategy

`tests/test_account_move_post_batch.py` (nuevo, aislado de `test_accountant.py` para no interferir con su
suite existente):
- `test_action_post_single_invoice_returns_wizard_with_its_own_id` — sanity check, un solo registro,
  confirma que `default_move_id == invoice.id` (E1).
- `test_action_post_batch_of_two_invoices_returns_wizard_for_first_move` — el caso que antes crasheaba;
  tras el fix, confirma `res['res_model'] == 'move.action.post.alert.wizard'`,
  `res['context']['default_move_id'] == invoice_1.id` (el primero de la iteración), y que ninguna de las
  2 facturas queda posteada (E2/E3).

Ciclo TDD real seguido: la segunda prueba se escribió primero en RED
(`self.assertRaises(ValueError): batch.action_post()`, confirmando el bug tal cual existía), luego se
aplicó el fix y se re-escribió la aserción a GREEN (sin excepción, `default_move_id` correcto) — evidencia
completa en `qc-report.md`.

## Risks

- Bajo riesgo: cambio de una sola línea, sin alterar la lógica de negocio (validación de crédito, flujo
  del wizard). El scope de la variable `move` ya existía en el mismo bloque.
## Addendum: Fix real — `clean_context()` en `move.action.post.alert.wizard::action_confirm()`

### Codebase Research

Instrumentación temporal en `account_move.py::write()` (log de `WARNING` con
`traceback.format_stack()` cuando `journal_id in vals` y `move.posted_before and move.journal_id.id !=
vals['journal_id']`) capturó la ocurrencia real en `contryclub-stg-2` con el stack completo. El stack
mostró la escritura ocurriendo DENTRO de `account.payment.create()`, en `odoo/models.py:4632-4645`:

```python
for model_name, parent_name in self._inherits.items():
    ...
    for data in data_list:
        if not data['stored'].get(parent_name):
            parent_data_list.append(data)          # crea un padre NUEVO
        elif data['inherited'][model_name]:
            parent = self.env[model_name].browse(data['stored'][parent_name])
            parent.write(data['inherited'][model_name])   # <- reutiliza un padre EXISTENTE
```

`data['stored'].get('move_id')` resultó verdadero porque el contexto de ejecución (heredado desde el
wizard, vía `self.env.context`) contenía `default_move_id` — Odoo aplica `context['default_<campo>']`
como valor implícito para cualquier campo ausente en los vals de `create()`. Como
`account_payment/models/payment_transaction.py::_create_payment()` (núcleo) nunca fija `move_id`
explícitamente en `payment_values`, ese default filtrado se coló, apuntando al `account.move` de la
factura (ya posteada) en vez de crear el asiento propio del pago.

### Implementation Strategy

`move_action_post_alert_views.py::action_confirm()`:
```python
from odoo.tools import clean_context

def action_confirm(self):
    self.move_id.with_context(
        clean_context(self.env.context), move_action_post_alert=True,
    ).action_post()
    return {'type': 'ir.actions.client', 'tag': 'reload'}
```
`clean_context()` (utilidad ya usada en el núcleo de este mismo repo,
`odoo-17.0/addons/account/models/account_move.py::_sync_dynamic_line()`, para exactamente esta clase de
problema) elimina cualquier clave `default_*` del contexto antes de propagarlo. `move_action_post_alert`
se agrega DESPUÉS de limpiar, para no perderlo.

### Testing Strategy

`tests/test_move_action_post_alert_wizard.py` (nuevo, 3 tests):
- `test_wizard_context_carries_the_leaked_default_move_id`: sanity check, confirma que el escenario es
  real (el wizard, abierto tal como lo hace `action_post()`, sí carga `default_move_id`).
- `test_action_confirm_does_not_leak_default_move_id_downstream`: espía `action_post()` (vía
  `unittest.mock.patch.object`) para capturar el contexto con el que se le llama desde
  `action_confirm()`, confirma que `default_move_id` ya no está presente y que `move_action_post_alert`
  sigue presente.
- `test_downstream_account_payment_create_does_not_target_the_invoice_move`: reproducción directa del
  mecanismo de corrupción — crea un `account.payment` (sin `move_id` explícito, igual que el núcleo)
  bajo el contexto SUCIO del wizard (`assertRaises(UserError)`, reproduce el error real de producción
  tal cual, incluyendo el mismo log de diagnóstico en la captura de test) y luego bajo el contexto
  LIMPIO (`clean_context()`), confirmando que el pago obtiene su propio asiento, no el de la factura.

### Risks

- Bajo riesgo: `clean_context()` es una utilidad estándar y ya probada del núcleo, usada exactamente para
  este propósito (evitar fuga de `default_*` en cadenas de creación anidadas). No cambia ningún
  comportamiento salvo eliminar contaminación de contexto no intencional.
- Riesgo de entorno (no de código): al validar este fix junto con otros módulos en la misma base de
  datos de pruebas, se detectó que `country_basic_payments` (que NO depende de `l10n_ve_accountant`) veía
  sus propios tests fallar si `l10n_ve_accountant` se instalaba junto a él en la misma BD — esto es un
  artefacto de la metodología de verificación (combinar módulos que no cohabitan en su configuración real
  de `depends`), no una regresión del fix; confirmado corriendo `country_basic_payments` en aislamiento
  real (ver `qc-report.md`).
