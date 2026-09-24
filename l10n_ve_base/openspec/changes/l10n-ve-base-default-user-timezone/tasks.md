# Tasks

## 1. Diagnóstico

- [x] 1.1 Auditada la cadena `invoice_date` → `invoice_date_display` →
      `date` en `l10n_ve_accountant`/`l10n_ve_invoice`: los tres defaults
      ya usan `fields.Date.context_today` (fix previo, ver
      `l10n_ve_accountant/openspec/changes/l10n-ve-invoice-date-display-timezone-fix`)
- [x] 1.2 Descartada colisión de campos entre `l10n_ve_accountant` e
      `l10n_ve_invoice` al redefinir `invoice_date`: atributos
      complementarios (uno fija `copy`/`string`, el otro
      `default`/`help`), sin conflicto real
- [x] 1.3 Confirmado en core Odoo 19 (`_compute_date`, `_get_accounting_date`,
      `account_move.py:848,6584`) que toda la ruta usa
      `fields.Date.context_today(self)`, no `fields.Date.today()`
- [x] 1.4 Identificado que `fields.Date.context_today()` degrada a UTC
      cuando no hay `tz` en `record._context` ni en `record.env.user.tz`
      (`base/models/res_partner.py:223`, `tz` sin default estático)
- [x] 1.5 Reproducido en staging (Odoo.sh): usuario Administrator con
      **Zona horaria** vacía → confirma la causa raíz real

## 2. Fix

- [x] 2.1 `l10n_ve_base/models/res_partner.py`: `tz` con
      `default=lambda self: self.env.context.get("tz") or "America/Caracas"`
- [x] 2.2 `l10n_ve_base/models/__init__.py`: `from . import res_partner`
- [x] 2.3 `l10n_ve_base/__init__.py`: corregido de vacío a
      `from . import models` (sin esto, ni el fix ni el resto del módulo
      cargaban — hallazgo colateral, no introducido por este cambio)

## 3. Migración (backfill de usuarios existentes)

- [x] 3.1 `l10n_ve_base/__manifest__.py`: versión `"1.0"` →
      `"19.0.1.0.1"` (requerido para que la migración dispare en `-u`)
- [x] 3.2 `l10n_ve_base/migrations/19.0.1.0.1/post-migrate.py`: backfillea
      `tz = "America/Caracas"` en `res.users` con `tz` vacío
- [x] 3.3 Descartado `post_init_hook` como mecanismo: solo corre en
      instalaciones nuevas (`-i`), no en `-u` de un módulo ya instalado en
      los clientes — por eso el backfill va en `migrations/`, no en el
      `__init__.py`

## 4. Tests

- [x] 4.1 `tests/test_res_partner_tz_default.py`: default sin tz en
      contexto, respeta tz del contexto, respeta valor explícito, aplica
      a `res.partner` directamente (no solo vía formulario de usuarios) —
      sin datos demo, cada test crea sus propios registros
- [x] 4.2 `tests/test_migration_backfill_tz.py`: backfillea solo usuarios
      con `tz` vacío, no toca a los que ya tienen uno, no falla cuando no
      hay nada que corregir — carga `post-migrate.py` vía `importlib`
      (el directorio `19.0.1.0.1/` no es un nombre de paquete válido)
- [x] 4.3 Corridos los 6 tests contra una instancia Docker real
      (`-i l10n_ve_base --test-enable --test-tags /l10n_ve_base`,
      DB temporal descartada al terminar): 0 fallos, 0 errores
- [x] 4.4 Confirmado que el fix al `__init__.py` vacío no rompe la carga
      del módulo (22 dependencias, instalación limpia)

## 5. Verificación pendiente

- [ ] 5.1 Auditar `res.users` con `tz = False` en ambientes productivos
      antes de generalizar el deploy
