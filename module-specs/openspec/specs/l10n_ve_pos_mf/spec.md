# l10n_ve_pos_mf — Point of Sale Fiscal Machine Integration

## Purpose

Integrates TFHKA fiscal printers with Odoo POS via Web Serial API. Handles order validation, fiscal invoice data construction, payment method mapping, offline buffering, and automatic sync. Provides fiscal debug tools, report generation, and systray connection management for the POS interface.

## Requirements

### Requirement: POS Order Validation and Fiscal Data Construction
The system SHALL build fiscal invoice data from POS orders including product lines with fiscal codes, payment lines grouped by method, and global discount proration.

#### Scenario: Build fiscal invoice data from POS order
- **WHEN** a POS order is finalized for fiscal printing
- **THEN** invoice lines are constructed with price_unit, quantity, fiscal_code, and normalized product name
- **AND** payment lines are constructed with `code_fiscal_printer` from `pos.payment.method`
- **AND** global discounts are prorated into individual line prices (Strategy A, no `q-` commands)

#### Scenario: Currency-aware amounts
- **WHEN** the POS currency is VEF/VES
- **THEN** amounts use the base currency (VEF)
- **AND** when the POS uses a foreign currency (e.g., USD), amounts use the foreign currency

#### Scenario: Offline-first order processing
- **WHEN** a POS order is validated
- **THEN** a dry-run validation is attempted first (network-tolerant)
- **AND** fiscal printing always executes regardless of backend connectivity
- **AND** if backend sync fails, the order is stored in LocalOrderBuffer for later retry

### Requirement: Payment Method Configuration
The system SHALL allow configuration of `code_fiscal_printer` on `pos.payment.method` to map Odoo payment methods to TFHKA fiscal codes.

#### Scenario: Map POS payment method to fiscal code
- **WHEN** a payment method is configured with `code_fiscal_printer = "01"`
- **THEN** the driver sends payment command `2XX` or closing command `1XX` with that code

#### Scenario: Filter invalid payment methods
- **WHEN** a payment line has no `code_fiscal_printer`
- **THEN** it is excluded from fiscal printing
- **AND** if no valid payment lines remain, the order is rejected with an error message

### Requirement: Offline Order Buffer
The system SHALL buffer unsynced POS orders in localStorage when backend connectivity is unavailable.

#### Scenario: Store order in offline buffer
- **WHEN** backend sync fails after fiscal printing
- **THEN** the order JSON and fiscal metadata are stored in localStorage under a namespaced key
- **AND** the buffer enforces a maximum of 50 pending orders

#### Scenario: Auto-flush pending orders
- **WHEN** the POS initializes or auto-sync interval fires
- **THEN** pending orders are replayed to the backend in reverse chronological order
- **AND** orders that exceed 5 retry attempts are abandoned

### Requirement: POS Fiscal Tools
The system SHALL provide debug and reporting tools accessible from the POS interface.

#### Scenario: Fiscal Debugger popup
- **WHEN** a developer opens the fiscal debugger
- **THEN** raw commands can be sent to the printer and all sent/received frames are logged
- **AND** the interceptor captures all sendCommand calls with timing data

#### Scenario: Report X and Report Z from POS
- **WHEN** the user requests a fiscal report from the POS interface
- **THEN** Report X prints without confirmation
- **AND** Report Z requires explicit user confirmation due to irreversibility

#### Scenario: Reprint fiscal document from Ticket Screen
- **WHEN** a cashier selects a previously invoiced order in the Ticket Screen (e.g., customer lost their physical receipt) and clicks "Reimprimir Documento Fiscal"
- **THEN** the button is only actionable if the order already has `mf_invoice_number` set (nothing to reprint otherwise, an error popup is shown)
- **AND** it calls `TfhkaDriver.reprintDocument()` directly via the Web Serial connection exposed globally (`window.fiscalPrinter`), not the legacy IoT Box flow
- **AND** the document type (invoice vs credit note) is derived from `order.get_total_with_tax() >= 0`
- **AND** success/failure is shown via popup (InfoPopup/ErrorPopup), consistent with other POS fiscal tools

### Requirement: POS POSConfig Settings
The system SHALL add fiscal printer settings to `pos.config`.

#### Scenario: Configure serial machine
- **WHEN** the POS config is saved with `serial_machine`, `flag_21`, `has_cashbox`
- **THEN** these values are used during fiscal invoice construction

#### Scenario: Auto-sync configuration
- **WHEN** `enable_auto_sync` is enabled on POS config
- **THEN** the POS periodically flushes offline orders at the configured interval
