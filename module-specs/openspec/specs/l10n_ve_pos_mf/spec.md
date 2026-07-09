# l10n_ve_pos_mf — Point of Sale Fiscal Machine Integration (Odoo 19)

## Purpose

Integrates TFHKA fiscal printers with Odoo 19 POS via Web Serial API. Handles order validation, fiscal invoice data construction, payment method mapping, and reporting from the POS interface. Odoo 19 differences vs the 17 implementation: offline buffering is delegated to the core POS (IndexedDB + automatic re-sync), the payment validation hook lives in `OrderPaymentValidation`, and all popups use the standard dialog service.

## Requirements

### Requirement: POS Order Validation and Fiscal Data Construction
The system SHALL build fiscal invoice data from POS orders including product lines with fiscal codes, payment lines grouped by method, and global discount proration.

#### Scenario: Build fiscal invoice data from POS order
- **WHEN** a POS order is finalized for fiscal printing
- **THEN** invoice lines are constructed with price_unit, quantity, fiscal_code (from `account.tax.fiscal_code`), and normalized product name
- **AND** payment lines are constructed with `code_fiscal_printer` from `pos.payment.method`
- **AND** global discounts are prorated into individual line prices (Strategy A, no `q-` commands)

#### Scenario: Currency-aware amounts
- **WHEN** the POS currency is VEF/VES
- **THEN** amounts use the base currency (VEF)
- **AND** when the POS uses a foreign currency (e.g., USD), amounts use the foreign currency helpers from `l10n_ve_pos` (`get_foreign_unit_price`, `get_foreign_amount`, `get_foreign_total_with_tax`)

#### Scenario: Credit note detection and affected invoice data
- **WHEN** the order total is negative or any line has `refunded_orderline_id`
- **THEN** the document type is `out_refund` and the original order is resolved via `refunded_orderline_id.order_id` (in-memory record), the LocalOrderHistory (offline), or the `get_order_by_uid` RPC — in that priority order
- **AND** the affected invoice block (`number`, `serial_machine`, `date`) is built from the original order's fiscal data
- **AND** the credit note is rejected when the original order has no `mf_invoice_number`

### Requirement: Payment Validation Flow Hook
The system SHALL intercept the Odoo 19 payment validation flow (`OrderPaymentValidation.finalizeValidation`) to run the fiscal sequence before the order syncs.

#### Scenario: Fiscal print before sync
- **WHEN** the cashier validates a paid order
- **THEN** the global discount is normalized (Strategy A), a network-tolerant accounting dry-run (`validate_order_dry_run` via `sync_from_ui` with SAVEPOINT/ROLLBACK) runs, and the fiscal document prints via Web Serial
- **AND** if fiscal printing fails, the validation is aborted (no sync, order stays payable)
- **AND** if the dry-run fails with a non-network error, a dialog shows the accounting problem and validation is aborted

#### Scenario: Offline handled by the core
- **WHEN** the backend is unreachable after a successful fiscal print
- **THEN** the core Odoo 19 offline mechanism keeps the order pending (IndexedDB) and re-syncs automatically; the fiscal fields travel in `serializeForORM` because pos.order loads all fields (`_load_pos_data_fields` returns `[]`)

### Requirement: Payment Method Configuration
The system SHALL allow configuration of `code_fiscal_printer` on `pos.payment.method` to map Odoo payment methods to TFHKA fiscal codes (01-19 national, 20-24 divisa/IGTF).

#### Scenario: Map POS payment method to fiscal code
- **WHEN** a payment method is configured with `code_fiscal_printer = "01"`
- **THEN** the driver sends payment command `2XX` or closing command `1XX` with that code

#### Scenario: Filter invalid payment methods
- **WHEN** a payment line has no `code_fiscal_printer`
- **THEN** it is excluded from fiscal printing
- **AND** if no valid payment lines remain, the order is rejected with an error message

### Requirement: Navbar Connection Button
The system SHALL provide a connection button in the top-right of the POS navbar (status-buttons area) implemented as an OWL component.

#### Scenario: Connection lifecycle
- **WHEN** the POS loads and `pos.config.access_button_mf` is enabled
- **THEN** the `FiscalPrinterButton` component mounts, silently auto-connects to a previously authorized port, and reflects state via CSS classes (disconnected/connecting/connected/error)
- **AND** clicking while disconnected triggers the Web Serial permission prompt; clicking while connected disconnects
- **AND** the connected driver is exposed globally as `window.fiscalPrinter`

### Requirement: Pending (Unfiscalized) Orders
The system SHALL allow locating and printing synced orders that have no fiscal invoice number.

#### Scenario: UNFISCALIZED filter in Ticket Screen
- **WHEN** the cashier selects the "Pendientes por facturar" filter
- **THEN** synced orders are fetched from the backend with the extra domain `mf_invoice_number = False` and listed (finalized orders without fiscal number)

#### Scenario: Print pending order
- **WHEN** the cashier selects an order without `mf_invoice_number` and clicks "Imprimir pedido pendiente"
- **THEN** the same fiscal data construction and driver flow used at validation time runs
- **AND** on success the fiscal data is persisted via `pos.order.write_mf_invoice_data` (sudo write of readonly fields) and propagated to the linked `account.move`
- **AND** the pending list refreshes (order record reloaded from the server)

#### Scenario: Session close blocked by pending orders
- **WHEN** the cashier attempts "Cerrar sesion e imprimir Z" and unfiscalized orders exist in the session
- **THEN** an error dialog lists up to 10 pending order names, the closing popup closes, and the POS navigates to the Ticket Screen with the UNFISCALIZED filter preselected

### Requirement: POS Fiscal Tools
The system SHALL provide debug and reporting tools accessible from the POS interface.

#### Scenario: Fiscal Debugger popup
- **WHEN** a developer opens the fiscal debugger (DebugWidget → FISCALIZADOR)
- **THEN** raw commands can be sent to the printer and all sent/received frames are logged with timing data

#### Scenario: Report X and Report Z from POS
- **WHEN** the user requests a fiscal report from the closing popup
- **THEN** Report X prints without confirmation
- **AND** Report Z requires explicit user confirmation, then reads S1 and syncs `account.move.report_z` and `pos.session.set_report_z`, and finally continues with the native `confirm()` close flow (cash-difference checks preserved)

#### Scenario: Reprint fiscal document from Ticket Screen
- **WHEN** a cashier selects a previously invoiced order (with `mf_invoice_number`) and clicks "Reimprimir Documento Fiscal"
- **THEN** `TfhkaDriver.reprintDocument()` runs via `window.fiscalPrinter` with the type derived from `order.totalDue >= 0`
- **AND** success/failure is shown via the dialog service (AlertDialog)

### Requirement: POS Config Settings
The system SHALL add fiscal printer settings to `pos.config` (own notebook page in the Odoo 19 form).

#### Scenario: Configure fiscal machine
- **WHEN** the POS config is saved with `serial_machine`, `flag_21`, `has_cashbox`, `access_button_mf`
- **THEN** these values are loaded into the POS (pos.config is fully serialized by the core) and used during fiscal invoice construction

### Requirement: Receipt Screen Fiscal Info
The system SHALL show the fiscal result on the receipt screen.

#### Scenario: Fiscal block on receipt screen
- **WHEN** the printed order has `mf_invoice_number`
- **THEN** the receipt screen shows "Factura Fiscal Impresa" (or "Nota de Crédito Impresa" when `totalDue < 0`) with the fiscal number, machine serial and Z report
