# POS Odoo 19 Frontend Specification

## Purpose

Define how `l10n_ve_pos` re-enables its OWL/JS foreign-currency patches after the Odoo 19 data-loading and serialization migration.

## Requirements

### Requirement: Inventory frontend patches

The migration plan MUST list every JS/OWL override in `l10n_ve_pos/static/src/overrides/` and `static/src/app/components/full_refund/` that depends on foreign-currency data, and identify the backend field or serialization hook that feeds it.

#### Scenario: Frontend patch inventory is complete

- GIVEN the static source tree
- WHEN the reviewer compares it with the plan
- THEN each override file appears in the inventory with its affected component and required backend fields

#### Scenario: Deleted or moved patch is flagged

- GIVEN a frontend file that no longer loads after migration
- WHEN the inventory is reviewed
- THEN the file is marked with a remediation action

### Requirement: Ensure backend fields feed the frontend

The plan MUST verify that every foreign-currency field consumed by the frontend is supplied by the data-loading and serialization slices.

#### Scenario: Payment screen has foreign amount

- GIVEN the payment screen override
- WHEN the reviewer traces `foreign_amount` and `is_foreign_currency`
- THEN the plan shows they are loaded by Slice 1 and serialized by Slice 2

#### Scenario: Order summary has foreign total

- GIVEN the order summary override
- WHEN the reviewer traces `get_foreign_total_with_tax`
- THEN the plan shows it depends on order-line `foreign_price` from Slice 2

### Requirement: Schedule frontend as Slice 4

The plan MUST schedule frontend re-enablement after data loading (Slice 1), serialization (Slice 2), and session accounting (Slice 3).

#### Scenario: Frontend slice has correct predecessors

- GIVEN the task list
- WHEN the reviewer checks dependencies
- THEN the frontend slice depends on the completion of Slice 2

### Requirement: Define frontend regression scenarios

The plan MUST specify UI tests covering VES/USD display, payment entry, ticket screen, receipt, and refund.

#### Scenario: Payment screen shows foreign amount

- GIVEN a payment line on a foreign-currency method
- WHEN the cashier views the payment screen
- THEN the foreign amount and local amount are both visible

#### Scenario: Ticket screen shows foreign totals

- GIVEN a synced order with foreign-currency lines
- WHEN the cashier opens the ticket screen
- THEN foreign total and tax are displayed

#### Scenario: Refund preserves foreign values in UI

- GIVEN a refund initiated from a foreign-currency order
- WHEN the refund order is displayed
- THEN foreign prices and totals match the original order
