## ADDED Requirements

### Requirement: Ajuste de descuento fijo en el desglose por línea en moneda de la compañía

Cuando una línea de factura usa descuento fijo (`discount_fixed`, con el campo nativo `discount` forzado a 0), el sistema DEBE (MUST) calcular el precio unitario y el monto de descuento de `company_currency_line_totals` (`l10n_ve_accountant`) usando el porcentaje de descuento equivalente exacto de `discount_fixed`, no el campo nativo `discount` -- que en este caso vale 0 y daría un precio unitario incorrecto.

#### Scenario: Línea con descuento fijo

- **WHEN** una línea de factura usa `discount_fixed` en una compañía configurada con descuento por monto fijo
- **THEN** `company_currency_line_totals` de esa línea refleja el descuento real aplicado, con `discount_type` en `'amount'`, y el precio unitario reconstruido reproduce el bruto correcto
