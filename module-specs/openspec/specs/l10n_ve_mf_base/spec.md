# l10n_ve_mf_base — Fiscal Machine Base Module

## Purpose

Shared foundation for TFHKA fiscal printer integration via Web Serial API. Provides the transport layer (SerialConnection), protocol layer (FiscalProtocol), status parsing (StatusParser), and the high-level driver (TfhkaDriver) used by both POS and Accounting modules.

## Requirements

### Requirement: Serial Connection Transport
The system SHALL provide a Web Serial API transport layer that manages port connection, read/write operations with lock-based concurrency control, and buffer flushing.

#### Scenario: Connect to fiscal printer via Web Serial
- **WHEN** the user selects a serial port and opens it with config (9600 8E1)
- **THEN** the connection is established, port info is captured, and configuration is persisted in localStorage for auto-reconnect

#### Scenario: Send command frame to printer
- **WHEN** a binary frame is passed to `write()`
- **THEN** the frame is written to the serial port with write-lock concurrency control

#### Scenario: Read response with ACK/NAK detection
- **WHEN** a command is sent and `read()` is called with a timeout
- **THEN** the response is read byte by byte until ACK (0x06), NAK (0x15), ETX delimiter, or timeout
- **AND** the readLock is always released in a finally block to prevent deadlocks

#### Scenario: Auto-reconnect on POS startup
- **WHEN** the POS initializes and a previously authorized port exists
- **THEN** the system auto-connects without user interaction

### Requirement: Fiscal Protocol Layer
The system SHALL implement the TFHKA RS-232 binary protocol including frame construction (STX + DATA + ETX + LRC), LRC validation, and status parsing.

#### Scenario: Build command frame
- **WHEN** an ASCII command string is provided
- **THEN** a binary frame is constructed: `STX(0x02) + command + ETX(0x03) + LRC`
- **AND** LRC is calculated as XOR of all bytes between STX and ETX (inclusive)

#### Scenario: Parse printer status (ENQ response)
- **WHEN** a 5-byte ENQ response is received (STX|STS1|STS2|ETX|LRC)
- **THEN** STS1 and STS2 are parsed to determine printer state (waiting, in-transaction, error)
- **AND** LRC is validated as `STS1 ^ STS2 ^ ETX`

#### Scenario: Detect printer states
- **WHEN** STS1 byte is read
- **THEN** 0x40/0x60/0x64 indicates waiting (ready), 0x41/0x61/0x65/0x62/0x42 indicates transaction in progress

### Requirement: TfhkaDriver — High-Level Commands
The system SHALL expose methods for all fiscal printer operations: status query, invoice printing, credit/debit note printing, report X/Z, data queries (S1, S3, S4), and document reprint.

#### Scenario: Print fiscal invoice
- **WHEN** order data is provided with partner, lines, payment_lines, and flag_21 config
- **THEN** the driver builds and sends the full command sequence: RIF, name, header info, items with fiscal codes, subtotal, payment commands, footer, document close
- **AND** reads S1 after printing to obtain the fiscal invoice number and serial

#### Scenario: Multi-payment close strategy (national currency only)
- **WHEN** multiple payment methods are present in the order and none is a foreign-currency (divisa) method (codes 01-19 only)
- **THEN** the driver selects the payment method with the highest amount as the closing method
- **AND** sends `2XX` commands only for non-closing payment methods
- **AND** closes with `1<closing_method>` (matching the Python SDK strategy)
- **AND** `1XX` command failures are treated as non-fatal

#### Scenario: Reprint document by number
- **WHEN** a document type (invoice/refund) and fiscal number are provided
- **THEN** the driver sends the reprint command with the document number zero-padded to 7 digits
- **AND** waits up to 30s for the printer to complete the physical reprint

### Requirement: Command Timeout and Retry
The system SHALL auto-adjust timeouts based on command type and retry up to 3 times with configurable delay.

#### Scenario: Auto-timeout by command type
- **WHEN** no explicit timeout is passed
- **THEN** programming commands (PJ) get 60s, reports (I0X/I0Z) get 30s, close commands (101/199/3) get 15s, others get 5s