- [ ] 5.2 (Verificación manual del líder técnico / consultor, no
      automatizable desde este repo) Confirmar en el cliente reportante
      (TI-15211) que, tras `-u l10n_ve_base`, las facturas nocturnas dejan
      de desfasarse. El repro automatizado equivalente ya vive en
      `l10n_ve_invoice/tests/test_ti_15211_invoice_date_timezone.py`.
- [x] 5.4 Corrido `-u l10n_ve_base` contra una DB con el módulo instalado
      en `19.0.1.0` (instalación previa real, no `-i` limpio):
      `odoo.upgrade.l10n_ve_base.19.0.1.0.1.post-migrate: l10n_ve_base
      19.0.1.0.1: backfilled tz='America/Caracas' for 5 user(s) with no
      timezone set. User ids: [2, 1, 3, 5, 6]`. El id `3` es el Public
      user real de la base (`login=public`, `share=True`, archivado);
      confirmado por consulta directa que también se backfilleó, junto a
      OdooBot (`id=1`) y un usuario portal simulado (`share=True`, sin
      `group_public`) que **no** se tocó, como se esperaba.
- [ ] 5.3 Revisar si algún otro flujo (vencimientos, reportes, cron) se
      vio afectado por el mismo `tz` vacío en el mismo ambiente

## 6. OpenSpec

- [x] 6.1 `proposal.md` + spec delta (`user-timezone-default`)
- [ ] 6.2 (Verificación manual del líder técnico: requiere el CLI
      `openspec` instalado/configurado, no disponible en este entorno de
      corrección) `openspec validate --changes`

## 7. Correcciones del review (PR #1346, pastor-binaural)

- [x] 7.1 Migración: `active_test=False` para alcanzar usuarios archivados
      (OdooBot, Public user)
- [x] 7.2 Migración: `share = False` para no tocar partners de usuarios
      portal
- [x] 7.3 Test que reproduce el síntoma real (`account.move` con fechas
      desfasadas) en `l10n_ve_accountant`
- [x] 7.4 Default de `tz` en `res_partner.py` derivado de
      `env.company.partner_id.tz` antes de caer al literal fijo
- [x] 7.5 Eliminado `models/ir_ui_view.py` (override vacío sin uso) y su
      import en `models/__init__.py`
- [x] 7.6 `test_noop_when_no_user_has_empty_tz` fuerza el estado noop
      explícitamente; quitado el `try/except Exception` que ocultaba el
      traceback
- [x] 7.7 `DEFAULT_TZ` definido una sola vez (`res_partner.py`), importado
      por `post-migrate.py`
- [x] 7.8 Newline final agregado en `l10n_ve_base/__init__.py` y
      `l10n_ve_base/models/__init__.py`

## 8. Correcciones del review (PR #1346, christopherBinaural, ronda 2)

- [x] 8.1 Migración: dominio corregido para alcanzar al Public user por
      compañía (`base.group_public`) sin tocar portales de clientes —
      `share = False` por sí solo excluía al Public user, que es
      `share = True` igual que un portal. Tests nuevos:
      `test_backfills_public_user_with_empty_tz` y
      `test_does_not_touch_portal_users`
      (`l10n_ve_base/tests/test_migration_backfill_tz.py`).
- [x] 8.2 DoD: aserción agregada sobre `account.move.line.date` en
      `l10n_ve_invoice/tests/test_ti_15211_invoice_date_timezone.py`
      (antes solo se validaban los campos del `account.move`).
- [x] 8.3 `proposal.md` § Impact: declarada la columna nueva
      `ir_module_module.binaural` (data-model change en rama estable) y
      el criterio de alcance del Public user en la migración.
- [x] 8.4 Evidencia de `-u l10n_ve_base` real (ver 5.4): corrido contra
      una DB con el módulo previamente instalado en `19.0.1.0`. El
      Public user real de la base (`id=3, login=public`) quedó
      backfilleado junto a OdooBot; un portal simulado no se tocó.
