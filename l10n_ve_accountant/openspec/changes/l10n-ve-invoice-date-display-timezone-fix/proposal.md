# Fix: validar una orden del PdV falla después de las 20:00 hora Venezuela ("No puede generar facturas que no estén registradas")

## Why

Un usuario reportó (2026-07-27, BD `pos2`) que al validar una orden desde el
PdV salía el error **"No puede generar facturas que no estén registradas."**
La orden no se validaba y no quedaba rastro en la base de datos.

El mensaje **no es de ningún módulo custom**: es de Odoo nativo,
`account/models/account_move_send.py:340`, msgid
`"You can't generate invoices that are not posted."`, traducido así en
`account/i18n/es_419.po`. Significa literalmente que se intentó generar el
PDF de una factura que quedó en **borrador**.

### Cadena completa

`point_of_sale/models/pos_order.py:1157` `_generate_pos_order_invoice()`:

```python
invoice = self._create_invoice(invoice_vals)
invoice.sudo().with_company(company).with_context(**self._get_invoice_post_context())._post()
...
if self.env.context.get('generate_pdf', True):
    invoice.with_context(skip_invoice_sync=True)._generate_and_send()   # ← lanza el UserError
```

`_post(soft=True)` de core **no publica los asientos con fecha futura**
(`account/models/account_move.py:5627`):

```python
future_moves = self.filtered(lambda move: move.date > fields.Date.context_today(self))
...
to_post = self - future_moves
```

`fields.Date.context_today()` es **consciente de la zona horaria** del
usuario (`America/Caracas`, UTC-4).

Ahora, de dónde sale `move.date`. `l10n_ve_accountant` redefine la fuente de
la fecha contable (`models/account_move.py:28-35`):

```python
def _get_accounting_date_source(self):
    return self.invoice_date_display or self.date
```

y declaraba el campo así (`models/account_move.py:21`):

```python
invoice_date_display = fields.Date(string="Invoice Date", default=fields.Date.today)
```

`fields.Date.today()` es `date.today()` — **hora local del contenedor, que
corre en UTC**. No tiene nada que ver con la zona horaria del usuario.

El flujo del PdV (`_prepare_invoice_vals`, core `pos_order.py:920`) sí
calcula bien `invoice_date` convirtiendo a la zona del usuario
(`invoice_date.astimezone(timezone).date()`), pero **nunca pasa
`invoice_date_display`**, así que este cae en su `default`. Los dos
`@api.onchange` que los mantienen sincronizados
(`l10n_ve_accountant:145-148`, `l10n_ve_invoice:112-115`, y
`l10n_ve_accountant:318-322`) solo se disparan en el formulario web, jamás
en creación programática o por RPC.

### El resultado, entre las 20:00 y las 23:59 hora Venezuela

Con la hora del incidente (`2026-07-28 01:22 UTC` = `2026-07-27 21:22` en
Caracas):

| Valor | Origen | Resultado |
|---|---|---|
| `invoice_date` | core, tz del usuario | `2026-07-27` ✅ |
| `invoice_date_display` | `default=fields.Date.today` (UTC) | `2026-07-28` ❌ |
| `move.date` | `_get_accounting_date_source()` → display | `2026-07-28` |
| `fields.Date.context_today()` en `_post` | tz del usuario | `2026-07-27` |

`2026-07-28 > 2026-07-27` → la factura se clasifica como movimiento futuro,
se le pone `auto_post='at_date'` y **se queda en borrador**. Acto seguido
`_generate_and_send()` la rechaza por no estar publicada, el `UserError`
sube por `sync_from_ui` y **toda la transacción hace rollback**.

Es un bug de ventana horaria: solo se reproduce entre las **00:00 y 03:59
UTC**, o sea de **20:00 a 23:59 hora Venezuela**. Encaja con la evidencia:
en `pos2` las facturas de PdV creadas hasta `20:34 UTC` (16:34 Caracas)
quedaron todas `posted` con `invoice_date = invoice_date_display = date =
2026-07-27`; las de la 01:22 UTC fallaron todas.

## What Changes

- `l10n_ve_accountant/models/account_move.py`
  - `invoice_date_display`: `default=fields.Date.today` →
    `default=fields.Date.context_today`. Este es **el fix del bug**: alinea
    la fecha contable con el mismo reloj que usa `_post()` para decidir si
    un asiento es futuro.
  - `_onchange_move_type`: `fields.Date.today()` →
    `fields.Date.context_today(self)` en `invoice_date` e
    `invoice_date_display` (mismo bug, camino UI).
- `l10n_ve_invoice/models/account_move.py`
  - `invoice_date`: `default=fields.Date.today` →
    `default=fields.Date.context_today`.
  - `_onchange_move_type`: `fields.Date.today()` →
    `fields.Date.context_today(self)`.
- `l10n_ve_iot_mf/models/account_move.py` (líneas 141, 247, 346)
  - La validación de impresión fiscal
    `invoice_date_display != fields.Date.today()` →
    `fields.Date.context_today(self)`, para que no bloquee la impresión en
    la misma franja horaria una vez corregido el default.

## Impact

- **Capability**: `invoice-accounting-date-timezone` (nueva).
- **Módulos**: `l10n_ve_accountant`, `l10n_ve_invoice`. Requiere reinicio de
  Odoo (cambio solo Python; los `default` se evalúan en runtime, no hace
  falta `-u` para que apliquen a facturas nuevas).
