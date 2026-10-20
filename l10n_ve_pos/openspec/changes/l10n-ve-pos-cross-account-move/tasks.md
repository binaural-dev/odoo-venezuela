# Tasks

## 1. Ruta split

- [x] 1.1 Fix polaridad en `_validate_cross_move` + guard `pay_later` + descomentar
- [x] 1.2 Descomentar `_line_vals_move_cross_incoming` (fix id de moneda hardcodeado)
- [x] 1.3 Descomentar `_line_vals_move_cross_outgoing` (fix id de moneda hardcodeado)
- [x] 1.4 Descomentar cuerpo de `_create_cross_move` (queda en `draft`, sin `action_post()`)
- [x] 1.5 Enganchar `self._validate_cross_move()` en `action_pos_session_close`

## 2. Ruta combine

- [x] 2.1 Descomentar `_create_combine_account_payment` (fix `payment_id` → `origin_payment_id` + guard `if account_payment:`)
- [x] 2.2 Descomentar `_create_cross_move_payment` (fix `payment_id` → `origin_payment_id`)
- [x] 2.3 Descomentar `_line_vals_move_cross_payment_incoming` (fix `payment_id` → `origin_payment_id` x4 + fix id de moneda x2)

## 3. Tests

- [x] 3.1 Fixture: journals/flags de cruce en `split_bank_method`/`combined_bank_method` (reutilizando `TestPosSessionAccountingBase`)
- [x] 3.2 Test pago entrante split
- [x] 3.3 Test pago saliente/reembolso split
- [x] 3.4 Test pago combine entrante
- [x] 3.5 Test sin `apply_one_cross_move` (no crea nada)
- [x] 3.6 Test con un solo journal configurado, ambas combinaciones (no crea nada, no rompe)
- [x] 3.7 Test con moneda foránea sin `id=3` (expone el bug del magic number si no está corregido)

Resultado: 6/6 tests nuevos en verde + 38/38 en toda la suite `l10n_ve_pos`
(sin regresiones), corrido en BD desechable `test_l10n_ve_pos_cross_move`
contra `src/odoo-venezuela/l10n_ve_pos`.

## 4. Verificación en producción (BD `pos`, contenedor `proj`)

- [x] 4.1 Confirmado que `src/custom/19-homologacion-jul-2026-pos` NO hace
      shadowing de `l10n_ve_pos` (módulo anidado dos niveles de más, Odoo no
      lo descubre) — ver nota en `design.md`. No requiere acción.
- [x] 4.2 Configurado método de pago real "Zelle" (split, `is_foreign_currency`)
      con ambos diarios de cruce + `apply_one_cross_move=True`.
- [x] 4.3 Dos transacciones reales de venta con Zelle → 2 asientos de cruce
      en borrador, cuentas y montos correctos, verificado por query directa
      en `proj_db`/BD `pos`. Posteados manualmente por el usuario; saldo de
      la cuenta real "Zelle" quedó exactamente en la suma de ambos pagos.
- [x] 4.4 Probada la rama saliente (reembolso) con Zelle en el mismo entorno
      — confirmado por el usuario: el cruce se generó correctamente.
- [ ] 4.5 **Test multicompañía** (pendiente, confirmado por el usuario que
      falta): validar el flujo completo (config + cierre de sesión + cruce)
      en una segunda compañía dentro de la misma BD, y auditar
      `pos.payment.method` en TODAS las compañías/instalaciones existentes
      con `apply_one_cross_move=True` + ambos journals ya configurados antes
      de este fix (comportamiento pasa de "nunca se ejecuta" a "se
      ejecuta").

## 5. OpenSpec

- [x] 5.1 `openspec validate --changes`

## 6. UX: claridad del campo `apply_one_cross_move`

- [x] 6.1 Renombrar `string` a "Enable Automatic Cross-Account Clearing" +
      traducción es_VE "Habilitar cruce automático de cuenta transitoria"
- [x] 6.2 Agregar `help` en inglés describiendo el efecto (asiento por pago
      vs. por sesión según split/combine, diario donde queda, y que nace en
      borrador sin afectar saldos hasta postearse)
- [x] 6.3 Corrido `-u l10n_ve_pos` en la BD `pos`, confirmado por el usuario
      que label/help ya se ven actualizados en la UI

## 7. Bug 4: fallback de cuenta transitoria para métodos `cash` (encontrado en producción)

Al probar en producción con un método de pago real en efectivo ("Efectivo
$", `is_foreign_currency=True`, `apply_one_cross_move=True`), el cierre de
sesión reventaba con un error SQL crudo
(`account_move_line_check_accountable_required_fields`) en vez de crear el
cruce o saltarlo con gracia. Causa: `outstanding_account_id` es
`invisible="type != 'bank'"` en la vista nativa — métodos cash nunca lo
tienen, por diseño de Odoo (el dinero va directo al diario de caja, sin
cuenta transitoria separada).

- [x] 7.1 Nuevo helper `_get_cross_transitory_account(payment_method)`:
      `payment_method.outstanding_account_id or
      self.company_id.account_default_pos_receivable_account_id` — mismo
      patrón de fallback que el nativo `_get_receivable_account`
- [x] 7.2 Usado en `_line_vals_move_cross_incoming`, `_outgoing`,
      `_payment_incoming`, y en los guards de `_validate_cross_move` /
      `_create_combine_account_payment`
- [x] 7.3 Nuevo test
      `test_cross_move_cash_method_falls_back_to_default_pos_receivable_account`
      — reproduce el caso real (método cash sin `outstanding_account_id`),
      confirma que el cruce se crea usando
      `account_default_pos_receivable_account_id`
- [x] 7.4 Suite completa re-corrida: 39/39 verde (7 tests propios de
      cross-account-move + 32 del resto de `l10n_ve_pos`), sin regresiones

## 8. Bug 5: `name` bloqueaba la secuencia del diario al postear (reportado por el usuario)

El usuario confirmó varios asientos de cruce reales y notó que, al postear,
el "Número" del asiento se quedaba fijo en el texto "PoS Payment Method
Adjustment" en vez de tomar la secuencia del diario `cross_account_journal`
(ej. `MISC/2026/00001`). Se aclaró con el usuario que la secuencia
correcta es la del diario donde vive el asiento (Miscelánea/
`cross_account_journal`), no la del diario real (`cross_journal`) — mover
el asiento al diario real habría sido un cambio de diseño mayor, descartado.

- [x] 8.1 `_create_cross_move`: quitar `"name": _("PoS Payment Method
      Adjustment")` del `create()`, mover el texto a `"ref"`
- [x] 8.2 `_create_cross_move_payment`: mismo fix
- [x] 8.3 Nuevo test `test_cross_move_name_takes_journal_sequence_on_post`
      — confirma que en `draft` el `name` queda en `/` (placeholder nativo)
      y `ref` lleva el texto descriptivo; tras `action_post()`, `name`
      recibe una secuencia real (no el literal viejo) y `ref` se preserva
- [x] 8.4 Suite completa re-corrida: 40/40 verde (8 tests propios de
      cross-account-move + 32 del resto de `l10n_ve_pos`), sin regresiones
