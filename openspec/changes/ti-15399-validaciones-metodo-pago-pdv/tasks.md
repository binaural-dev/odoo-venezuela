## 0. Decisiones

- [x] 0.1 Rama `19.0_fix-ti_15399_pos_payment_method_validations` desde `19.0`. Ticket: 15399
- [x] 0.2 La caja no es obligatoria en el método (design.md, D1)
- [x] 0.3 La regla de las transitorias aplica a todo método en moneda alterna o con moneda de cobro, no solo al
      efectivo (design.md, D2)
- [x] 0.4 Quitar la regla de moneda para un método sin caja que traía el parche original (design.md, D3)

## 1. l10n_ve_pos: cuentas transitorias distintas

- [x] 1.1 `pos.payment.method._check_distinct_suspense_accounts` en `models/pos_payment_method.py`: método con
      `is_foreign_currency` o `tender_currency_id` cuyo `journal_id` y `cross_journal` tienen la misma
      `suspense_account_id` → `ValidationError`. Vigila `is_foreign_currency`, `tender_currency_id`, `journal_id`
      y `cross_journal`
- [x] 1.2 `account.journal._check_pos_methods_distinct_suspense_accounts` en `models/account_journal.py` (archivo
      nuevo, importado en `models/__init__.py`): al cambiar `suspense_account_id`, revisa con `sudo()` los
      métodos que usan el diario como `journal_id` o como `cross_journal` (design.md, D2)

## 2. l10n_ve_pos: diario en la moneda de sus cajas

- [x] 2.1 `pos.payment.method._check_journal_currency_in_pos` en `models/pos_payment_method.py`: un diario con
      moneda distinta de la de alguna de sus cajas → `ValidationError`; un diario sin moneda pasa
- [x] 2.2 Con 0.4: quitar el bloque que exige la moneda de la compañía a un método en moneda alterna o con moneda
      de cobro, dejar el `@api.constrains` en `journal_id` y `config_ids` y ajustar el docstring

## 3. Traducciones

- [x] 3.1 `i18n/es_VE.po`: mensajes de 1.1 y 2.1
- [x] 3.2 Con 0.4: quitar el mensaje de la regla de 2.2

## 4. Pruebas

- [x] 4.1 Archivo nuevo `tests/test_pos_payment_method_validations.py` (registrarlo en `tests/__init__.py`), un
      caso por escenario de la spec de cambios:
      - transitorias iguales al guardar un método en moneda alterna y uno con moneda de cobro → error;
      - transitoria igualada desde el diario afectado y desde el diario del método → error al guardar el diario;
      - transitorias distintas → se guarda;
      - método sin cruce con las transitorias iguales → se guarda;
      - método guardado antes de la regla (transitorias igualadas por SQL): sigue legible; al cambiarle
        `cross_journal` → error;
      - diario en USD en una caja en Bs, desde el método y agregando la caja desde el método → error;
      - diario en la moneda de la caja y diario sin moneda → se guarda;
      - método sin caja en moneda alterna con diario en otra moneda → se guarda (con 0.4)
- [x] 4.2 `tests/test_pos_session_cross_account_move.py`:
      `test_cash_sale_emits_the_move_even_when_both_suspense_accounts_match` iguala las transitorias por el ORM y
      hoy choca con 1.2. Igualarlas por SQL (un método guardado antes de la regla) y conservar lo que
      asevera: el asiento se crea sin efecto contable
- [x] 4.3 Suites de los módulos que crean métodos con cruce o con moneda de cobro, sin fallos nuevos:
      `binaural_pos_multicurrency`, `binaural_pos_close` (integra-addons en `origin/19.0`), `l10n_ve_pos_mf`,
      `l10n_ve_pos_self_order`: 286 pruebas, 1 error ajeno a este cambio (`setUpClass` de
      `l10n_ve_pos_mf/tests/test_pos_order_print_verification.py`: «You can't open the session without a foreign
      cash payment method», de `binaural_pos_close`). No se comparó contra `19.0` sin la rama

## 5. Manifest

- [x] 5.1 Subir `l10n_ve_pos/__manifest__.py` de 19.0.1.32.0 a 19.0.1.32.1. Se verifica con `-u l10n_ve_pos` sin
      errores en una base de prueba

## 6. Verificación

- [x] 6.1 Suite de `l10n_ve_pos` en una base nueva con el parche original: 17 clases fallan en `setUpClass`, todas
      por la regla de 0.4. Sin esa regla: 259 pruebas al instalar, 1 error, el de 4.2
- [x] 6.2 pre-commit verde sobre los archivos del parche
- [x] 6.3 Suite de `l10n_ve_pos` en verde con 0.4, 4.1 y 4.2: 272 pruebas; la clase nueva, 13 de 13
- [x] 6.4 En poscon2, por la interfaz, con una caja en Bs y otra en USD: los casos del ticket (método en moneda
      alterna con la transitoria por defecto en los dos diarios; diario en USD en una caja en Bs) dan el error al
      guardar el método, no al abrir la caja. Probado por el usuario

## 7. Diarios de cruce obligatorios para moneda alterna

- [x] 7.1 Exigir `cross_account_journal` y `cross_journal` en `models/pos_payment_method.py` y
      `views/pos_payment_method.xml` cuando el método se marca en moneda alterna.
- [x] 7.2 Traducir el error en `i18n/es_VE.po` y actualizar el escenario de configuración incompleta.
- [x] 7.3 Verificar en Odoo los casos de creación, activación y eliminación de un diario, y los métodos
      antiguos sin cruce en `tests/test_pos_payment_method_validations.py` y
      `tests/test_pos_session_cross_account_move.py`. Suite `/l10n_ve_pos`: 275 pruebas en verde.
- [x] 7.4 Actualizar `l10n_ve_pos` en `poscon2_ti16547_test` y verificar la vista resuelta y el mensaje
      en español desde Odoo, con rollback de los datos de prueba.

## Workflow follow-up

- PR a `19.0` con "Ticket: https://binaural.odoo.com/odoo/all-tickets/15399".
- Nota en el chatter del ticket solo después de que se pruebe en poscon2.
- Avisar a consultoría: los métodos en moneda alterna o con moneda de cobro necesitan una cuenta transitoria por
  diario. La consulta de design.md (D4) lista los métodos ya guardados con las dos iguales.
- Archivar este change después del merge. `cruce-venta-efectivo-entre-transitorias` se archiva aparte.