- **Alcance real**: afecta a **toda factura creada programáticamente o por
  RPC** en la franja 20:00–23:59 VE, no solo al PdV — ventas desde
  `sale.order`, facturación en lote, importaciones, API. En el PdV explota
  con `UserError`; en otros flujos el síntoma es más silencioso (la factura
  queda en borrador con `auto_post='at_date'` y fecha contable un día
  adelantada).
- **Datos existentes**: en `pos2` no quedó ningún asiento colgado — el
  rollback de `sync_from_ui` los eliminó (verificado: los ids 1042–1047 de
  los logs no existen, y no hay ningún `account_move` con `auto_post <>
  'no'` ni ninguna `out_invoice`/`out_refund` en borrador). **No hace falta
  data-fix.** Conviene revisar otras BD productivas por si alguna factura
  quedó en borrador con `auto_post='at_date'` y fecha adelantada un día.
- **Riesgo**: bajo. `fields.Date.context_today` es el default estándar de
  core para campos de fecha contable (p. ej.
  `account_payment.py:16`). Cuando el contenedor y el usuario están en la
  misma zona horaria el comportamiento es idéntico al anterior.
- **Sin verificar en navegador todavía**: pendiente que el usuario repita la
  validación de una orden del PdV en la franja horaria afectada.

## La separación `invoice_date` (tasa) / `invoice_date_display` (fiscal) no cambia

El diseño de `l10n_ve_accountant` se mantiene intacto — este cambio toca
únicamente `default`s, no el cableado:

- `invoice_date` sigue siendo la fecha de tasa
  (`account_move_line.py:423`, `account_move.py:354, 516, 1476, 1495, 1540`).
- `invoice_date_display` sigue siendo la fecha fiscal/visual (libros,
  reportes, retenciones) **y** la fuente de la fecha contable `date` vía
  `_get_accounting_date_source()` — no es un campo meramente decorativo, y
  por eso su default en UTC rompía la publicación.
- `_get_accounting_date_source()` y `_onchange_invoice_date_display()` no se
  modifican.

Ambos defaults se movieron a la vez (`today` → `context_today`), así que la
relación entre los dos campos es la misma; solo cambia el día que devuelven
cuando la fecha UTC del servidor difiere de la local del usuario.

**En el PdV la tasa no cambia**: core pasa `invoice_date` explícitamente en
`_prepare_invoice_vals` ya convertido a la zona del usuario, de modo que el
`default` nunca se aplicaba en esa ruta. Solo se corrige
`invoice_date_display`.

**En factura manual desde el formulario sí hay cambio de comportamiento**:
en la franja 20:00–23:59 VE el formulario abría con la fecha de mañana en
ambos campos y ahora abre con la de hoy, lo que mueve también la fecha de
tasa de mañana a hoy (que es la corrección buscada — pedir la tasa de una
fecha futura era el error).

## `l10n_ve_iot_mf` tenía el mismo bug al revés (incluido)

`l10n_ve_iot_mf/models/account_move.py:141, 247, 346` valida la impresión
fiscal con:

```python
if self.invoice_date_display != fields.Date.today():
    raise ValidationError(_("Cannot print an invoice with a future date"))
```

Compara contra UTC. Con este fix, en la franja 20:00–23:59 VE
`invoice_date_display` sería la fecha local (p. ej. 27) y
`fields.Date.today()` la UTC (28): no coincidirían y **bloquearía la
impresión fiscal**. Es el mismo bug de raíz y necesita el mismo
`context_today`.

Corregido en las tres líneas con `fields.Date.context_today(self)`. El
módulo está `uninstalled` en `pos` y `pos2` (igual que
`l10n_ve_invoice_digital` y `l10n_ve_pos_mf`), así que no se puede verificar
aquí: **queda pendiente de probar en una BD con máquina fiscal instalada**.

## Pendiente relacionado: el cron de auto-publicación está desactivado

Cuando `_post(soft=True)` clasifica un asiento como futuro le pone
`auto_post='at_date'` y lo deja en borrador; quien lo publica después es el
cron `ir_cron_auto_post_draft_entry` (core `account`, diario a las 02:00,
`model._autopost_draft_entries()`).

En `pos` y en `pos2` ese cron está **desactivado** (`active = f`), pese a que
en core viene activo por defecto (`account/data/service_cron.xml` no fija
`active`). Es decir: cualquier asiento que quede programado en esas bases —
por este bug o por un flujo legítimo, como un reverso con fecha futura desde
`account_move_reversal.py:106` — **no se publicaría nunca**.

No forma parte de este cambio (con el fix ya no se programan facturas del PdV
por accidente), pero conviene decidir si la desactivación fue deliberada.

## Observación aparte (no incluida en este cambio)

`integra-addons/binaural_hr_payroll` usa `default=fields.Date.today()` —
**con paréntesis** — en cuatro campos (`hr_payroll_move.py:35`,
`hr_employee_childs_education.py:19`, `hr_employee_salary_change.py:11`,
`hr_employee_scholarship.py:16`). Eso evalúa la fecha **una sola vez al
importar el módulo**, dejando congelada la fecha de arranque del worker como
default permanente. Es un bug distinto y ese módulo no está instalado en
`pos2`; se deja anotado, no se toca aquí.