#### Scenario: Heavy command delay
- **WHEN** a heavy command (101, 199, 3, 2XX) is sent
- **THEN** a 500ms delay is inserted after write before reading response
- **AND** light commands use a 100ms delay (matching Python SDK time.sleep patterns)

### Requirement: Display Amount Formatting
The system SHALL format monetary amounts intended for human-readable informational lines on the printed ticket (e.g., global discount line) using Venezuelan locale conventions, separately from the protocol-level digit encoding used in payment/amount commands.

#### Scenario: Format amount with thousands separator and decimal comma
- **WHEN** `_formatDisplayAmount(value)` is called with a numeric amount (e.g., 39290.94)
- **THEN** it returns a string with `.` as the thousands separator and `,` as the decimal separator (e.g., `"39.290,94"`)
- **AND** amounts under 1000 have no thousands separator (e.g., `15` → `"15,00"`)
- **AND** this formatting is used exclusively for display text (`iXX` informational lines like `DESC. GLOBAL = X`), never for the raw digit-only protocol fields (`2XX` payment amounts, item prices) which continue using `_formatAmount()`

### Requirement: IGTF (Impuesto a las Grandes Transacciones Financieras) Support
The system SHALL detect foreign-currency (divisa) payment methods and apply the TFHKA-mandated closing sequence required for the printer to calculate and print IGTF, per the TFHKA IGTF manual (v1.1.0, Feb 2022 Gaceta 6.687).

#### Scenario: Classify payment method codes as national vs divisa
- **WHEN** a payment method code is evaluated
- **THEN** codes `01`-`19` are classified as PAGO EN MONEDA NACIONAL (no IGTF)
- **AND** codes `20`-`24` are classified as PAGO EN DIVISAS (triggers IGTF calculation when Flag 50=01 on the printer)

#### Scenario: Detect divisa payment in an order
- **WHEN** `_hasDivisaPayment(payment_lines)` is called
- **THEN** it returns `true` if any payment line has a method code between 20 and 24
- **AND** returns `false` for an empty or undefined payment_lines array

#### Scenario: Close with 199 instead of 1XX when divisa payment is present
- **WHEN** an invoice, credit note, or debit note includes at least one payment method with code 20-24
- **THEN** the driver sends `2<method><amount>` for **all** payment methods (including what would normally be the highest-amount closing method)
- **AND** does **NOT** send any `1<closing_method>` direct-close command
- **AND** relies on the final `199` command (always sent at the end of every fiscal document) to close the transaction with IGTF calculation
- **THIS** matches the TFHKA IGTF manual requirement: "el comando 199 es de uso obligatorio para cerrar todos los documentos fiscales (...) cuando el flag 50 está en 01"

#### Scenario: Read S25 status for current-document IGTF breakdown
- **WHEN** `readS25Data()` is called
- **THEN** the driver sends the `S25` command and parses: subtotal of taxable bases, subtotal of tax, total amount with IGTF, total amount without IGTF, item count, payment count, and document type (0=None, 1=Invoice, 2=Credit Note, 3=Debit Note)
- **AND** computes `igtfAmount` as the difference between total-with-IGTF and total-without-IGTF
- **AND** returns zero values if no fiscal transaction is currently open (S25 is only meaningful mid-transaction)

#### Scenario: IGTF rate already exposed via S3
- **WHEN** `readS3Data()` is called
- **THEN** the response includes an `igtf` object with `type`, `typeLabel`, and `value` (the currently programmed IGTF rate, e.g. 3.00%) parsed from the 4th tax line of the S3 response

#### Scenario: Fiscalizador surfaces IGTF configuration for diagnostics
- **WHEN** an administrator opens the Fiscalizador (Developer Tools → Fiscalizador MF) and clicks "Info IGTF (S3+S25)"
- **THEN** the tool displays the programmed IGTF rate (from S3), the raw system flags (for manual verification of Flag 50/63), the current open-document IGTF breakdown (from S25, if any), and a classification of all S4-programmed payment methods into Nacional (01-19) vs Divisa (20-24)
- **AND** warns if no divisa (20-24) payment methods are programmed on the printer, since foreign-currency collection would then be impossible without reprogramming
