# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el bug del ticket #15019 (id 14984): `action_post()`
      no valida `date_accounting` contra la fecha de la factura de origen
- [x] 1.2 Ubicado el punto de la validación existente en
      `models/account_retention.py:477` (`action_post`), junto al resto de
      chequeos previos a emitir (monto vs. factura, número de 14 dígitos,
      validación ISLR)
- [x] 1.3 Confirmado el campo de fecha de factura disponible:
      `move_id.invoice_date_display or move_id.invoice_date`, ya usado en
      `account_retention_line.py:336`

## 2. Fix

- [x] 2.1 `_get_max_invoice_date()`: fecha de factura más reciente entre
      `retention_line_ids.move_id` (`invoice_date_display or invoice_date`)
- [x] 2.2 `_check_accounting_date_vs_invoices()`: compara contra la más
      reciente (`max`, no `min`) y nombra la factura infractora en el
      mensaje
- [x] 2.3 `@api.constrains("date_accounting", "retention_line_ids")
      _check_accounting_date()`: bloquea en `create`/`write`, no solo al
      aprobar
- [x] 2.4 `action_post()`: usa el mismo helper; respeta `is_automated`
      (chatter + `return False` en vez de reventar el lote, igual que la
      validación de monto existente)
- [x] 2.5 Traducción del mensaje (placeholders nombrados) en
      `l10n_ve_payment_extension/i18n/es_VE.po`
- [x] 2.6 `account_retention_line.py`: `@api.constrains("move_id")
      _check_retention_accounting_date()` — cierra el hueco donde un
      `write` directo sobre `move_id` de la línea esquivaba el constraint
      del padre; colapsado a `self.retention_id._check_accounting_date_vs_invoices()`
      (mapeo sobre el M2o, deduplica solo) en vez de iterar `for record in
      self`, para no rehacer `_get_max_invoice_date()` una vez por línea
      modificada
- [x] 2.7 Bump de versión en `__manifest__.py`: `19.0.2.0.28` →
      `19.0.2.0.29` (superado luego en 3b.5: la base subió a `.30` y el
      bump propio se perdió en el merge, resuelto con `.31`)

## 3. Verificación

- [x] 3.1 `test_13_accounting_date_before_invoice_date_blocked_on_save`:
      bloqueo al asignar `date_accounting`, no al aprobar (anclado a
      `invoice_date_display`, no `invoice_date`)
- [x] 3.2 `test_14_accounting_date_equal_to_invoice_date_allowed`: límite
      inclusivo (ídem, `invoice_date_display`)
- [x] 3.3 `test_15_accounting_date_multi_invoice_uses_latest_date`: caso que
      la versión con `min()` dejaba pasar; fija `invoice_date_display`
      explícitamente distinto en cada factura y agrega aserción directa
      sobre `_get_max_invoice_date()` para que falle si se revierte a `min()`
- [x] 3.4 `test_16_accounting_date_check_skipped_without_lines`: sin líneas
      no bloquea
- [x] 3.5 Validada sintaxis de los archivos modificados (`ast.parse`)
- [x] 3.6 Corregida regresión en `tests/test_payment_concept_setup.py`
      (`test_07_get_retention_iva_values_future_date`): retrocedía
      `date_accounting` 60 días sin mover la fecha de factura; ahora también
      retrocede `invoice_date_display` de la factura para no chocar con la
      nueva validación
- [ ] 3.7 Correr la suite completa del módulo
      (`l10n_ve_payment_extension`) en una instancia Odoo real
- [ ] 3.8 Reproducir el escenario exacto del ticket en staging
      (`https://binaural-consultoria-jose-leandro7-staging-37438704.dev.odoo.com`)
      y confirmar que tanto guardar como "Aprobar" bloquean con el mensaje
      esperado
- [ ] 3.9 Decidir si la retención ya emitida del ticket (con fecha contable
      inconsistente) requiere corrección manual, y quién la ejecuta
- [x] 3.10 Confirmado con el equipo: el camino de generación de retención
      desde `wizard/account_payment_register.py` está muerto en V19, no se
      usa — no requiere test ni fix
- [x] 3.11 Code review de 3ra ronda: confirmó `max()`/`min()`, bloqueo en
      `write`, `is_automated`, tests bien anclados a `invoice_date_display`,
      y validez del uso de `.new()` en `test_15`; encontró la regresión de
      3.6 y el hueco de 2.6, ambos corregidos — pendiente solo de correr en
      Odoo real (3.7/3.8)
- [x] 3.12 `test_13`/`test_15` envueltos en `self.cr.savepoint()` para que
      la no-persistencia sea real y aserible (antes solo se comprobaba
      `state == "draft"`, que no cambia pase lo que pase); se agregó
      aserción sobre `date_accounting` sin cambiar (`test_13`) y sobre el
      conteo de retenciones sin crecer (`test_15`)
- [x] 3.13 Code review de 4ta ronda (independiente): descartó 3 de 4
      sospechas planteadas (constraint de línea no rompe con `.new()` ni
      con `ensure_one()`; los dos constraints no producen mensajes
      divergentes porque comparten el mismo helper; el ajuste de
      `test_payment_concept_setup.py` es correcto y el orden de escritura
      importa); confirmó 1 ineficiencia real (bucle O(N²), corregido en
      2.6) y encontró que `proposal.md`/`spec.md` describían un
      comportamiento del flujo automatizado distinto al real — corregido
      en la sección 4

