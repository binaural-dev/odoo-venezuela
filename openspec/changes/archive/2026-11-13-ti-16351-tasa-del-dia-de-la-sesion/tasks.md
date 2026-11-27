## 0. Decisiones

- [x] 0.1 2026-11-12: la sesión trabaja siempre con la tasa de su apertura; una sesión del día 3 no puede arrancar
      con la tasa del día 2 (Jesús Cegarra)
- [x] 0.2 2026-11-12: una sesión que pasa la medianoche respeta la tasa de su apertura y solo se avisa
- [x] 0.3 2026-11-12: sin tasa del día la caja no abre
- [x] 0.4 2026-11-12: la carga de monedas sin el filtro por `write_date` va en este ticket, sin esperar el
      PR odoo-venezuela#1569
- [x] 0.5 2026-11-12: se fija el día de la tasa, no su valor: una corrección del mismo día entra al recargar
      (mantiene el comportamiento de `binaural_pos_multicurrency` y sus pruebas)
- [x] 0.6 2026-11-12 (code review): se corrigen B1, B2, I1a, I2, I3, I4, M1, M2, M4, M7, M8 y M10; quedan como
      limitaciones la medianoche entre chequeo y apertura (M3), el usuario sin zona horaria (M5), el reloj del
      navegador (M6), la sincronización sin validar la tasa (M9) y el kiosko abierto varios días (I1b)

## 1. Implementación

- [x] 1.1 `pos.session.foreign_rate_date` y `_set_opening_control_data`: guarda el día; sin tasa, `UserError`
- [x] 1.2 `pos.config._compute_rate`: tasa del día de la sesión activa; la sesión invalida la caché al guardar
      el día (`current_session_id` no se puede usar en `@api.depends`)
- [x] 1.3 `pos.load.mixin._last_server_date_to_load`: `res.currency` sin filtro por `write_date`. Entró a 19.0
      antes con la tarea 86066 (#1569, ver 1.13); en este cambio solo queda el comentario con el motivo del ticket
- [x] 1.4 `res.currency._load_pos_data_read`: `rate` del día de la sesión (`pos.session._get_pos_currency_rates`)
- [x] 1.5 `pos.session.check_opening_rate` + parche de `OpeningControlPopup.confirm` y `PosStore.checkOpeningRate`
- [x] 1.6 Aviso de sesión de un día anterior (`PosStore.afterProcessServerData`, `pay`, `validateOrderFast`)
- [x] 1.7 Traducciones es_VE y versión 19.0.1.31.0
- [x] 1.8 Helpers `pos.session._get_rate_date()` y `pos.config._get_pos_rate_date()`; `_compute_rate` con la
      compañía de la caja
- [x] 1.9 Kiosko: `res.currency._load_pos_self_data_read` con la tasa del día de la sesión (`l10n_ve_pos_self_order`)
- [x] 1.10 Popup: gancho `_beforeOpeningSession`, lectura de `foreign_rate_date` después de abrir, apertura y
      recarga con órdenes pagadas sin enviar, sesión borrada delegada al core
- [x] 1.11 `check_opening_rate` ignora datos mal formados del navegador
- [x] 1.12 Día de la tasa en el formulario de la sesión
- [x] 1.13 2026-11-13, tras el merge de la tarea 86066: `tender_currency_rates` con el día de la sesión, el chequeo
      de apertura compara las tasas de cobro, y la carga de monedas sin `write_date` une los motivos de los dos cambios

## 2. Pruebas

- [x] 2.1 `tests/test_pos_session_opening_rate.py` (12): día guardado al abrir, apertura a las 8:30 pm de Caracas,
      sesión que pasa la medianoche, sesión nueva del día siguiente, corrección del mismo día, apertura sin tasa,
      caja cargada el día anterior, moneda con tasa vieja, monedas en cada carga limitada, helpers del día,
      asiento del cierre después de medianoche, datos mal formados
- [x] 2.2 `l10n_ve_pos_self_order/tests/test_kiosk_session_rate.py` (2): kiosko sin tasa no abre; monedas del
      kiosko con la tasa del día de la sesión
- [x] 2.3 Suites completas en base nueva con los dos módulos, como el CI:
      `odoo -d <base nueva> -i l10n_ve_pos,l10n_ve_pos_self_order --test-tags /l10n_ve_pos,/l10n_ve_pos_self_order --stop-after-init`
      (sobre 19.0 con la tarea 86066: 270 + 105, sin fallos; `l10n_ve_pos_igtf` en otra base: 12, sin fallos)
- [x] 2.4 Mutación (rehecha el 2026-11-25 sobre 19.0 + esta rama, suites completas de los dos módulos): con
      `context_today` en `_compute_rate` fallan 5 tests; sin `_apply_pos_session_rates` en `_load_pos_data_read`
      falla `test_session_keeps_its_opening_rate_after_midnight`; sin el override del kiosko falla su test (13/11).
      La carga de monedas sin `write_date` no se muta aquí: es de la tarea 86066 (ver 1.3)
- [x] 2.5 `static/tests/unit/session_opening_rate.test.js` (Hoot, 12)
- [x] 2.6 PdV (`pos_test_16351`, copia de `pos_consultor`): apertura sin tasa ("Sin tasa del día", y el servidor
      también bloquea); tasa cambiada después de cargar la caja ("Tasa desactualizada", recarga y abre con la tasa
      nueva); sesión de un día anterior (cobra con su tasa y avisa al cargar y al cobrar)
- [x] 2.7 `tests/test_pos_tender_currency.py` (2 nuevos): tasas de cobro de una sesión de ayer; tasa de cobro vieja
      en el navegador
- [x] 2.8 integra-addons (PR complementario): `binaural_pos_multicurrency` y `binaural_pos_close` con esta rama

## 3. Cierre

- [x] 3.1 Revisión con code-reviewer
- [x] 3.2 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md`

## 4. Code review de SaulOrte (2026-11-19)

- [x] 4.1 Sin conexión la caja no abre: `checkOpeningRate` devuelve "blocked" con el aviso del core ante
      `ConnectionLostError` (antes "ok"); escenario "Apertura sin conexión" en la spec
- [x] 4.2 Registro de `_beforeOpeningSession` antes de `set_opening_control`: declarado como limitación (no se
      mueve: `binaural_pos_close` solo registra los cajones en `opening_control`)
- [x] 4.3 Descripción del PR y OpenSpec: la carga completa de monedas es de la tarea 86066; mutación rehecha (2.4)
- [x] 4.4 Evidencia (2026-11-25, `origin/19.0` `a91770ee` + esta rama, base nueva `t16351_rev25`):
      `odoo -d t16351_rev25 -i l10n_ve_pos,l10n_ve_pos_self_order --test-tags /l10n_ve_pos,/l10n_ve_pos_self_order --stop-after-init --workers=0`
      → 311 tests, 0 fallos, 3 errores que también salen en `origin/19.0` sin esta rama
      (`test_kiosk_invoice_foreign_credit_precise_across_many_rates_and_quantities` con 7.654.321 Bs/$: el pago
      no se publica sin tasa, chequeo de `l10n_ve_accountant` ya en 19.0). Hoot
      `session_opening_rate.test.js` en `/web/tests`: 12/12; con el `return "ok"` anterior falla el test de sin
      conexión (11/12). Los tours de `binaural_pos_multicurrency` están en integra-addons#3249

