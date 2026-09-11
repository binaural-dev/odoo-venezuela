# Fix: la retención ISLR toma el precio unitario en vez del importe de la línea

## Why

Reportado por Miguel Casanova (cliente Maxcam) vía WhatsApp el 11/09/2026,
ticket TI-15158/#15194 ("Ajustar error base imponible de retenciones ISLR").

Caso de reproducción: orden de compra `P00192`, proveedor Hierros Miranda
C.A. (RIF J-300819000), diario "Facturas de Proveedores Guarenas". Al generar
la factura del proveedor y calcular la retención ISLR, el sistema tomaba el
**precio unitario** de la línea como base imponible en vez del **importe de
la línea** (precio unitario × cantidad, con descuento aplicado).

### Causa raíz

`AccountMoveRetention._get_payment_concepts_from_invoice()`
(`l10n_ve_payment_extension/models/account_move.py`) calcula el monto base
por línea de dos formas distintas según cuántas líneas de la factura tengan
un concepto de pago ISLR asociado (`use_price_unit = len(valid_lines) > 1`):

- **Una sola línea válida**: usa `move_id.tax_totals["base_amount"]` (el
  subtotal de la factura completa) — correcto.
- **Más de una línea válida**: usaba `abs(line.price_unit)` — el precio
  unitario **sin multiplicar por cantidad ni aplicar descuento** — en vez de
  `abs(line.price_subtotal)` (el importe real de la línea).

Con cantidad distinta de 1 o cualquier descuento, el monto base de cada
concepto quedaba mal calculado, generando una retención ISLR incorrecta con
riesgo de incumplimiento fiscal.

Esta lógica es compartida por los dos flujos de creación de retención ISLR
del módulo, así que el bug afectaba a ambos por igual:

- **Manual**: `action_create_islr_from_invoice()` (precarga
  `default_islr_lines` del wizard).
- **Automática**: `auto_create_islr_retention()`.

## What Changes

- `l10n_ve_payment_extension/models/account_move.py`
  - `_get_payment_concepts_from_invoice()`: cuando hay más de una línea con
    concepto de pago ISLR, el monto base por línea pasa de
    `abs(line.price_unit)` a `abs(line.price_subtotal)`.

## Impact

- **Capability**: `islr-retention-base-amount` (nueva).
- **Módulo**: `l10n_ve_payment_extension` (base de Venezuela, no específico
  de Maxcam — el cálculo vive en el módulo de localización, así que el
  fix beneficia a todo cliente con retención ISLR y facturas
  multi-línea, no solo a Maxcam).
- **Alcance real**: solo afecta facturas con **más de una línea con
  concepto de pago ISLR** y cantidad ≠ 1 o descuento ≠ 0. Facturas de una
  sola línea ISLR nunca tuvieron este problema (usan el subtotal total de
  la factura).
- **Riesgo**: bajo. Cambio de una sola expresión, sin tocar el resto del
  flujo de creación de retenciones.
- **Datos existentes**: las retenciones ISLR ya emitidas con esta base mal
  calculada no se corrigen automáticamente por este cambio — es solo un fix
  hacia adelante. Si el cliente necesita corregir retenciones ya
  declaradas, requiere una tarea de corrección de datos histórica aparte.
- **Verificado**: test automatizado `test_16b_...` (dos líneas ISLR con
  cantidad y descuento ≠ 1/0) corrido en contenedor Docker sobre una base de
  datos de prueba descartable; pasa con el fix y falla sin él.
