## Why

Tarea 82427 (Flujos restantes POS Operativo). Con la máquina fiscal usada solo desde
Contabilidad (sin PdV), una factura en USD de una compañía en Bs se imprime en dólares:
`account_move._mf_build_invoice_lines` decide por la moneda de la **compañía** y no por la
de la **factura**, y manda `price_unit` tal cual. La MF trabaja siempre en Bs.

## What Changes

- Pendiente de desarrollo en esta rama: líneas y pagos a la MF en Bs cuando la factura
  está en otra moneda.

## Impact

- `l10n_ve_account_mf` (impresión fiscal desde Contabilidad).
