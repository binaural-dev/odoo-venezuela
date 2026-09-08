# l10n_ve_suggested_amount

## Purpose

Agrega al asistente de registro de pagos (`account.payment.register`) un monto sugerido de pago para el caso de tres monedas distintas: la factura está en una moneda extranjera, el pago se hace en otra moneda distinta, y ambas difieren de la moneda base de la compañía. Extiende únicamente el wizard `account.payment.register`. Depende de `account` y `l10n_ve_accountant`.

## Requirements

### Requirement: Monto sugerido solo con tres monedas distintas

El campo computado `suggested_custom_amount` (Monetary en la moneda de pago `currency_id`) de `account.payment.register` DEBE (MUST) calcularse únicamente cuando la moneda del documento (`source_currency_id`), la moneda de pago (`currency_id`) y la moneda base de la compañía (`company_currency_id`) son las tres distintas entre sí; en cualquier otro caso DEBE (MUST) valer `0.0`. La vista del asistente muestra el campo solo cuando su valor es distinto de `0.0`.

#### Scenario: Tres monedas distintas

- **WHEN** se registra un pago en una moneda distinta a la de la factura y ambas difieren de la moneda base de la compañía
- **THEN** `suggested_custom_amount` contiene el monto sugerido convertido a la moneda de pago

#### Scenario: Pago en la moneda de la factura o en la moneda base

- **WHEN** la moneda de pago coincide con la moneda de la factura o con la moneda base de la compañía
- **THEN** `suggested_custom_amount` es `0.0` y el campo no se muestra en el asistente

### Requirement: Fórmula de conversión según la fecha de pago

El cálculo de `suggested_custom_amount` DEBE (MUST) elegir la ruta de conversión según la fecha: si la fecha de pago (`payment_date`, o la fecha actual si no está establecida) coincide con la fecha de la factura de la primera línea (`move_id.invoice_date`, o la fecha de la línea en su defecto), convierte el residual en moneda de la compañía (`source_amount`) desde `company_currency_id` hacia la moneda de pago; si difiere, o si no puede determinarse la fecha de la factura (asistente sin líneas o sin fecha), convierte el residual en moneda original (`source_amount_currency`) desde `source_currency_id` hacia la moneda de pago. Ambas conversiones usan `_convert` con la compañía y la fecha de pago.

#### Scenario: Pago en la misma fecha de la factura

- **WHEN** la fecha de pago es igual a la fecha de la factura
- **THEN** el monto sugerido es `source_amount` convertido de la moneda base de la compañía a la moneda de pago a la fecha de pago

#### Scenario: Pago en fecha posterior

- **WHEN** la fecha de pago difiere de la fecha de la factura
- **THEN** el monto sugerido es `source_amount_currency` convertido de la moneda original de la factura a la moneda de pago a la fecha de pago
