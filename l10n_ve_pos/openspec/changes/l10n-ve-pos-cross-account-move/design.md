# Design: Cruce automático transitoria → banco (l10n_ve_pos)

## ⚠️ Superado parcialmente por `l10n-ve-pos-cross-move-by-split-transactions`

Dos partes de este documento **ya no describen el código**:

- **Qué dispara el cruce**: era `apply_one_cross_move`; ese campo fue
  eliminado. Ahora dispara `is_foreign_currency` + ambos diarios de cruce.
- **Cómo se decide la granularidad y desde dónde se dispara**: el walkthrough
  de la sección "3. Al cerrar sesión: dos rutas paralelas" describe dos
  disparadores independientes (`_validate_cross_move` para split,
  `_create_combine_account_payment` para combine). Esa asimetría era un bug:
  `_validate_cross_move` no filtraba por `split_transactions`, así que los
  métodos combinados recibían un asiento agregado **más** uno por pago. Hoy
  hay un único punto de entrada y la granularidad la decide
  `split_transactions`.
- **Bug #4 (cuenta transitoria de métodos `cash`)**: el fallback a
  `account_default_pos_receivable_account_id` evitaba el error de Postgres
  pero apuntaba a la cuenta contable equivocada. Corregido allá.

Sigue vigente de acá: el asiento nace en `draft` y no se postea solo, el texto
va en `ref` para no bloquear la secuencia del diario en `name` (bug #5), y el
fix del id de moneda hardcodeado (bug #3).

## Estado de este change

**No archivado.** Sigue viviendo en `openspec/changes/l10n-ve-pos-cross-account-move/`
(no en `openspec/specs/`, que hoy está vacío para esta capability). Queda
abierto porque falta la tarea 4.5 en `tasks.md` (test/auditoría
multicompañía). Cualquier agente que busque la capability `pos-cross-account-move`
por el flujo normal de specs no la va a encontrar — debe buscarla aquí, en
`changes/`.

## Flujo completo (walkthrough)

Todo el código vive en `src/odoo-venezuela/l10n_ve_pos/models/pos_session.py`.

### 1. Configuración (una vez, por método de pago)

En `pos.payment.method` (campos definidos en `pos_payment_method.py`):

- `is_foreign_currency` — marca que este método maneja divisa (control de negocio, no toca el cruce directamente).
- `outstanding_account_id` — campo **nativo** de Odoo, la cuenta transitoria del método. Solo editable en la UI cuando `type == 'bank'` (`invisible="type != 'bank'"` en la vista nativa) — en métodos `cash` siempre queda vacío, por diseño de Odoo (ver bug #4).
- `cross_account_journal` — diario tipo `general` (Miscelánea) donde queda registrado el asiento de cruce.
- `cross_journal` — diario tipo `bank`/`cash` que representa la cuenta **real** hacia donde se traslada el valor; debe tener configuradas líneas de pago entrante (`inbound_payment_method_line_ids.payment_account_id`) y saliente (`outbound_payment_method_line_ids.payment_account_id`).
- `apply_one_cross_move` — interruptor on/off del cruce (label en UI: "Enable Automatic Cross-Account Clearing" / "Habilitar cruce automático de cuenta transitoria"). Independiente de `split_transactions` ("Identificar cliente"): éste decide split vs. combine, no si hay cruce o no.

Los cuatro campos (`is_foreign_currency`, `cross_account_journal`, `cross_journal`, `apply_one_cross_move`) se cargan al frontend del POS vía `_load_pos_data_fields`, pero ahí son solo datos informativos — la lógica del cruce corre 100% en backend, al cerrar sesión.

### 2. Durante la sesión: contabilización normal (sin cambios)

Cada pago se contabiliza como siempre en Odoo — cae en `outstanding_account_id` (bank) o en la cuenta del diario de caja (cash), vía el pipeline nativo. El cruce **no** interviene aquí; solo actúa al cerrar sesión.

### 3. Al cerrar sesión: dos rutas paralelas según `split_transactions`

**Ruta split** (`split_transactions=True`, "Identificar cliente" ✓ — un pago = un registro):

```
action_pos_session_close()
  └─ super().action_pos_session_close(...)      # pipeline nativo, sin tocar
  └─ self._validate_cross_move()                # ← engachado aquí
       for cada pos.payment de la sesión:
         if type == pay_later: skip
         if not apply_one_cross_move: skip
         if falta cross_account_journal/cross_journal/cuenta transitoria: skip
         if payment.amount >= 0:
           line_vals = _line_vals_move_cross_incoming(payment)
         else:
           line_vals = _line_vals_move_cross_outgoing(payment)
         _create_cross_move(payment, line_vals)   # crea 1 account.move en draft
```

Resultado: **un asiento de cruce por cada pago** de un método con el flag activo.

**Ruta combine** (`split_transactions=False` — todos los pagos del método se agrupan en un solo `account.payment` por sesión):

```
_create_combine_account_payment(payment_method, amounts, diff_amount)
  └─ res = super()...                             # pipeline nativo (crea el account.payment agrupado)
  └─ [fix Odoo 19: origin_payment_id en vez de payment_id]
  └─ escribe foreign_rate/foreign_debit/foreign_credit (ya existía antes de este change)
  └─ if apply_one_cross_move + ambos journals + cuenta transitoria resuelta:
       self._create_cross_move_payment(res)        # ← disparado DESDE ACÁ, no desde action_pos_session_close
            line_vals = _line_vals_move_cross_payment_incoming(res)
            crea 1 account.move en draft
```

Resultado: **un asiento de cruce por sesión** (agrupa todos los pagos combinados de ese método). No existe rama "outgoing" para combine — el vuelto siempre se paga en efectivo, nunca por un método bank combinado (limitación heredada del código original, documentada, no un bug).

Nota de asimetría intencional: split se dispara **después** del pipeline nativo (`action_pos_session_close`); combine se dispara **durante** (dentro de `_create_combine_account_payment`, que el pipeline nativo ya invoca). No se unificó para minimizar el diff contra el código legacy.

### 4. La cuenta transitoria (ambas rutas)

`_get_cross_transitory_account(payment_method)` resuelve siempre:

```python
payment_method.outstanding_account_id or self.company_id.account_default_pos_receivable_account_id
```

Para métodos `bank`, normalmente hay `outstanding_account_id` configurado y se usa directo. Para métodos `cash` (que nunca lo tienen, ver bug #4), cae al fallback — el mismo patrón que usa el nativo `_get_receivable_account`.

### 5. El asiento de cruce en sí

Cada `account.move` creado (`_create_cross_move` / `_create_cross_move_payment`):

- Vive en el diario `cross_account_journal` (Miscelánea).
- Tiene 2 líneas: una sobre la cuenta real (`cross_journal`) y otra sobre la cuenta transitoria, en direcciones opuestas de débito/crédito según el signo del pago.
- Lleva `foreign_debit`/`foreign_credit`/`foreign_rate` con el monto en divisa, coherente con la tasa operativa de la sesión.
- **Se crea siempre en `state="draft"`** — nunca se llama `action_post()`. Queda pendiente de revisión manual por contabilidad.
- El texto descriptivo "PoS Payment Method Adjustment" vive en `ref` ("Referencia"), NO en `name` ("Número"). `name` se deja sin asignar a propósito: es el campo que Odoo calcula nativamente (`_compute_name`/`_set_next_sequence`) tomando la secuencia del diario en el que vive el asiento — en este caso, la secuencia propia de `cross_account_journal`. Fijar `name` con un literal en el `create()` bloquearía esa asignación para siempre.

### 6. Paso manual final (fuera del alcance del código)

Contabilidad revisa el/los asiento(s) en el diario de Miscelánea y los postea a mano. En el momento de postear (`action_post()`), Odoo asigna la secuencia de `cross_account_journal` a `name` (ej. `MISC/2026/00001`) — antes de eso, `name` queda en `/` (placeholder de borrador). Solo al postear el valor realmente se traslada de la cuenta transitoria a la cuenta real.

**Decisión confirmada con el usuario**: la secuencia es la del diario en el que vive el asiento (`cross_account_journal`, Miscelánea), no la del diario real (`cross_journal`) — mover el asiento al diario real habría sido un cambio de diseño mayor (redefinir para qué sirve `cross_account_journal`), descartado explícitamente.

## Bugs encontrados

| # | Ubicación | Problema | Fix |
|---|---|---|---|
| 1 | `_validate_cross_move` (ruta split) | `if not apply_one_cross_move:` dispara el cruce cuando el flag está en `False` (el default) — polaridad invertida respecto al nombre del campo | Invertir a `if apply_one_cross_move:` |
| 2 | `_create_cross_move_payment` / `_line_vals_move_cross_payment_incoming` (ruta combine) | Usan `move.move_id.payment_id`; en Odoo 19 el campo se renombró a `origin_payment_id` (ver `account.move.origin_payment_id`, `/home/binaural19/odoo/addons/account/models/account_move.py:206`) | Reemplazar por `move.move_id.origin_payment_id` (4 apariciones). Mismo fix ya aplicado en este archivo para `_create_split_account_payment` |
| 3 | `_line_vals_move_cross_incoming`/`_outgoing`/`_payment_incoming` | 6 comparaciones `currency == 3` / `self.env.company.currency_id.id == 3`, asumiendo VEF = id 3 | Reemplazar por `self.foreign_currency_id.id` (related ya existente en `pos.session`, `foreign_currency_id`) |
| 4 | `_line_vals_move_cross_incoming`/`_outgoing`/`_payment_incoming` (los 3, ambas rutas) leían `payment_method.outstanding_account_id` sin validar que existiera | Métodos de pago `cash` **nunca** tienen `outstanding_account_id`: es `invisible="type != 'bank'"` en la vista nativa (`point_of_sale/views/pos_payment_method_views.xml:24`) — Odoo enruta cash directo a la cuenta del diario de caja, sin cuenta transitoria separada. Con `apply_one_cross_move=True` en un método cash, la línea de cruce se creaba con `account_id = NULL`, y Postgres la rechazaba en producción con `account_move_line_check_accountable_required_fields` (encontrado probando con un método real "Efectivo $") | Nuevo helper `_get_cross_transitory_account(payment_method)`: `payment_method.outstanding_account_id or self.company_id.account_default_pos_receivable_account_id` — mismo patrón de fallback que usa el nativo `_get_receivable_account` (`pos_session.py:1660`: `payment_method.receivable_account_id or company.account_default_pos_receivable_account_id`). Usado en las 3 funciones de líneas y en el guard de `_validate_cross_move`/`_create_combine_account_payment` |
| 5 | `_create_cross_move` / `_create_cross_move_payment` (ambas rutas) fijaban `"name": _("PoS Payment Method Adjustment")` al crear el `account.move` | `name` es el campo "Número" (secuencia del diario), no una descripción libre. Al fijarlo con un literal, `_compute_name` nativo (`account_move.py:938`, `move_has_name = move.name and move.name != '/'`) nunca dispara `_set_next_sequence()` — el asiento queda para siempre con el texto fijo en vez del número de secuencia de `cross_account_journal` al postearse (reportado por el usuario tras confirmar varios asientos reales) | Mover el texto a `ref` ("Referencia") y dejar `name` sin asignar en el `create()`. Al postear, Odoo asigna la secuencia normalmente |

Los cinco bugs están confirmados en el código (no son hipótesis) y fueron
verificados línea por línea contra el archivo actual y contra el core de
Odoo 19 en `/home/binaural19/odoo/addons/point_of_sale/` y
`/home/binaural19/odoo/addons/account/`. Los bugs 4 y 5 se descubrieron
durante la verificación manual en producción (ver sección de
verificación), no en la revisión de código inicial — el código legacy
comentado nunca contempló métodos de pago cash para este flujo.

## Decisiones de arquitectura

| Decisión | Elegido | Por qué |
|---|---|---|
| ¿Postear el asiento de cruce automáticamente? | **No** — queda en `draft` | Decisión de negocio confirmada: contabilidad revisa y valida a mano antes de que impacte el mayor |
| ¿Implementar split y combine en el mismo change? | **Sí, ambas** | `split_transactions` (campo nativo) ya decide qué ruta toma cada pago; no es una decisión de alcance sino una necesidad de cobertura completa |
| ¿Dónde enganchar la ruta split? | `action_pos_session_close`, después de `super()` | Los pagos (`pos.payment`) ya existen completos en ese punto; independiente del pipeline de acumuladores de `_create_account_move` |
| ¿Dónde enganchar la ruta combine? | Sin cambio — ya vive dentro de `_create_combine_account_payment` | Esa función ya es invocada por el pipeline nativo (`_create_bank_payment_moves` → `_create_account_move` → `action_pos_session_close`); engancharla aparte duplicaría el disparo |
| ¿Rama "outgoing" (saliente) para combine? | **No se implementa** | El legacy nunca la tuvo; el vuelto siempre se paga en efectivo (cash), no bank combinado. Se documenta como limitación heredada, no como bug nuevo |

## Archivos modificados

| Archivo | Tipo de cambio |
|---|---|
| `src/odoo-venezuela/l10n_ve_pos/models/pos_session.py` | Descomentar y corregir 6 métodos (ver `tasks.md`) |
| `src/odoo-venezuela/l10n_ve_pos/tests/test_pos_session_cross_account_move.py` | Nuevo — 6 casos de test |
| `src/odoo-venezuela/l10n_ve_pos/tests/__init__.py` | Import del nuevo archivo de test |

## Nota (corregida): el `addons_path` del contenedor `proj` NO tiene shadowing

Se investigó inicialmente si `src/custom/19-homologacion-jul-2026-pos`
(primera entrada del `addons_path` de `proj`) hacía sombra a
`src/odoo-venezuela/l10n_ve_pos`. **Verificado que NO es el caso**: Odoo solo
descubre módulos un nivel directo debajo de cada entrada del `addons_path`
(`<entrada>/<modulo>/__manifest__.py`). Dentro de
`19-homologacion-jul-2026-pos`, `l10n_ve_pos` está anidado dos niveles más
profundo (`.../odoo-venezuela/l10n_ve_pos/__manifest__.py`); un
`find -maxdepth 2 -name __manifest__.py` en esa carpeta no devuelve nada, así
que Odoo nunca la registra como fuente de módulos. Esa entrada del
`addons_path` es inerte para efectos de resolución de módulos — `proj`
siempre resolvió `l10n_ve_pos` desde `src/odoo-venezuela`, donde vive este
fix.

Además, el contenedor corre con `--dev=all` (autoreload), así que los
cambios de este change quedaron activos en caliente sin reiniciar nada.

**Verificado en producción** (BD `pos`, método de pago real "Zelle", split):
dos pagos reales generaron dos asientos de cruce independientes en el diario
"Operaciones misceláneas", con las cuentas y montos correctos
(`foreign_debit`/`foreign_credit` coherentes con la tasa de la sesión); al
postearlos manualmente, el saldo de la cuenta real de banco ("Zelle") pasó a
reflejar exactamente la suma de ambos pagos.

## Ajuste de UX: label y help de `apply_one_cross_move`

Durante la verificación manual, el nombre del campo resultó ambiguo (`Apply
One Cross Move` / "Aplicar un único asiento de ajuste" — sonaba a "combinar
todo en un asiento", cuando en realidad es el interruptor on/off del cruce,
independiente de si el método es split o combine). Se corrigió en
`pos_payment_method.py`:

- `string`: `"Enable Automatic Cross-Account Clearing"` (antes "Apply One
  Cross Move"), con su traducción en `i18n/es_VE.po`: "Habilitar cruce
  automático de cuenta transitoria".
- `help` (en inglés, sin traducir a propósito): describe qué se crea, en qué
  diario, cuándo (por pago vs. por sesión según split/combine), y que queda
  en borrador sin afectar saldos hasta ser posteado a mano.

No es un cambio de comportamiento — solo mejora la claridad del campo en la
UI. Requiere `-u l10n_ve_pos` (o reinicio de registro) para que Odoo
sincronice el nuevo `field_description`/`help` y cargue la traducción
actualizada del `.po` — un simple reload de código (`--dev=all`) no
resincroniza traducciones.

## Riesgo de despliegue / migración

Hoy, con el bug de polaridad, cualquier `pos.payment.method` con
`apply_one_cross_move=True` y ambos journals configurados **nunca** dispara
el cruce. Al corregir la polaridad, ese mismo método empezará a generar un
asiento de cruce en cada cierre de sesión donde participe. Antes de
desplegar, auditar en producción:

```python
env["pos.payment.method"].search([
    ("apply_one_cross_move", "=", True),
    ("cross_account_journal", "!=", False),
    ("cross_journal", "!=", False),
])
```

y confirmar con contabilidad si esa configuración (si existe) es intencional
o residual de cuando la función aún operaba en Odoo 17.
