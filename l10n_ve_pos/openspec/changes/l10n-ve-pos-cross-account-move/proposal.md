# Cruce automático transitoria → banco para pagos en moneda extranjera (l10n_ve_pos)

## Why

Los métodos de pago con `is_foreign_currency=True` se contabilizan hoy contra su
`outstanding_account_id` (cuenta transitoria) como cualquier método de pago
nativo de Odoo. La intención de negocio original era generar además un
asiento manual que vacíe esa transitoria y traslade el saldo a la cuenta real
del diario de Banco (`cross_journal`), dejando trazabilidad en un diario tipo
`general` (`cross_account_journal`).

Ese código (`_validate_cross_move`, `_line_vals_move_cross_incoming/outgoing`,
`_create_cross_move`, `_create_cross_move_payment`,
`_line_vals_move_cross_payment_incoming` en
`src/odoo-venezuela/l10n_ve_pos/models/pos_session.py`) está completamente
comentado desde antes de la migración a Odoo 19 — verificado por diff: el
mismo bloque, intacto, existe sin tocar en
`src/custom/19-homologacion-jul-2026-pos/odoo-venezuela/l10n_ve_pos/models/pos_session.py`.
Sin embargo los tres campos que lo configuran
(`cross_account_journal`, `cross_journal`, `apply_one_cross_move` en
`pos_payment_method.py`) siguen vivos, expuestos en el formulario de método
de pago (`views/pos_payment_method.xml`) y cargados al POS — un admin puede
configurarlos creyendo que activan el cruce, y hoy no hacen nada.

Al intentar resucitar el código se encontraron tres bugs que impiden
descomentarlo tal cual:

1. **Polaridad invertida** en `_validate_cross_move`: la condición dispara el
   cruce cuando `apply_one_cross_move` es `False` (el default), lo opuesto de
   lo que sugiere el nombre del campo.
2. **Campo renombrado en Odoo 19**: la ruta combine
   (`_create_cross_move_payment` / `_line_vals_move_cross_payment_incoming`)
   usa `move.move_id.payment_id`, renombrado a `origin_payment_id` en Odoo 19
   (mismo problema ya resuelto en este archivo para
   `_create_split_account_payment`).
3. **Id de moneda hardcodeado**: 6 comparaciones `currency == 3` /
   `self.env.company.currency_id.id == 3`, asumiendo que VEF siempre tiene
   `id=3` — no garantizado fuera de la base de datos original de desarrollo.

## What Changes

- **Ruta split** (pagos con `split_transactions=True`): se descomenta y
  corrige `_validate_cross_move` (fix de polaridad + guard `pay_later`),
  `_line_vals_move_cross_incoming`/`_line_vals_move_cross_outgoing` (fix del
  id de moneda hardcodeado) y `_create_cross_move` (cuerpo, queda en
  `state="draft"`). Se engancha `self._validate_cross_move()` en
  `action_pos_session_close`, justo después de `super()`.
- **Ruta combine** (pagos con `split_transactions=False`): se descomenta y
  corrige `_create_combine_account_payment` (fix `origin_payment_id` + guard
  defensivo), `_create_cross_move_payment` y
  `_line_vals_move_cross_payment_incoming` (fix `origin_payment_id` x4 + fix
  id de moneda x2). No requiere un punto de enganche nuevo: la llamada ya
  vive dentro de `_create_combine_account_payment`, invocada por el pipeline
  nativo de cierre de sesión.
- **Decisión de negocio confirmada**: el asiento de cruce se crea en
  `state="draft"` y NO se postea automáticamente — contabilidad lo revisa y
  valida a mano.
- Tests nuevos en `tests/test_pos_session_cross_account_move.py` cubriendo
  ambas rutas, signos, y los casos donde el cruce no debe aplicar.

## Impact

- **Capability**: `pos-cross-account-move` (nueva).
- **Módulo**: `l10n_ve_pos` (solo `models/pos_session.py` + tests nuevos). Sin
  cambios de vista ni de modelo — los campos de configuración ya existen.
- **Riesgo de despliegue**: al corregir la polaridad, cualquier
  `pos.payment.method` que ya tenga `apply_one_cross_move=True` con ambos
  journals configurados en producción pasará de "nunca genera cruce" a
  "genera cruce en cada cierre de sesión". Auditar antes de desplegar (ver
  `design.md`).
