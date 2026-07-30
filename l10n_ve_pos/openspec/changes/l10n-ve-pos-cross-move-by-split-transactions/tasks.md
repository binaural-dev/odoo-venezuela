# Tasks

## 1. Un solo disparador

- [x] 1.1 Reescribir `_validate_cross_move` para agrupar por método de pago y
      ramificar según `split_transactions` (N asientos vs. 1 neteado)
- [x] 1.2 Quitar la llamada a `_create_cross_move_payment` de
      `_create_combine_account_payment` (conserva solo el contrato de
      `foreign_rate`/`foreign_debit`/`foreign_credit`)
- [x] 1.3 Eliminar `_create_cross_move_payment` y
      `_line_vals_move_cross_payment_incoming` (código muerto)
- [x] 1.4 Nuevo `_create_cross_move_for`: elige rama entrante/saliente por el
      signo del importe, habilitando la rama saliente en combine

## 2. Elegibilidad por `is_foreign_currency`

- [x] 2.1 Nuevo helper `_is_cross_move_eligible(payment_method)`
- [x] 2.2 Eliminar el campo `apply_one_cross_move` de `pos_payment_method.py`
      (definición + `_load_pos_data_fields`)
- [x] 2.3 Eliminarlo de `views/pos_payment_method.xml`; los dos diarios de
      cruce pasan a `invisible="not is_foreign_currency"`
- [x] 2.4 Eliminar sus dos entradas de `i18n/es_VE.po` (`field_description` y
      `help`)

## 3. Cuenta transitoria por tipo de método

- [x] 3.1 `_get_cross_transitory_account` ramifica por `payment_method.type`:
      `cash` → `journal_id.default_account_id`; `bank` →
      `outstanding_account_id or journal_id.default_account_id`; fallback final
      a la POS receivable de la compañía

## 4. Líneas parametrizadas

- [x] 4.1 `_line_vals_move_cross_incoming`/`_outgoing` reciben
      `(payment_method, amount, foreign_amount, foreign_rate, partner)` en vez
      de un `pos.payment`
- [x] 4.2 `_create_cross_move` recibe `(payment_method, line_vals,
      foreign_rate, date, ref, partner)` — los dos últimos añadidos en la
      sección 6; el `foreign_currency_id` del asiento pasa a salir
      de `self.foreign_currency_id` (la del config de la sesión) en vez de la
      del pago

## 5. Tests

- [x] 5.1 `_configure_cross` sin `apply_one_cross_move`
- [x] 5.2 Split → un asiento por pago (3 pagos, 3 asientos)
- [x] 5.3 Combine → un solo asiento neteado (3 pagos, 1 asiento) — el caso que
      reproduce el bug reportado
- [x] 5.4 Combine + split conviviendo en la misma sesión
- [x] 5.5 Split saliente (reembolso)
- [x] 5.6 Combine con neto negativo → rama saliente
- [x] 5.7 Combine con neto cero → no crea nada
- [x] 5.8 Método bank → vacía `outstanding_account_id`
- [x] 5.9 Método cash → vacía la cuenta de su diario, y **no** la POS receivable
- [x] 5.10 `is_foreign_currency=False` → no crea nada
- [x] 5.11 Falta un diario de cruce → no crea nada, no rompe
- [x] 5.12 `pay_later` no elegible (aunque el fallback resuelva cuenta)
- [x] 5.13 Regresiones conservadas: secuencia del diario en `name` al postear,
      y moneda foránea sin `id=3`
- [x] 5.14 **Correr la suite completa de `l10n_ve_pos`** en BD desechable y
      confirmar sin regresiones. Corrida en `test_l10n_ve_pos_split_cross`
      (borrada al terminar) con
      `-i l10n_ve_pos --test-enable --test-tags /l10n_ve_pos --workers=0`:
      **0 failed** (ningún assert roto), 12/13 de los tests nuevos de cruce en
      verde, 3 skips intencionales preexistentes (Slices C2.3/C2.4/C2.5).
      El módulo carga limpio: ningún error de vista ni rastro de
      `apply_one_cross_move` en el log.

      3 tests cortan por un **bug preexistente ajeno a este change**:
      `binaural_stock_accountant/models/account_move.py:85` hace
      `move.invoice_reception_date` en su `action_post()`, pero su manifest
      declara `depends: ["account", "stock", "l10n_ve_stock"]` — el campo lo
      define `binaural_commissions`, que no está en esa cadena. En un entorno
      sin `binaural_commissions` instalado, **cualquier** `action_post()`
      revienta con `AttributeError`. Ya estaba documentado en
      `binaural_pos_close/tests/test_pos_close_migration.py:473`.

      Dos de los tres (`test_create_bank_payment_moves_...`,
      `test_create_split_account_payment_...`) viven en
      `test_pos_session_accounting_move_creation.py`, que este change no toca
      — confirma que la causa es ambiental. El tercero,
      `test_cross_move_name_takes_journal_sequence_on_post`, es el único de
      cruce afectado y es el único que llama `action_post()`; su lógica no
      cambió en este change.

