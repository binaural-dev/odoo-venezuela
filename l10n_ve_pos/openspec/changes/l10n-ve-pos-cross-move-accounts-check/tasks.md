# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_session_cross_account_move.py`: chequeo de apertura
      (banco: línea de pago entrante/saliente, solo la vaciada en el mensaje;
      efectivo: transitorias; efectivo sin líneas de pago no se bloquea;
      enganche en `_check_before_creating_new_session`) y red de seguridad en
      `_create_cross_move_for` (entrante y saliente)
- [x] 1.2 Los dos tests del 15219 (transitoria del diario o del
      `cross_journal` vacía) afirman además el aviso en el log
- [x] 1.3 integra-addons (PR #2896): `binaural_pos_close`
      (`test_open_check_requires_payment_accounts_for_foreign_drawer`) y
      `binaural_pos_multicurrency` (el `assertKnownBug` de H6 pasa a
      aserciones, cajas bien configuradas abren, elegibilidad de cajas en otra
      moneda con las dos transitorias)

## 2. Corrección

- [x] 2.1 `pos_config.py`: `_check_cross_move_accounts` desde
      `_check_before_creating_new_session` (sesión virtual de la caja)
- [x] 2.2 `pos_session.py`: cuentas que faltan por tipo de método,
      `_cross_move_suspense_accounts_ready` y `UserError` en
      `_create_cross_move_for`
- [x] 2.3 `pos_session.py`: elegibilidad por método en `_validate_cross_move`
- [x] 2.4 `i18n/es_VE.po`
- [x] 2.5 Textos de otros changes y de la spec consolidada

## 3. Verificación

- [x] 3.1 Rojo antes del fix: `./odoo test -i posv19 -m l10n_ve_pos -d <bd>
      --tags "/l10n_ve_pos:TestPosSessionCrossAccountMove"` → 3 failed, 4
      errors (`AttributeError`, `CheckViolation`, sin aviso); efectivo sin
      líneas de pago bloqueado con la primera versión. Verde: 29/29.
      `binaural_pos_close` 47/47 (sin su extensión: `ValidationError not
      raised`)
- [x] 3.2 Batería: `l10n_ve_pos` aparte 91/91; capa A de `binaural_pos_multicurrency` 62/66 (los 3 tours por el dbfilter de `./odoo test` y `test_refund_keeps_original_rate` por `l10n_ve_stock`, previos); tours con `--db-filter` 3/3 (pasan por `open_ui`: el chequeo no bloquea las cajas de prueba); hoot 8/8 propios; `-u l10n_ve_pos,binaural_pos_close,binaural_pos_multicurrency` en posv19
- [x] 3.3 Navegador en posv19 (06-oct, Caja VES, PVU sin cuenta en sus líneas
      de pago): sin sesión, "Abrir caja registradora" del tablero muestra el
      error de validación con el método, el diario y las dos cuentas, y no se
      crea la sesión (desde `/pos/ui` el core lo muestra como página 422); con
      la sesión 479 ya creada y la cuenta vaciada, abrir con 227,80 $ (+10 $)
      muestra "Operación no válida" con las cuentas que faltan, sin asientos y
      la sesión sigue en `opening_control`; con la cuenta restaurada abre:
      PVT/2026/0010 debe 1111302 / haber 9990001 8.033,40 Bs (10 $) y cruce
      XVES en borrador debe 1111303 / haber 1111302 8.033,40 Bs (10 $)

## 4. Archivo

- [ ] 4.1 Archivar antes `l10n-ve-pos-cross-move-by-split-transactions`: este
      change modifica el mismo requisito ("Elegibilidad del cruce por
      `is_foreign_currency`") sobre su texto
