# Frontend API Wrappers Specification

## Purpose

Define thin compatibility wrappers that expose Odoo 17 method names on the Odoo 19 `PosOrder` patch so existing IGTF logic continues to function without silent failures.

## Requirements

### Requirement: get_paymentlines wrapper returns payment_ids

The system MUST provide `get_paymentlines()` on `PosOrder.prototype` that returns `this.payment_ids`.

#### Scenario: Order with one payment

- GIVEN an order has one payment line
- WHEN `order.get_paymentlines()` is called
- THEN it returns an array containing that payment line

#### Scenario: Order with no payments

- GIVEN an order has no payment lines
- WHEN `order.get_paymentlines()` is called
- THEN it returns an empty array

### Requirement: get_total_with_tax wrapper returns total due

The system MUST provide `get_total_with_tax()` on `PosOrder.prototype` that returns `this.totalDue` with a safe fallback when the getter is unavailable.

#### Scenario: Active order total

- GIVEN an active order has lines totaling 100 and no IGTF
- WHEN `order.get_total_with_tax()` is called
- THEN it returns the order's total due amount

### Requirement: get_due wrapper returns remaining due

The system MUST provide `get_due()` on `PosOrder.prototype` that returns `this.remainingDue` with a safe fallback when the getter is unavailable.

#### Scenario: Unpaid order

- GIVEN an order with total due 100 and 0 paid
- WHEN `order.get_due()` is called
- THEN it returns 100

### Requirement: add_paymentline wrapper delegates to Odoo 19 method

The system MUST provide `add_paymentline(method)` on `PosOrder.prototype` that calls `this.addPaymentline(method)`.

#### Scenario: Adding a payment line

- GIVEN a payment method is available
- WHEN `order.add_paymentline(method)` is called
- THEN a new payment line is added via the Odoo 19 API

### Requirement: select_paymentline wrapper delegates to Odoo 19 method

The system MUST provide `select_paymentline(line)` on `PosOrder.prototype` that calls `this.selectPaymentline(line)`.

#### Scenario: Selecting a payment line

- GIVEN an order has multiple payment lines
- WHEN `order.select_paymentline(line)` is called
- THEN the specified line becomes the selected payment line
