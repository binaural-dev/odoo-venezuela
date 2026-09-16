# Views and Templates Specification

## Purpose

Define how XML views and OWL templates integrate with Odoo 19 core `point_of_sale` structures.

## Requirements

### Requirement: pos_order.xml inherits from Odoo 19 core view

The system MUST reference existing Odoo 19 `point_of_sale` view XML IDs in `pos_order.xml`.

#### Scenario: View validation

- GIVEN the module is installed
- WHEN `pos_order.xml` is loaded
- THEN no missing view-parent error occurs

### Requirement: pos_payment_method.xml adds apply_igtf field

The system MUST add the `apply_igtf` field to the correct payment method form view in Odoo 19.

#### Scenario: Payment method form renders

- GIVEN a user opens a payment method form
- THEN the `apply_igtf` checkbox is visible

### Requirement: pos_payment_views.xml extends Odoo 19 views

The system MUST extend the correct Odoo 19 POS payment tree and form views.

#### Scenario: Payment form renders IGTF fields

- GIVEN a user opens a POS payment form
- THEN `include_igtf`, `igtf_amount`, and `foreign_igtf_amount` are visible

### Requirement: payment_status.xml XPath matches Odoo 19 template

The system MUST use XPath selectors that match the Odoo 19 `PaymentScreenStatus` template structure.

#### Scenario: Status template inheritance loads

- GIVEN the POS payment screen is opened
- WHEN `payment_status.xml` is rendered
- THEN the IGTF status block appears without template error
- AND the original total and change rows remain visible

### Requirement: payment_lines.xml renders IGTF row

The system MUST render an IGTF row in the payment lines template.

#### Scenario: Order with IGTF payment

- GIVEN an order has an IGTF payment line
- WHEN payment lines are rendered
- THEN the IGTF amount row is displayed

#### Scenario: Order without IGTF payment

- GIVEN an order has no IGTF payment lines
- WHEN payment lines are rendered
- THEN the IGTF row is not displayed