## 3b. Ronda de review humano (PR #1302)

- [x] 3b.1 `_prepare_retention_vals()` (`models/account_move.py`) y
      `create_muti_retencion()` (`wizard/batch_retentions_wizard.py`):
      corregido `date_accounting` para que use
      `max(fecha_actual, invoice_date_display or invoice_date)` en vez de
      una fecha fija — cierra el hueco real donde la creación automática de
      retenciones podía chocar contra el nuevo constraint
- [x] 3b.2 Agregado `test_13b_accounting_date_before_invoice_date_blocked_on_save_sale`
      (variante de `test_13` con `out_invoice`/`sale_journal`) para anclar
      el escenario de venta, no solo el de compra
- [x] 3b.3 Descartado el punto "líneas canceladas inflan
      `_get_max_invoice_date()`": `state` en `account.retention.line` es
      `related="retention_id.state"` (estado de la retención, no de la
      factura); dentro de una sola retención todas las líneas comparten el
      mismo valor, así que el filtro propuesto no cambia nada. Documentado
      en `proposal.md` y como escenario en `spec.md`
- [x] 3b.4 Confirmado que la ubicación de `openspec/` dentro del módulo
      (`l10n_ve_payment_extension/openspec/`) sigue un patrón ya usado en
      otros módulos del repo (además del root en `openspec/specs/` en la
      raíz) — no requiere moverse
- [x] 3b.5 Auditoría independiente (5ta ronda) encontró 2 bloqueantes reales
      sin corregir en 3b.1-3b.4:
      - `auto_create_islr_retention()` (`models/account_move.py`) tenía el
        mismo defecto que `_prepare_retention_vals()` y no se había
        tocado — se llama desde `action_post()` de la factura junto con
        `_create_retention("iva")`, así que revienta el `action_post()`
        completo con ISLR automático e `invoice_date_display` futura.
        Corregido con el mismo criterio de 3b.1
      - El bump de versión de 2.7 quedó pisado por los merges de
        `maintenance-19.0` (la base ya estaba en `.30`); repuesto a `.31`
      También corrigió el fix de 3b.1: `date_accounting` no debe quedar en
      el futuro respecto a hoy, así que la fórmula pasó de
      `max(fecha, invoice_date)` a `min(max(fecha, invoice_date), hoy)`
      en los tres sitios (`account_move.py` x2, `batch_retentions_wizard.py`)
- [x] 3b.6 Misma auditoría encontró que `test_13b` (3b.2) no probaba nada
      distinto de `test_13`: `_create_iva_retention()` hardcodea
      `type="in_invoice"`, así que el `move_type` de venta de la factura no
      cambiaba el camino ejercitado. Corregido agregando
      `retention.type = "out_invoice"` explícito (mismo patrón que
      `test_05`)
- [x] 3b.7 Misma auditoría refutó 2 afirmaciones falsas en la nota de
      aclaración de 3b.3 (en `proposal.md`/`spec.md`): la guarda de
      "no crear retención para factura cancelada" vive en
      `account_retention.py` y solo aplica a retenciones de terceros (no
      en `account_move.py` ni de forma general); y una retención `cancel`
      sí admite `write` vía `action_draft`, no es inmutable. Ambas
      corregidas — la conclusión (el filtro por `state` es un no-op) no
      dependía de ninguna de las dos y se mantiene

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta
- [x] 4.2 Corregido el escenario multi-factura del spec (era aritméticamente
      falso: comparaba contra la fecha más antigua en vez de la más
      reciente)
- [x] 4.3 Documentado en `proposal.md` el constraint a nivel de línea y la
      exclusión explícita del wizard de registro de pagos (código muerto)
- [x] 4.4 Corregido `proposal.md`: ya no afirma que `action_post()`
      "reemplazaba un chequeo inline con `min()`" (ese chequeo nunca existió
      en `HEAD`, fue un borrador intermedio de esta misma rama) — ahora
      describe la validación como nueva, no como reemplazo
- [x] 4.5 Corregido el escenario de cron en `spec.md`/`proposal.md`: decían
      que el flujo automatizado "no interrumpe el resto del lote"; el
      código sí lo interrumpe (`return False` dentro del `for retention in
      self`, igual que la validación de monto preexistente) — el texto
      ahora describe el comportamiento real en vez del deseado
- [x] 4.6 Agregado a `spec.md`/`proposal.md` el escenario "fuera de
      alcance": los constraints nuevos no vigilan que se mueva
      `invoice_date_display` de la factura *después* de emitida la
      retención (solo vigilan el lado de la retención)
- [ ] 4.7 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)

## 5. Proceso (pendiente, no técnico)

- [x] 5.1 Rama `maint-19.0-fix-ti-14984-retention-accounting-date` creada
      desde `maintenance-19.0`, con commit `54480a486` (10 archivos:
      6 modificados + el directorio `openspec/changes/retention-accounting-date-validation/`
      completo, antes `untracked`)
- [ ] 5.2 Abrir el PR contra `maintenance-19.0` para que el review tenga
      dónde registrarse (no ejecutado: requiere confirmación explícita
      antes de hacer push)
