# Fix: bloquear la emisión de una retención con fecha contable anterior a la factura

## Why

Ticket de helpdesk (`https://binaural.odoo.com/odoo/helpdesk/action-389/14984`,
#15019): **"Retención de IVA: Odoo permite registrar y emitir la retención
con Fecha Contable anterior a la Fecha de Factura"**.

Reproducido en staging: se crea una factura (`invoice_date` = 31/08/2026),
se genera y confirma la retención de IVA correspondiente
(`date_accounting` = 31/08/2026), se edita manualmente `date_accounting` a
29/08/2026 (2 días antes de la factura) y se presiona **Aprobar**
(`action_post()`). Odoo lo permite sin ninguna advertencia: la retención
queda `emitted` con una fecha contable anterior al hecho generador (la
factura), lo cual es contrario a la lógica contable/fiscal esperada — una
retención no puede contabilizarse antes de que exista la factura que la
origina.

`action_post()` (`models/account_retention.py:477`) ya valida otras
condiciones antes de emitir (monto de retención vs. total de la factura,
formato del número de comprobante IVA, retención ISLR), pero ninguna
compara `date_accounting` contra la fecha de las facturas de las líneas de
retención.

## What Changes

- `l10n_ve_payment_extension/models/account_retention.py`
  - Nuevo helper `_get_max_invoice_date()`: fecha de factura más reciente
    (`invoice_date_display or invoice_date`) entre
    `retention_line_ids.move_id`.
  - Nuevo helper `_check_accounting_date_vs_invoices()`: compara
    `date_accounting` contra `_get_max_invoice_date()` — no contra la más
    antigua — y lanza `ValidationError` (con el nombre de la factura
    infractora) si es anterior.
  - Nuevo `@api.constrains("date_accounting", "retention_line_ids")
    _check_accounting_date()`: invoca el helper en `create`/`write`, para
    que la inconsistencia **nunca quede guardada**, no solo bloqueada al
    aprobar.
  - `action_post()`: agrega la llamada al helper dentro del `for retention
    in self:` de validaciones previas a emitir (no existía ningún chequeo
    de fechas ahí antes de este cambio). Respeta el contrato `is_automated`
    ya existente en el método (igual que la validación de monto vs.
    factura, línea 497): si viene de cron/acción automatizada, hace
    `message_post(category='exception')` y `return False`. Nota: ese
    `return False` está dentro del `for`, así que interrumpe el
    procesamiento del resto del lote (recordset `self`) — replica el mismo
    comportamiento (y la misma limitación) de la validación de monto
    preexistente, no lo corrige.
- `l10n_ve_payment_extension/tests/test_retention_lifecycle.py`
  - `test_13_accounting_date_before_invoice_date_blocked_on_save`: el
    bloqueo ocurre al **asignar** `date_accounting`, no al aprobar.
  - `test_14_accounting_date_equal_to_invoice_date_allowed`: el límite es
    inclusivo.
  - `test_15_accounting_date_multi_invoice_uses_latest_date`: dos facturas
    con fechas distintas, `date_accounting` posterior a la más antigua pero
    anterior a la más reciente — debe bloquear (verifica explícitamente que
    la comparación usa `max()`, no `min()`, de las fechas de factura).
  - `test_16_accounting_date_check_skipped_without_lines`: sin líneas, no
    hay validación posible y no debe bloquear.
- `l10n_ve_payment_extension/i18n/es_VE.po`
  - Traducción del mensaje, con placeholders nombrados
    (`%(accounting_date)s`, `%(invoice_date)s`, `%(invoice_name)s`).
- `l10n_ve_payment_extension/models/account_retention_line.py`
  - Nuevo `@api.constrains("move_id") _check_retention_accounting_date()`:
    el `@api.constrains` de `account.retention` solo se dispara cuando las
    líneas se tocan a través del padre; un `write` directo sobre
    `move_id` de una línea (código o wizard) lo esquivaba. Este constraint
    a nivel de línea reinvoca
    `retention_id._check_accounting_date_vs_invoices()` para cerrar ese
    hueco.
- `l10n_ve_payment_extension/models/account_move.py`
  - `_prepare_retention_vals()` creaba la retención con `date_accounting =
    self.date` (fecha contable del asiento), sin mirar
    `invoice_date_display`. Cuando la factura tiene `invoice_date_display`
    posterior a `self.date`, la creación automática de la retención desde la
    factura (el camino real que dispara el escenario del ticket) pasaba a
    chocar con el nuevo constraint. Corregido a
    `min(max(self.date, invoice_date_display or invoice_date), hoy)`: nunca
    antes de la factura, pero tampoco después de hoy — `date_accounting` no
    puede quedar en el futuro.
  - `auto_create_islr_retention()` tenía el mismo defecto
    (`date_accounting = fields.Date.today()` fijo) y **no se había
    corregido en la primera pasada**: se llama desde `action_post()` de la
    factura (el mismo bucle que dispara `_create_retention("iva")`), así
    que con ISLR automático e `invoice_date_display` posterior a hoy
    revienta el `action_post()` completo de la factura. Mismo fix:
    `min(max(hoy, invoice_date_display or invoice_date), hoy)`.
- `l10n_ve_payment_extension/wizard/batch_retentions_wizard.py`
  - Mismo defecto en `create_muti_retencion()`, en los dos caminos
    (individual y agrupado por partner): usaban `fields.Date.today()` fijo.
    Corregido con el mismo criterio: `max` contra la fecha de factura (o el
    máximo entre todas las facturas del grupo), con techo en hoy.
- `l10n_ve_payment_extension/__manifest__.py`
  - Bump `19.0.2.0.30` → `19.0.2.0.31` (el bump original del PR,
    `.28 → .29`, se perdió en los merges de `maintenance-19.0` porque la
    base ya traía `.30`).
- `l10n_ve_payment_extension/tests/test_retention_lifecycle.py`
  - `test_13b_accounting_date_before_invoice_date_blocked_on_save_sale`:
    variante de `test_13` con `out_invoice` / `sale_journal`, para anclar el
    escenario literal del ticket (factura de venta), no solo el de compra.
- `l10n_ve_payment_extension/tests/test_payment_concept_setup.py`
  - `test_07_get_retention_iva_values_future_date` retrocedía
    `date_accounting` 60 días sin mover la fecha de la factura (que por
    default queda en hoy) — con la nueva validación eso es precisamente el
    caso que se bloquea, así que el test empezó a fallar. Se ajustó para
    retroceder también `invoice_date_display` de la factura (90 días),
    manteniendo la relación fecha-contable/fecha-factura válida; el test
    sigue verificando lo que le corresponde (que el wizard de libros
    excluye retenciones fuera de su rango de fechas), no la validación de
    este cambio.

## Impact

- **Capability**: `retention-accounting-date-validation` (nueva).
- **Módulo**: `l10n_ve_payment_extension`. Cambia varios métodos (`action_post`,
  `_prepare_retention_vals`, `auto_create_islr_retention`,
  `create_muti_retencion` del wizard batch) más los constraints nuevos; no
  requiere migración de datos, solo bump de versión de manifest.
- **Alcance**: aplica a los tres tipos de retención que comparten
  `action_post()` (`iva`, `islr`, `municipal`) y a los dos sentidos
  (`in_*`/`out_*`), porque todos pasan por la misma validación de fechas
  antes de emitir.
- **Retenciones ya emitidas** con fecha contable inconsistente (como la del
  ticket, `emitted` con `date_accounting` anterior a la factura) **no se
  corrigen con este cambio** — la validación solo bloquea emisiones
  futuras. Si el cliente necesita corregir la retención del caso reportado,
  es una acción manual aparte (cancelar/reemitir con fecha correcta).
- **Riesgo**: bajo-medio. La validación ahora también corre en `write()` vía
  `@api.constrains`, así que cualquier flujo existente que dejara una
  retención con fecha contable inconsistente (aunque fuera sin intención)
  empezará a fallar al guardar. Es el comportamiento que pide el ticket,
  pero conviene vigilar si algún proceso batch dependía del estado laxo
  anterior.
- **Sin verificar en navegador todavía**: pendiente reproducir el escenario
  del ticket en staging tras el fix, confirmando que el botón "Aprobar"
  ahora bloquea con mensaje.
- **Fuera de alcance, confirmado con el equipo**: `wizard/account_payment_register.py:200`
  crea retenciones con `date_accounting = payment_date`, pero ese camino de
  generar retención desde el wizard de registro de pagos es código muerto
  en V19 — no se usa. No se documenta como riesgo porque no hay ejecución
  real que dispare el nuevo constraint por esa vía.
- **Nota de review (aclaración, no un defecto)**: se planteó en la revisión
  humana del PR que `_get_max_invoice_date()` debería descartar líneas de
  retención "canceladas" (por analogía con `_validate_islr_retention`, que
  sí filtra `rl.state != "cancel"`). No aplica: `state` en
  `account.retention.line` es un campo `related="retention_id.state"`, es
  decir, refleja el estado de la retención (padre), no el de la factura. Y
  como `_get_max_invoice_date()` corre con `self.ensure_one()` sobre una
  sola retención, **todas sus líneas comparten siempre el mismo `state`**:
  o la retención está cancelada y todas sus líneas lo reflejan, o no lo
  está y ninguna línea lo refleja. El filtro nunca podría descartar una
  línea individual dentro de una misma retención — es matemáticamente un
  no-op (y de hecho `_validate_islr_retention` tiene el mismo no-op, sobre
  un resultado que además nunca se lee). Tampoco es una vía real para
  "facturas canceladas": `_get_max_invoice_date()` no filtra por
  `move_id.state`, así que si una factura se cancela *después* de creada
  la retención draft, su fecha sigue contando para el máximo — caso borde
  de baja severidad, documentado como fuera de alcance en `spec.md`, no
  como imposible. Conclusión: no hay cambio de código que aplicar aquí,
  solo la aclaración.
- **Fuera de alcance, explícito**: los dos constraints nuevos vigilan el
  lado de la retención (`date_accounting`, `retention_line_ids`, `move_id`
  de la línea). Ninguno vigila el lado de la factura: si `invoice_date_display`
  de una factura ya asociada a una retención `emitted` se mueve hacia
  adelante después de la emisión, el par queda inconsistente sin que nada
  lo detecte. Cerrar ese caso requeriría un constraint en `account.move`
  sobre `retention_iva_line_ids.retention_id`, que toca otro modelo y no
  se incluye en este cambio.
