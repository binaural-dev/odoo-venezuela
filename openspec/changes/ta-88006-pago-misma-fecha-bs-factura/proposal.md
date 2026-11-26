## Why

Al pagar desde el wizard de pagos de una factura el mismo día de su fecha, y en otra moneda, los Bs. del pago no coincidían con los Bs. de la factura. Es un hecho aritmético: con la factura y el pago en la misma fecha y tasa, los Bs. del pago son los de la factura y no debe nacer diferencial cambiario.

Se detectó en la matriz de casos de diferencial cambiario (hoja `V3-Matriz_Casos_Diferencial_Cambiario_3x3`, 85 casos). Caso COM/VEN-E01: línea sin IVA de USD 862,07 más IVA 16 % = USD 1.000,00; el pago de USD 1.000,00 el mismo día dejaba un residual de Bs. 1,03 (NC de cliente en ventas, asiento de diferencial en compras), porque las líneas redondeadas suman Bs. 1,03 más que USD 1.000,00 × tasa.

Causas, todas en `l10n_ve_igtf`:

1. `account_payment.py` → `_prepare_move_line_default_vals`: el ajuste del pago exacto el mismo día solo se aplicaba si los Bs. del pago estaban a 0,10 Bs. del residual; con redondeo por línea la diferencia es Bs. 1,03 y el ajuste no corría.
2. `account_payment.py` → `_fix_writeoff_balance` (pago con write-off): mismo criterio estricto en Bs.
3. `account_payment.py` → rama IGTF con write-off: la contrapartida usaba `total_base_residual` (suma de TODAS las facturas, en Bs.) en lugar de `base_residual`, y en pagos salientes el monto en divisa de la línea de IGTF se restaba cuando la línea se suma al balance. Mezclaba unidades: en COM/VEN-C04x y C05x el write-off se llevaba Bs. 856.005,86 y la factura de venta quedaba parcial.
4. `account_move.py` → `compute_bi_igtf` decidía con `payment_state`, que es otro campo almacenado cuyo orden de recálculo cambia entre procesos (semilla de hash de Python). Con el saldo en 0 y `payment_state` aún `not_paid`, `bi_igtf` y `igtf_top_aply` quedaban en 0 y no se recalculaban. Es la causa de que `test12_payment_from_invoice_with_igtf_journal_desconciliation` fallara según la corrida. La copia de `l10n_ve_igtf_note_debit` tenía la misma compuerta.

## What Changes

- Nuevo `_same_date_payment_covers_residual`: el pago del mismo día cubre la deuda si sus Bs. igualan el residual dentro de 0,10 Bs. (criterio histórico) o si el monto del pago iguala el residual convertido a la moneda del pago dentro de una unidad de redondeo de esa moneda. Un pago parcial o excedente no se fuerza. Con fechas distintas se conserva el criterio estricto y el diferencial real.
- `_prepare_move_line_default_vals` y `_fix_writeoff_balance` usan ese criterio solo el mismo día de la factura.
- IGTF con write-off: la contrapartida usa `base_residual` (la factura del pago) y el monto en divisa de la línea de IGTF saliente se suma.
- Nuevo `_igtf_base_is_computable` en `account.move`: se calcula la base con saldo abierto, o con la factura publicada, no revertida y con conciliaciones; ya no se decide por `payment_state`. Se aplica en `l10n_ve_igtf` y en `l10n_ve_igtf_note_debit`.
- Pruebas con `Form`: `test_igtf_same_date_payment_balance.py` (matriz de 21 casos × redondeo por línea/global × IVA incluido/excluido × ventas/compras, más fechas distintas y los casos C04x/C05x) y `test_igtf_bi_igtf_payment_state_order.py`.

## Impact

- **Specs afectadas**: `l10n_ve_igtf` (línea de IGTF del pago, ajuste de balances del wizard, base imponible acumulada) y `l10n_ve_igtf_note_debit` (base del modo nota de débito).
- **Código**: `l10n_ve_igtf/models/account_payment.py`, `l10n_ve_igtf/models/account_move.py`, `l10n_ve_igtf_note_debit/models/account_move.py`. Versiones: `l10n_ve_igtf` 19.0.1.2.25, `l10n_ve_igtf_note_debit` 19.0.1.0.4. Sin migración ni textos nuevos.
- **Qué ve el usuario**: el pago de una factura el mismo día, en otra moneda, la deja pagada con los mismos Bs. de la factura, sin NC/ND ni asiento de diferencial de Bs. 1,03. Con fechas distintas el diferencial real se sigue generando.
- **Lo que no cambia**: pagos con fechas distintas, pagos parciales, la fórmula del IGTF.
- **Datos existentes**: no se recalculan facturas ya cerradas; las que vuelvan a tocarse calculan `bi_igtf` con la compuerta nueva.
- **Fuera de alcance**: la marca «mantener valor alterno» (ajuste 5) y la fecha de la nota con anticipos (D04/D07), y COM-B01 (USD 0,78): son decisiones de negocio pendientes.
