# Fix: el cruce exige sus cuentas antes de abrir la sesión (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H6 de la prueba e2e del PdV multimoneda (01-oct-2026).
En la caja VES, abrir la sesión con fondo en el cajón foráneo ($) asienta la
diferencia de apertura (`binaural_pos_close._post_foreign_statement_difference`)
y su cruce con `use_suspense=False`: la pata del diario real sale de la cuenta
de las líneas de pago del `cross_journal` (`_get_cross_real_account`). Si esas
líneas no tienen cuenta, la línea se crea con `account_id` NULL y Postgres la
rechaza (`account_move_line_check_accountable_required_fields`): "Falta la
cuenta requerida…", el popup de apertura queda trabado y la caja no se puede
abrir con fondo en $.

No es una configuración rara: `l10n_ve_accountant`
(`_check_payment_method_line_accounts`) solo exige esa cuenta en los diarios de
**banco**, y el core crea los diarios de **efectivo** con sus líneas de pago sin
cuenta. Un diario de efectivo usado como `cross_journal` llega al error sin que
nadie lo edite. `_is_cross_move_eligible` ya reconocía este hueco en la rama
`use_suspense=False` y lo dejaba fuera de alcance. Afecta también a la
diferencia del cierre y al cruce de las ventas con banco.

Decisión (05-oct): avisar antes, como hace el core con
`_check_profit_loss_cash_journal`, en vez de caer a otra cuenta en silencio.

## What Changes

- **`models/pos_config.py`**: `_check_before_creating_new_session` llama a
  `_check_cross_move_accounts`, que recorre los métodos elegibles para el cruce
  en una sesión virtual de la caja (`pos.session.new`, para respetar las
  extensiones por sesión, p. ej. `binaural_pos_multicurrency`) y lanza un
  `ValidationError` con cada cuenta que falta. La sesión no se crea.
- **`models/pos_session.py`**:
  - `_get_cross_move_missing_accounts(payment_method)`: lo que el cruce de las
    ventas usa, por tipo de método (decisión 05-oct: cada módulo exige lo que
    usa): banco → `_get_cross_move_missing_payment_accounts` (líneas de pago
    entrantes y salientes del `cross_journal`); efectivo →
    `_get_cross_move_missing_suspense_accounts` (las dos transitorias).
    `binaural_pos_close` (integra) lo extiende para el método del cajón
    foráneo, cuya diferencia de apertura/cierre usa las líneas de pago.
  - `_create_cross_move_for`: si alguna pata sale sin cuenta, `UserError` con
    la lista, en vez del `CheckViolation` (sesión creada antes de vaciar la
    cuenta).
  - `_cross_move_suspense_accounts_ready(payment_method)`: si falta una
    transitoria, el cruce `use_suspense=True` se sigue omitiendo, como fijó el
    ticket 15219 (el cierre no se cae por esto), pero deja un aviso en el log.
  - `_validate_cross_move` evalúa la elegibilidad por método y no por pago:
    mismo resultado, un aviso por método.
- **`i18n/es_VE.po`**: mensajes nuevos.
- Textos que decían "se omite en silencio" actualizados: change
  `l10n-ve-pos-cross-move-by-split-transactions`, change
  `cruce-venta-efectivo-entre-transitorias` (raíz, spec y proposal) y la spec
  consolidada `openspec/specs/l10n_ve_pos/spec.md`.

## Impact

- Apertura: una caja con un método con cruce incompleto no abre hasta
  configurar la cuenta (mensaje con método, diario y cuenta). Antes: o
  reventaba (líneas de pago del cajón foráneo) o abría y omitía el cruce de las
  ventas en efectivo en silencio (transitorias). Al desplegar, las cajas con
  métodos de efectivo con cruce sin transitorias dejarán de abrir hasta
  configurarlas.
- Asientos: los mismos que con la cuenta configurada; no hay plan B que cambie
  la cuenta destino.
- Sin migración ni cambio de vistas. Va en la misma rama que H1
  (`l10n-ve-pos-refund-foreign-sign`), con su versión 1.20.
- Orden de merge: este cambio antes que el PR #2896 de integra-addons
  (`binaural_pos_close` y `binaural_pos_multicurrency` llaman a los helpers
  nuevos).
