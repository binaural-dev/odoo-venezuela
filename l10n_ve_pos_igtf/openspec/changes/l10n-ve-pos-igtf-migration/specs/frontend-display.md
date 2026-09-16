# Frontend Payment Status Display Specification

## Purpose

Define how the POS payment status screen displays IGTF breakdown, base imponible, and foreign amounts in Odoo 19.

## Requirements

### Requirement: igtfAmount getter returns formatted IGTF

The system MUST expose an `igtfAmount` getter that returns the IGTF amount formatted as currency.

#### Scenario: Order with IGTF

- GIVEN an order with IGTF amount 3
- WHEN the payment status renders
- THEN the IGTF line shows the formatted value 3.00

### Requirement: biAmount getter returns formatted base imponible

The system MUST expose a `biAmount` getter returning the base imponible formatted as currency.

#### Scenario: Order with IGTF

- GIVEN an order subtotal of 100 and IGTF 3
- WHEN the payment status renders
- THEN the base imponible shows 100.00

### Requirement: foreignIgtfAmount getter returns formatted foreign IGTF

The system MUST expose a `foreignIgtfAmount` getter returning the IGTF amount in foreign currency.

#### Scenario: Foreign IGTF payment

- GIVEN an order with local IGTF 105 and rate 35
- WHEN the payment status renders
- THEN the foreign IGTF shows 3.00 USD

### Requirement: isIgtf detects IGTF payment methods

The system MUST determine whether a payment line is IGTF-eligible via `payment_method_id.apply_igtf`.

#### Scenario: IGTF payment line

- GIVEN a payment line whose method has `apply_igtf` true
- WHEN `isIgtf` is evaluated
- THEN it returns true

#### Scenario: Non-IGTF payment line

- GIVEN a payment line whose method has `apply_igtf` false
- WHEN `isIgtf` is evaluated
- THEN it returns false

### Requirement: formatCurrency uses Odoo 19 signature

The system MUST call `formatCurrency(value)` without a second format-type argument.

#### Scenario: Render totals

- GIVEN a total value of 100
- WHEN the component formats it
- THEN it calls `formatCurrency(100)` and succeeds
- AND no `'Product Price'` string is passed as a second argument

### Requirement: formatIgtfAmount works with Odoo 19 models

The system MUST format IGTF amounts using Odoo 19 `payment_method_id` and `amount` properties.

#### Scenario: Payment line IGTF amount

- GIVEN a payment line with IGTF amount 3 and foreign IGTF amount 0.09
- WHEN `formatIgtfAmount()` runs
- THEN it returns correctly formatted local and foreign IGTF strings
