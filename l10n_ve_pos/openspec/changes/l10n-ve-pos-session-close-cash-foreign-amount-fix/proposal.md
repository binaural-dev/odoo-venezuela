# Fix: líneas de efectivo "combine" del asiento de cierre de sesión con foreign_debit/foreign_credit en 0 (l10n_ve_pos)

## Why

En la sesión de PdV "Binaural C.A/00043" (`pos.session` id 79), el asiento
de cierre (`POSS/2026/0126`, `account.move` id 288) tenía dos líneas —
"Efectivo Bs" (id 1018) y "Efectivo $" (id 1019), ambas con `debit > 0` —
con `foreign_debit = 0.00` y `foreign_credit = 0.00`. Esto viola la regla
de negocio: toda línea contable en `l10n_ve_pos` debe llevar su
equivalente en moneda fuerte (USD), igual que lleva `debit`/`credit` en
Bs — nunca ambos foreign en cero si el monto real no lo es.

Se confirmó el valor esperado de dos formas independientes:
- La línea "hermana" de cada pago, en el asiento de extracto bancario
  separado que Odoo crea para cada método de pago tipo caja
  (`CSH1/2026/0028` para Efectivo Bs, `CSH2/2026/0026` para Efectivo $),
  sí tenía el `foreign_debit` correcto (2.51 y 42.92 respectivamente, tasa
  737.2321).
- El asiento 288 estaba descuadrado en la columna foreign: total
  `foreign_debit` = 40.75 (solo Zelle) vs total `foreign_credit` = 83.67 —
  faltaban exactamente 42.92, el valor de la línea 1019.

### Causa raíz

`_create_cash_statement_lines_and_cash_move_lines` (`models/pos_session.py`)
llama a `set_foreign_amount_in_line` para cada línea de
`combine_cash_receivable_lines + combine_cash_statement_lines`. El
`combine_cash_receivable_lines` nativo de Odoo 19 se crea **directamente
en el asiento de cierre de la propia sesión** (`self.move_id`), que solo
contiene líneas `asset_receivable` (las cuentas por cobrar de cada método
de pago contra las de las facturas) — la cuenta real de caja/banco de
cada método vive en un asiento de extracto **separado**
(`account.bank.statement.line`).

`set_foreign_amount_in_line` buscaba una línea "contraparte" no-receivable
en el mismo asiento (`other_lines`) y anidaba **toda** la lógica de
escritura — incluido `not_foreign_recalculate = True` — dentro de
`if other_lines:`. Para las líneas del asiento de cierre esa contraparte
nunca existe, así que el método no hacía nada: `not_foreign_recalculate`
nunca se marcaba y la línea quedaba a merced del cómputo automático de
`l10n_ve_accountant` (`_compute_foreign_debit_credit`), que corrió por
primera vez antes de que el asiento tuviera asignado `foreign_inverse_rate`
(eso ocurre después, en `_create_account_move`) y quedó fijo en 0.

### Cómo se reproduce en el PdV

No hace falta la combinación exacta de la sesión 00043 (dos métodos de
efectivo); basta con **un solo** método de pago que cumpla:

1. Diario de tipo Efectivo (`is_cash_count = True`, vía `journal_id.type
   == 'cash'`).
2. "Identificar cliente" / `split_transactions` **desactivado** (modo
   "combine", no "split") — es el modo por defecto de la mayoría de
   métodos de efectivo.
3. `is_foreign_currency = True`, con un monto cobrado lo bastante grande
   para que su conversión a USD no redondee a 0.00 (montos de 1 Bs sí
   redondean a 0.00 legítimamente y no son bug).

Pasos:

1. Punto de Venta → Configuración → Métodos de pago: confirmar que el
   método de efectivo cumple lo anterior.
2. Abrir una sesión de PdV con ese método.
3. Registrar una venta y cobrarla (total o parcialmente) con ese método.
   No hace falta facturar la orden — el bug ocurre en el cierre de
   sesión, no en la ruta de factura.
4. Cerrar la sesión (validar el efectivo y confirmar cierre).
5. Contabilidad → Diario → abrir el asiento de cierre (nombre = nombre de
   la sesión). La línea de ese método de pago muestra `foreign_debit` /
   `foreign_credit` = 0.00 aunque `debit`/`credit` tengan el monto real.
   Comparando contra el asiento de extracto bancario separado del mismo
   método (mismo monto, misma tasa) se ve el valor que debería tener.

## What Changes

- `models/pos_session.py`, método `set_foreign_amount_in_line`: se separa
  el "match" (¿el debit/credit de esta línea corresponde al monto de este
  payment method?) de la sincronización opcional con la línea contraparte.
  Ahora **siempre** se escribe `foreign_debit`/`foreign_credit` y
  `not_foreign_recalculate = True` en `line` cuando hay match, exista o no
  una línea contraparte no-receivable en el mismo asiento. La
  sincronización de `other_line` (cuando sí existe) se mantiene igual que
  antes.

## Impact

- **Capability**: `pos-odoo19-session-accounting` (añade requirement).
- **Módulo**: `l10n_ve_pos`, solo backend
  (`models/pos_session.py::set_foreign_amount_in_line`). Requiere
  reinicio del worker de Odoo para tomar el cambio (no toca vistas ni
  requiere `-u` del módulo, es Python puro sin cambios de schema).
- **Riesgo de despliegue**: bajo — el fix solo agrega una escritura que
  antes se saltaba en silencio; el camino que sí funcionaba (líneas con
  contraparte, ej. estados de cuenta bancarios) queda bit a bit igual.
  Validado con revisión independiente (Opus) contra el código nativo de
  Odoo 19 y el módulo `l10n_ve_accountant`.
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - Data-fix de los 3 asientos ya generados incorrectamente en la sesión
    00043 (líneas 1018, 1019 en 0.00; línea 1020 "De los pagos de
    factura" en `NULL` en vez de 0.00/valor esperado — mismo defecto,
    ruta de `_create_invoice_receivable_lines`, no tocada aquí).
  - El test `test_create_cash_statement_lines_writes_foreign_fields_on_cash_receivable`
    en `tests/test_pos_session_accounting_move_creation.py` sigue marcado
    `@unittest.skip` (Slice C2.3) — sería la cobertura de regresión
    natural para este fix.
  - Caso borde preexistente (no introducido por este fix): dos métodos de
    pago "combine" con el **mismo monto exacto** en la misma sesión
    podrían confundirse entre sí en el matching por `float_compare`, ya
    que este itera todas las líneas combinadas sin filtrar por método. En
    efectivo es benigno (comparten la tasa de sesión), pero queda anotado
    para una futura corrección basada en identidad de línea en vez de
    monto.
