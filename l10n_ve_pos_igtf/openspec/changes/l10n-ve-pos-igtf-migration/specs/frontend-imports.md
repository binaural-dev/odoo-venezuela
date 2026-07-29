# Frontend Imports Specification

## Purpose

Define how `l10n_ve_pos_igtf` JavaScript modules MUST import Odoo 19 `point_of_sale` dependencies and patch the correct model prototypes so the module loads without errors.

## Requirements

### Requirement: PosOrder and PosPayment imports use Odoo 19 paths

The system MUST import `PosOrder` from `@point_of_sale/app/models/pos_order` and `PosPayment` from `@point_of_sale/app/models/pos_payment`.

#### Scenario: Module loads order_model.js

- GIVEN the module is installed in Odoo 19
- WHEN `order_model.js` is parsed
- THEN no import error is raised for the order model dependency
- AND `PosOrder.prototype` is patched with IGTF methods

#### Scenario: Module loads payment_model.js

- GIVEN the module is installed in Odoo 19
- WHEN `payment_model.js` is parsed
- THEN no import error is raised for the payment model dependency
- AND `PosPayment.prototype` is patched with IGTF fields

### Requirement: pos_hook import uses Odoo 19 path

The system MUST import `usePos` from `@point_of_sale/app/hooks/pos_hook`.

#### Scenario: Module loads payment_status.js

- GIVEN the module is installed in Odoo 19
- WHEN `payment_status.js` is parsed
- THEN no import error is raised for `usePos`
- AND the component registers successfully

### Requirement: Patches target Odoo 19 prototypes

The system MUST patch `PosOrder.prototype` and `PosPayment.prototype`. Patching legacy `Order` or `Payment` classes MUST NOT occur.

#### Scenario: Runtime patch verification

- GIVEN the POS frontend is loaded
- WHEN an order and a payment are created
- THEN IGTF methods are available on the order instance
- AND IGTF fields are available on the payment instance
