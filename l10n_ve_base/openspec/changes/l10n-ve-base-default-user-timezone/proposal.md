# Fix: usuarios sin zona horaria configurada desfasan la fecha contable un día (TI-15211)

## Why

Ticket TI-15211: al registrar o validar una factura en horario nocturno
(pasadas las 8:00 PM hora Venezuela), el campo `invoice_date` quedaba con
la fecha correcta del día local, pero `date` (fecha contable) e
`invoice_date_display` (fecha de visualización) tomaban la fecha del día
**siguiente**. Esto desfasaba secuencias de libros contables, cierres de
caja diarios y reportes fiscales.

### Descartado: no es un bug en la cadena de cómputo de fechas

El ticket planteaba como causa raíz el patrón clásico de
`datetime.now()`/`fields.Date.today()` (hora UTC del servidor) sin
convertir a la zona horaria del usuario. Se auditó toda la cadena
`invoice_date` → `invoice_date_display` → `date` en `l10n_ve_accountant` y
`l10n_ve_invoice`:

- `invoice_date_display` (`l10n_ve_accountant/models/account_move.py:22`):
  `default=fields.Date.context_today`.
- `invoice_date` (`l10n_ve_invoice/models/account_move.py:24`):
  `default=fields.Date.context_today`.
- `_get_accounting_date_source()` (`l10n_ve_accountant/models/account_move.py:39-46`):
  usa `invoice_date_display`, que ya es tz-aware.
- Core Odoo 19 (`_compute_date`, `_get_accounting_date`) también usa
  `fields.Date.context_today(self)` en todos los puntos relevantes.

Este camino ya fue corregido antes por un cambio relacionado (ver
`l10n_ve_accountant/openspec/changes/l10n-ve-invoice-date-display-timezone-fix`,
que movió esos mismos campos de `fields.Date.today` a
`fields.Date.context_today` tras un incidente de PdV). No hay ningún
`fields.Date.today()`/`datetime.now()` sin convertir en la ruta que puebla
estos tres campos. Verificamos también que no existe colisión entre las
redefiniciones de `invoice_date` en `l10n_ve_accountant` y
`l10n_ve_invoice` (atributos complementarios, sin atributos en conflicto:
uno fija `copy`/`string`, el otro `default`/`help`).

### Causa raíz real: `context_today()` sin zona horaria resuelta cae a UTC

`fields.Date.context_today(record)` (core) es tz-aware **solo si logra
resolver un tz**:

```python
tz_name = record._context.get('tz') or record.env.user.tz
if tz_name:
    ...  # conversión correcta a la zona horaria
return today.date()  # sin tz_name: hora del servidor cruda (UTC)
```

Se reprodujo el síntoma exacto en el ambiente de staging
(`binauraldev.com`, Odoo.sh): el usuario **Administrator** tenía el campo
**Zona horaria** (`res.users.tz`, delegado desde `res.partner.tz`) vacío.
El propio formulario de Odoo lo advierte: *"Si no ha configurado una,
entonces se usa UTC"*. Sin `tz` en el contexto de la request (flujos sin
sesión de navegador normal: automatizaciones, integraciones, o
simplemente un usuario al que nunca se le configuró) y sin `res.users.tz`,
`context_today()` degrada exactamente al comportamiento reportado.

`res.partner.tz` (`base/models/res_partner.py:223`) no tiene un default
estático — solo `default=lambda self: self.env.context.get('tz')` — así
que cualquier usuario creado sin un `tz` presente en el contexto de
creación queda permanentemente en `False`.

## What Changes

- `l10n_ve_base/models/res_partner.py` (nuevo): override de `tz` en
  `res.partner` — `default=lambda self: self.env.context.get("tz") or
  "America/Caracas"`. Sigue respetando el tz que mande el cliente si viene
  en el contexto; solo aplica el fallback regional cuando no hay nada.
  Como `res.users` delega el campo `tz` a `res.partner` vía `_inherits`,
  cubre ambos modelos.
- `l10n_ve_base/__init__.py`: estaba **vacío** (0 bytes) — el paquete
  `models/` nunca se importaba, así que `ir_module.py` (campo `binaural`)
  e `ir_ui_view.py` (override vacío) llevaban inertes desde siempre.
  Corregido a `from . import models` porque, sin eso, el nuevo default de
  `tz` tampoco cargaría. Hallazgo colateral, no introducido por este
  cambio.
- `l10n_ve_base/models/__init__.py`: agregado `from . import res_partner`.
- `l10n_ve_base/__manifest__.py`: versión `"1.0"` → `"19.0.1.0.1"`
  (formato `19.0.x.y.z` usado en el resto del repo; necesario para que
  Odoo dispare la migración en `-u`).
- `l10n_ve_base/migrations/19.0.1.0.1/post-migrate.py` (nuevo): backfillea
  `tz = "America/Caracas"` en todo `res.users` con `tz` vacío al momento
  de actualizar el módulo. Necesario porque el default de campo solo se
  evalúa en `create()` — no es retroactivo para usuarios ya existentes.
- `l10n_ve_base/tests/` (nuevo): `test_res_partner_tz_default.py` (default
  respeta contexto/valor explícito, aplica tanto a `res.partner` como a
  `res.users`) y `test_migration_backfill_tz.py` (la migración backfillea
  solo a quien tiene `tz` vacío, y no falla cuando no hay nada que
  corregir). Sin datos demo/fixture: cada test crea sus propios registros.

## Impact

- **Capability**: `user-timezone-default` (nueva, en `l10n_ve_base`).
- **Módulos**: solo `l10n_ve_base`. No se modificó
  `l10n_ve_accountant`/`l10n_ve_invoice` — su cadena de fechas ya estaba
  correcta.
- **Alcance real**: no es específico de facturación. Cualquier cómputo que
  dependa de `fields.Date.context_today()`/`fields.Datetime.context_timestamp()`
  en cualquier módulo (fechas contables, vencimientos, reportes,
  validaciones de "no future date") se beneficia del mismo fix, porque la
  causa raíz era la resolución del tz del usuario, no un campo puntual de
  `account.move`.
- **Datos existentes**: requiere `-u l10n_ve_base` para que la migración
  corra. Usuarios con `tz` ya seteado (aunque sea distinto de
  `America/Caracas`, p. ej. un usuario remoto) no se tocan.
- **Riesgo**: bajo. El fallback solo actúa cuando no hay ninguna señal de
  tz (ni contexto ni usuario), y es el mismo valor regional que ya se usa
  como default de facto en el resto de la localización venezolana.
- **Verificado**: reproducido el síntoma en staging con `tz` vacío;
  corregido manualmente por UI como mitigación inmediata; 6 tests
  automatizados corridos contra una instancia real confirman el default y
  la migración (ver `tasks.md`).
- **Pendiente**: confirmar en ambientes productivos cuántos usuarios
  tienen `tz` vacío antes de generalizar el deploy (auditoría sugerida:
  `res.users` con `tz = False`).