## 6. Trazabilidad de los borradores (detectado verificando en producción)

Con "Identificar cliente" activo, la sesión 65 de la BD `pos` generó
correctamente los dos asientos de cruce, pero salían idénticos en la lista
(`/`, misma fecha, mismo importe, mismo `ref` genérico, columna "Socio" vacía
porque el partner iba sólo en las líneas) — se leían como uno solo.

- [x] 6.1 Nuevo `_cross_move_ref(payment=None)`: con pago devuelve
      `"<base> - <orden> - <payment.name o #id>"`; sin pago, `"<base> - <sesión>"`
- [x] 6.2 `_create_cross_move_for` / `_create_cross_move` reciben `ref` y
      `partner`; el `account.move` se crea con ambos
- [x] 6.3 Nuevo `_cross_move_header_partner(partner)`: omite el partner de la
      cabecera si es de otra compañía. `account.move.partner_id` es
      `check_company=True`, `account.move.line.partner_id` no, y
      `pos.order.partner_id` no valida compañía — propagarlo tumbaría el
      cierre completo con `UserError`
- [x] 6.4 Tests: `test_split_refs_identify_each_payment_of_the_same_order`
      (dos pagos del mismo método en la misma orden, mismo importe),
      `test_split_move_header_carries_the_partner`,
      `test_combine_move_ref_names_the_session_and_has_no_partner`,
      `test_partner_from_another_company_does_not_block_the_cross_move`
- [x] 6.5 Suite re-corrida: `0 failed` de 49 tests, los 4 tests nuevos en
      verde, sin fallos nuevos más allá de los 3 preexistentes de
      `binaural_stock_accountant` (ver 5.14)

## 7. Verificación manual

- [ ] 7.1 Probar en navegador el caso del reporte: método bank combinado con
      varios pagos en una sesión → **un** asiento; el mismo método con
      "Identificar cliente" activo → uno por pago
- [ ] 7.2 Probar un método `cash` en divisa ("Efectivo $") y confirmar que la
      pata transitoria cae en la cuenta del diario de caja
- [ ] 7.3 `-u l10n_ve_pos` para que el registro sincronice la baja del campo
      `apply_one_cross_move` y la vista actualizada

## 8. Despliegue

- [ ] 8.1 Auditar en producción los métodos que pasan a cruzar:
      `search([("is_foreign_currency","=",True),("cross_account_journal","!=",False),("cross_journal","!=",False)])`
- [ ] 8.2 Revisar con contabilidad los asientos de cruce ya generados sobre
      métodos `cash` (cruzaron contra la POS receivable en vez de la cuenta del
      diario de caja)

## 9. OpenSpec

- [x] 9.1 `openspec validate --changes`
- [x] 9.2 Nota en el `design.md` de `l10n-ve-pos-cross-account-move` marcándolo
      superado por este change
- [x] 9.3 Ambos changes (`l10n-ve-pos-cross-account-move` y este) movidos del
      `openspec/` de la raíz de `docker-odoov19` — que está **untracked**, no
      versiona nada — al `openspec/` del propio módulo
      (`src/odoo-venezuela/l10n_ve_pos/openspec/changes/`), que es el que sí
      vive en el repo `odoo-venezuela` y la convención vigente (ver commit
      `3d0683f61`)
- [x] 9.4 Ejemplo contable con números en `design.md`: los dos asientos que el
      nativo genera para un pago en efectivo, el descuadre que producía el
      código viejo, y la query para detectar asientos ya afectados
