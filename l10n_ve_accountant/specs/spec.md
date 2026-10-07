# Spec: `l10n_ve_accountant` — Fix `action_post()` batch-posting crash

> **Nota de esta rama** (`17.0_fix_ta_79281_error_in_confirm_payment`): el fix `self.id`→`move.id`
> descrito abajo ya estaba aplicado en esta rama antes de este trabajo (confirmado por
> `git diff`/`git show HEAD`). Esta spec documenta el fix tal como se investigó y validó en paralelo, en
> el checkout anidado `src/custom/test-countryclub17/odoo-venezuela` — se incluye aquí íntegra por
> trazabilidad. El fix que sí es nuevo en esta rama es el del Addendum (`clean_context()`), la causa raíz
> real, confirmada en producción.

## Contexto

Investigando un error reportado en producción/staging (`contryclub-stg-2`, instancia
`binaural-consultoria-countryclub17`): *"No puede editar el diario de un movimiento de cuenta si se ha
publicado una vez."* al confirmar facturas de venta de suscripciones. Tras una investigación exhaustiva
(múltiples agentes Explore, búsqueda repo-wide, revisión de logs del servidor) se descartó que
`country_sale_subscription`, `country_sale_subscription_fees` o `country_basic_payments` sean la causa —
ninguno escribe `journal_id` sobre un `account.move`, ninguno resetea a borrador un move posteado.

Durante esa investigación se encontró, en cambio, un bug real y confirmado (con test, ver `qc-report.md`)
en `l10n_ve_accountant/models/account_move.py::action_post()`: el wizard de alerta de límite de crédito
usa `self.id` (el recordset completo pasado a `action_post()`) en vez de `move.id` (el registro actual de
la iteración) al construir el contexto del wizard. Esto **no** es la causa confirmada del error de
`journal_id` original, pero es un defecto de fondo real, verificado empíricamente, que hace frágil
cualquier posteo por lote de facturas de venta en este entorno.

Esta spec cubre exclusivamente ese fix puntual — no reabre ni modifica el resto del comportamiento de
`action_post()` (validación de límite de crédito, flujo del wizard en sí).

## Requisitos EARS

### Ubicuos

- U1: El sistema SIEMPRE debe referenciar, dentro del bucle `for move in self:` de `action_post()`, el
  registro de la iteración actual (`move`) al construir cualquier valor específico de ese registro —
  nunca el recordset completo (`self`) para operaciones que asumen un solo registro.

### Basados en evento (Cuando/Entonces)

- E1: CUANDO `action_post()` se invoque sobre un recordset de **un solo** `account.move` de tipo
  `out_invoice`/`out_refund` sin `move_action_post_alert` en el contexto, ENTONCES el sistema debe
  retornar la acción del wizard `move.action.post.alert.wizard` con `context.default_move_id` igual al
  id de esa factura — comportamiento sin cambios (regresión cero).
- E2: CUANDO `action_post()` se invoque sobre un recordset de **2 o más** `account.move` (al menos uno
  `out_invoice`/`out_refund`) sin `move_action_post_alert` en el contexto, ENTONCES el sistema debe
  retornar la acción del wizard referenciando el `id` del **primer** move de la iteración que cumple la
  condición — sin lanzar ninguna excepción.
- E3: CUANDO el escenario de E2 ocurra, ENTONCES ninguna de las facturas del lote debe quedar posteada
  como efecto colateral de la construcción del wizard (el posteo real solo ocurre al confirmar el
  wizard, fuera de alcance de este fix).

### Fuera de alcance

- La validación de límite de crédito (`account_use_credit_limit`/`use_partner_credit_limit`) — sin
  cambios.
- El wizard `move.action.post.alert.wizard` en sí (`action_confirm()`/`action_cancel()`) — sin cambios.
- La causa raíz del error de `journal_id` original en `contryclub-stg-2` — sigue sin confirmarse al 100%;
  este fix es una corrección de un defecto real descubierto durante esa investigación, no una prueba de
  que sea la causa completa.
- Cualquier cambio en `country_sale_subscription`, `country_sale_subscription_fees`,
  `country_basic_payments` — permanecen intactos.

## Addendum: Fix real — fuga de `default_move_id` en `move.action.post.alert.wizard`

**Contexto**: el fix de `self.id`→`move.id` (arriba) resultó ser un bug real pero NO la causa del error de
producción reportado en `contryclub-stg-2`. Se instrumentó temporalmente `account.move.write()` con un
log de diagnóstico (stack completo) que capturó la ocurrencia real en producción, revelando la causa
verdadera con un traceback completo — no una hipótesis.

**Causa raíz confirmada**: `account_move.py::action_post()` abre el wizard con
`context: {'default_move_id': move.id}`. `move_action_post_alert_views.py::action_confirm()` hacía
`self.move_id.with_context(move_action_post_alert=True).action_post()` — `with_context()` solo agrega
claves, nunca limpia el contexto heredado del wizard, que sigue cargando ese `default_move_id`. Cuando
`action_post()` desencadena la reconciliación real de un pago (`_reconcile_after_done()` →
`_create_payment()` → `account.payment.create()`), y esos `payment_values` no fijan `move_id`
explícitamente, el ORM aplica `context['default_move_id']` como default implícito para el campo `move_id`
— y como `account.payment._inherits = {'account.move': 'move_id'}`, Odoo (`odoo/models.py:4632-4645`)
trata eso como "el padre ya existe" y escribe los campos propios del pago (incluyendo su `journal_id`,
el banco del proveedor) **sobre la factura ya posteada** en vez de crear un asiento nuevo — disparando el
guard `posted_before`/`journal_id` del núcleo.

### Requisitos EARS (Addendum)

- U2: El sistema SIEMPRE debe limpiar cualquier clave `default_*` heredada del contexto de apertura de
  `move.action.post.alert.wizard` antes de invocar `action_post()` desde `action_confirm()`, para que
  ninguna creación posterior de registros (pagos, asientos) dentro de esa misma cadena de llamadas herede
  un `default_move_id`/similar no intencional.
- E4: CUANDO se confirme el wizard y esa confirmación dispare la creación de un `account.payment` (vía
  reconciliación de un pago real), ENTONCES ese `account.payment` debe crear su PROPIO asiento contable
  nuevo (`move_id` propio), nunca reutilizar el `account.move` de la factura que originó el wizard.

## No funcionales

- Compatibilidad: el fix debe ser transparente para el caso de un solo registro (E1) — cero regresión.
- Alcance del cambio: una sola línea (`self.id` → `move.id`), sin tocar la firma del método ni su
  contrato de retorno.
- Estado del cambio: temporal, en el working tree de este checkout
  (`src/custom/test-countryclub17/odoo-venezuela`), sin commit — pendiente de autorización explícita
  (Gate 6) tras confirmar en el ambiente real si ayuda a resolver el problema principal reportado.
