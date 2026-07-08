# POS Odoo 19 Order/Payment Serialization Specification

## Purpose

Define how `l10n_ve_pos` migrates order, payment, and order-line serialization from Odoo 17 `_order_fields`, `_payment_fields`, and `_export_for_ui` to Odoo 19 patterns.

## Requirements

### Requirement: Inventory and map serialization overrides

The migration plan MUST list every override of `_order_fields`, `_payment_fields`, and `_export_for_ui` in `l10n_ve_pos` and in blocked downstream modules, and map each to the corresponding Odoo 19 serialization hook.

#### Scenario: Serialization inventory is complete

- GIVEN the gap-analysis table
- WHEN the reviewer inspects `pos_order.py`, `pos_payment.py`, and `pos_order_line.py`
- THEN every old serialization method is listed with its Odoo 19 replacement

#### Scenario: Downstream serialization is covered

- GIVEN the list of blocked downstream modules
- WHEN the reviewer checks the mapping table
- THEN any downstream `_export_for_ui` or `_order_fields` override is also mapped

### Requirement: Preserve order foreign-currency fields

The plan MUST specify how `pos.order` fields `foreign_amount_total` and `foreign_currency_rate` are populated from the UI order and exposed back to the UI.

#### Scenario: Order creation preserves foreign total

- GIVEN a UI order containing `foreign_amount_total` and `foreign_currency_rate`
- WHEN the migrated order creation path is executed
- THEN the resulting `pos.order` record stores both values

#### Scenario: Existing order reload preserves foreign rate

- GIVEN a saved `pos.order` with a foreign currency rate
- WHEN the order is reloaded in the POS UI
- THEN the UI payload includes `foreign_currency_rate`

### Requirement: Preserve payment foreign-currency fields

The plan MUST specify how `pos.payment` fields `foreign_amount` and `foreign_rate` are serialized between UI and backend.

#### Scenario: Payment line from UI preserves foreign amount

- GIVEN a UI payment line with `foreign_amount` and `foreign_rate`
- WHEN the order is created from the UI
- THEN the `pos.payment` record stores both values

#### Scenario: Payment UI reload shows foreign amount

- GIVEN a saved payment with foreign amount
- WHEN the payment is exported for the UI
- THEN the payload contains `foreign_amount` and `foreign_rate`

### Requirement: Preserve order-line foreign-currency fields

The plan MUST specify how `pos.order.line` fields `foreign_price` and `foreign_currency_rate` are exposed to and received from the UI.

#### Scenario: Order line UI payload includes foreign price

- GIVEN an order line with `foreign_price`
- WHEN the line is serialized for the UI
- THEN the payload contains `foreign_price` and `foreign_currency_rate`

#### Scenario: Refund preserves foreign price

- GIVEN a refund order line created from an original line
- WHEN the refund data is prepared
- THEN `foreign_price` is copied to the refund line

### Requirement: Define serialization verification scenarios

The plan MUST include automated-test scenarios for order creation, refund, and order reload.

#### Scenario: End-to-end serialization check

- GIVEN a multi-currency order with one payment and one line
- WHEN the order is created and then reloaded
- THEN all foreign-currency fields survive the round trip
