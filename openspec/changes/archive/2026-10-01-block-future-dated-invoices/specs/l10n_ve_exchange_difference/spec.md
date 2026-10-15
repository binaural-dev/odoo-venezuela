## ADDED Requirements

### Requirement: La ND/NC de diferencial no se bloquea por la fecha futura de un pago

La ND/NC de diferencial toma como fecha (`invoice_date`, `invoice_date_display`, `date`) la fecha del pago. Al confirmarla, el sistema DEBE (MUST) pasar el contexto `l10n_ve_skip_future_date_check=True` a `action_post()`, de modo que el guard de `l10n_ve_invoice` que impide confirmar documentos con fecha futura no se aplique a esta nota. Un pago con fecha futura NO DEBE (MUST NOT) fallar dentro de la conciliación con un error de fecha de documento que el usuario no puede relacionar con el pago.

#### Scenario: Pago con fecha futura sobre factura en divisa

- **WHEN** se registra un pago con fecha posterior a hoy sobre una factura en divisa y se genera la ND/NC de diferencial
- **THEN** la nota se confirma con la fecha del pago, sin el error de fecha futura

#### Scenario: Tests de aislamiento de tasas

- **WHEN** los tests de esta capa necesitan fechas sin tasas propias
- **THEN** usan fechas pasadas (años 2000-2019), no futuras, para no chocar con el guard de fecha futura de `l10n_ve_invoice`

#### Scenario: Fixtures de test independientes de otros módulos

- **WHEN** los tests de esta capa necesitan un diario de banco en la moneda de la compañía
- **THEN** solo reutilizan uno existente si su método de pago entrante tiene `payment_account_id`; de lo contrario crean el suyo, para no depender de diarios de la plantilla contable (p. ej. al instalar `account_asset`)

#### Scenario: Reversión por el wizard estándar

- **WHEN** una nota de diferencial se revierte con el wizard estándar
- **THEN** la reversión no debe tener `invoice_date` (tasa) posterior a su `invoice_date_display`; el test usa la misma fecha de la nota original
