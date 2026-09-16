# Tasks

## 1. Diagnóstico

- [x] 1.1 Localizado el origen real del mensaje: core `account`
      (`account_move_send.py:340`, es_419.po), no un módulo custom
- [x] 1.2 Trazada la cadena `_generate_pos_order_invoice()` → `_post(soft=True)`
      → `_generate_and_send()` → `_check_move_constraints()`
- [x] 1.3 Descartados los `integra-addons` instalados en `pos2`: el único que
      toca fechas de factura es `binaural_stock_accountant` y solo
      `invoice_date_due` + un `action_post()` que no está en esta ruta
      (core llama `_post()` directo)
- [x] 1.4 Descartadas fechas de bloqueo contable (`fiscalyear_lock_date`,
      `tax_lock_date`, `sale_lock_date`, `hard_lock_date` vacías en ambas
      compañías de `pos2`)
- [x] 1.5 Confirmado el desfase: contenedor `proj` en UTC, usuarios en
      `America/Caracas`; fallos a las 01:22 UTC (21:22 VE), últimas
      facturas OK a las 20:34 UTC (16:34 VE)
- [x] 1.6 Causa raíz: `l10n_ve_accountant._get_accounting_date_source()`
      hace que `move.date` venga de `invoice_date_display`, cuyo
      `default=fields.Date.today` es UTC, mientras `_post()` compara contra
      `fields.Date.context_today()` (tz del usuario)

## 2. Fix

- [x] 2.1 `l10n_ve_accountant/models/account_move.py:21`
      `invoice_date_display`: `default=fields.Date.context_today`
- [x] 2.2 `l10n_ve_accountant/models/account_move.py:145-148`
      `_onchange_move_type`: `fields.Date.context_today(self)`
- [x] 2.3 `l10n_ve_invoice/models/account_move.py:19-23` `invoice_date`:
      `default=fields.Date.context_today`
- [x] 2.4 `l10n_ve_invoice/models/account_move.py:112-115`
      `_onchange_move_type`: `fields.Date.context_today(self)`
- [x] 2.5 `l10n_ve_iot_mf/models/account_move.py:141, 247, 346`: la
      validación de impresión fiscal compara contra
      `fields.Date.context_today(self)`

## 3. Verificación

- [x] 3.1 Confirmado que no quedaron asientos colgados en `pos2` (rollback de
      `sync_from_ui`; sin `auto_post <> 'no'` ni facturas de venta en
      borrador) → no hace falta data-fix
- [ ] 3.2 Reiniciar Odoo y repetir la validación de una orden del PdV en la
      franja 20:00–23:59 VE (usuario, en navegador)
- [ ] 3.3 Confirmar que la factura resultante queda `posted` con
      `invoice_date = invoice_date_display = date` = fecha VE
- [ ] 3.4 Revisar otras BD productivas por facturas en borrador con
      `auto_post='at_date'` y fecha contable un día adelantada
- [x] 3.5 Confirmado que la separación `invoice_date` (tasa) /
      `invoice_date_display` (fiscal + fuente de `date`) no se altera: solo
      cambian `default`s, no `_get_accounting_date_source()` ni
      `_onchange_invoice_date_display()`
- [x] 3.6 Confirmado que en el PdV la fecha de tasa no cambia (core pasa
      `invoice_date` explícito, el `default` nunca aplicaba en esa ruta)
- [ ] 3.7 Probar la impresión fiscal en una BD con `l10n_ve_iot_mf`
      instalado (uninstalled en `pos`/`pos2`, no verificable aquí)
- [ ] 3.8 Decidir si la desactivación del cron
      `ir_cron_auto_post_draft_entry` en `pos` y `pos2` fue deliberada
      (`active = f` en ambas; en core viene activo)

## 5. Manifests

- [x] 5.1 `l10n_ve_accountant` 19.0.1.0.2 → 19.0.1.0.3
- [x] 5.2 `l10n_ve_invoice` 19.0.1.0.3 → 19.0.1.0.4
- [x] 5.3 `l10n_ve_iot_mf` 19.0.1.0.1 → 19.0.1.0.2

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta
- [x] 4.2 `openspec validate --changes`
