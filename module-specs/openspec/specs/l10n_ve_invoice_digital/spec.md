# l10n_ve_invoice_digital — The Factory HKA Digital Invoicing (Venezuela)

## Purpose

Integrates Odoo's sales invoicing (and vendor retention) flows with The Factory HKA's digital invoicing API for Venezuela. Sales invoices, credit notes and debit notes are digitalized asynchronously through a per-company FIFO queue processed by a cron, so posting never blocks on TFHKA's response; vendor IVA/ISLR retentions are still digitalized synchronously at posting. Covers eligibility rules, the queue's state machine and crash/interruption recovery, order/sequence guards required by TFHKA's strictly-consecutive numbering, multi-currency invoicing, and the supporting journal/sequence/API-log infrastructure.

## Requirements

### Requirement: Digitalization Queue
Eligible sales documents (`out_invoice`, `out_refund`) are queued for digitalization instead of calling TFHKA synchronously at posting. The queue tracks `tfhka_digitalization_state` (`none` / `queued` / `processing` / `success` / `error`) and `tfhka_queued_at` (FIFO ordering).

#### Scenario: Enqueue on posting (normal mode)
- **WHEN** a digital-journal invoice/credit note is posted through `move.action.post.alert.wizard.action_confirm()` and the company is not in "digitalization with payment" mode
- **THEN** `_tfhka_enqueue_eligible_for_digitalization()` queues every move for which `_tfhka_is_eligible_for_digitalization()` is true (not already digitalized, journal is digital, a TFHKA document type can be determined)
- **AND** the move's `tfhka_digitalization_state` becomes `'queued'` with `tfhka_queued_at` set to the current time; nothing is sent to TFHKA inline

#### Scenario: Enqueue via the manual button (payment mode)
- **WHEN** the company has "digitalization with payment" enabled, `action_tfhka_generate_digital()` is the only path to the queue
- **THEN** it validates the previous document is already queued/processing/success, the document type is determinable, and there is no sequence-number gap, all **before** enqueueing — a failed validation never touches `tfhka_digitalization_state`

#### Scenario: Re-posting an already-queued or in-flight document is a no-op
- **WHEN** `_tfhka_enqueue_digitalization()` is called for a move already in `'queued'` or `'processing'`
- **THEN** the move is skipped (its queue position and state are left untouched)

### Requirement: Cron Processing, Per-Company Isolation
A cron (`ir_cron_tfhka_digitalization_queue`, every minute, `numbercall=-1`/`doall=False` so it survives its first run) processes the queue one document at a time per company, never crossing TFHKA's "last number + 1" invariant between companies.

#### Scenario: Oldest-first, one at a time
- **WHEN** the cron runs for a company with queued documents
- **THEN** it picks the oldest by `tfhka_queued_at, id` and calls `generate_document_digital()`, committing after each document so progress is visible immediately

#### Scenario: Shared batch budget across companies
- **WHEN** the cron tick processes multiple companies
- **THEN** `TFHKA_QUEUE_BATCH_SIZE` (200) is a single budget shared across all companies that tick, not a per-company allowance, bounding total work (and HTTP calls) regardless of company count

#### Scenario: One company's error halts only that company's queue
- **WHEN** a document fails digitalization and is marked `'error'`
- **THEN** `_tfhka_process_queue_for_company` refuses to process any further document of that company (ignoring moves in `state='cancel'` when counting errors) until the error is resolved, while every other company's queue keeps advancing

#### Scenario: An unrelated exception in one company doesn't abort the tick
- **WHEN** processing one company raises an exception that is not itself a per-document digitalization failure (e.g. a transient DB error)
- **THEN** `_tfhka_cron_process_queue` catches it, rolls back to clear the aborted-transaction state, logs it, and continues with the remaining companies

### Requirement: Interrupted-Attempt Recovery
A document can be killed mid-flight (e.g. hitting `limit_time_cron` right after TFHKA answered but before Odoo recorded the result). The system must never resend a document TFHKA already has.

#### Scenario: Stuck 'processing' document, successful attempt confirmed by the log
- **WHEN** the cron starts a tick and finds a document still `'processing'` from a previous run
- **THEN** it looks up `tfhka.api.log` for a successful `/Emision` call for that document since its last send attempt (`tfhka_last_attempt_at`, with `TFHKA_CLOCK_SKEW_MARGIN` tolerance)
- **AND** if found, replays `_register_success` from the logged response (never resubmits) and marks the document `'success'`

#### Scenario: Stuck 'processing' document past its grace period, no confirmation
- **WHEN** a document has been `'processing'` for longer than `TFHKA_STUCK_PROCESSING_GRACE_PERIOD` (1 minute) with no matching success log entry
- **THEN** it is marked `'error'` with a message warning that TFHKA's receipt is unconfirmed and a manual retry may submit a duplicate — it is **not** requeued automatically

#### Scenario: Within the grace period, left untouched
- **WHEN** a document has been `'processing'` for less than the grace period and no log confirms it yet
- **THEN** it is left in `'processing'`, and the per-company queue halts for this tick without even checking the error guard (it may still be legitimately in flight)

#### Scenario: Partial write inside a failed attempt is rolled back
- **WHEN** `generate_document_digital()` raises partway through (e.g. TFHKA answers 200 but the response is missing an expected field) after already flipping `is_digitalized` to `True`
- **THEN** the whole attempt runs inside `self.env.cr.savepoint()`, so that partial write is rolled back together with the failure, and the document consistently ends in `'error'` with `is_digitalized` still `False`

### Requirement: Manual Retry Without Duplicate Submission
The "Retry Digitalization" button (visible only when `tfhka_digitalization_state == 'error'`) must not resend a document to TFHKA if an earlier attempt already succeeded there, even though Odoo's own state says `'error'` (e.g. the HTTP response to `/Emision` was lost to a network timeout after TFHKA had already processed the document).

#### Scenario: Prior attempt actually succeeded at TFHKA
- **WHEN** `action_tfhka_retry_digitalization()` runs on a document in `'error'`
- **THEN** it looks up `tfhka.api.log` for a successful `/Emision` response recorded since `tfhka_last_attempt_at`
- **AND** if found, it recovers that result (`_register_success` via the logged response) instead of resubmitting, sets the document to `'success'`, and posts a chatter message explaining the automatic recovery

#### Scenario: No confirmed prior success
- **WHEN** no successful log entry is found for the current attempt
- **THEN** the document is simply re-queued (`'queued'`, error cleared) at its original FIFO position — it is **not** sent through `_tfhka_enqueue_digitalization()`, which would reset `tfhka_queued_at` and send it to the back of the queue behind documents that queued while it was in error

### Requirement: Order and Sequence Guards
TFHKA requires strictly consecutive document numbering; several guards keep Odoo from submitting documents out of order or with an undeterminable type.

#### Scenario: Previous document must already be queued/processing/digitalized
- **WHEN** a document is about to be queued (any mode)
- **THEN** `_tfhka_validate_previous_document_queued()` blocks it if the previous posted document in the same journal/move_type (compared by `name`, which orders correctly across a `sequence_prefix` reset) is not `'queued'`, `'processing'` or `'success'`

#### Scenario: No TFHKA document type determinable
- **WHEN** a document would reach the queue but no TFHKA document type can be derived for it (e.g. a credit note without `reversed_entry_id`)
- **THEN** it is blocked before queueing (manual path, `_tfhka_validate_document_type_determinable`) or silently excluded from automatic enqueueing (`_tfhka_is_eligible_for_digitalization`), since reaching `'queued'` with no way to succeed would wedge the company's queue permanently

#### Scenario: Sales invoicing series misconfiguration doesn't abort normal posting
- **WHEN** `_tfhka_get_document_type_and_series()` raises `UserError` on its own (an invalid sales invoicing series configuration) during automatic eligibility checking inside the posting flow
- **THEN** `_tfhka_is_eligible_for_digitalization` catches it and excludes the move from the queue instead of letting the error abort the whole posting

#### Scenario: Local sequence-number gap in payment mode
- **WHEN** a company has "digitalization with payment" enabled (TFHKA is sent the local `sequence_number` as the document number) and a document's `sequence_number` is not exactly one more than its predecessor's **in the same `sequence_prefix`**
- **THEN** `_tfhka_check_sequence_gap()` blocks it — cross-`sequence_prefix` predecessors (e.g. a yearly reset) are a legitimate reset, not a gap, and are not compared

### Requirement: Payment-Required Digitalization Mode
Companies can require a sales document's payment to be registered before it can be digitalized.

#### Scenario: Cash mode blocks digitalization until paid
- **WHEN** a company has `digitalization_with_payment_tfhka` enabled and `payment_mode_tfhka = 'cash'`
- **THEN** any non-credit-note invoice not yet `'paid'`, `'in_payment'` or `'reversed'` is blocked from digitalization, reported as a single error listing every offending invoice

### Requirement: Multi-Currency Invoicing
Companies can enable dual-currency invoices (VES + USD) with a line-level currency selector.

#### Scenario: Multi-currency becomes mandatory once a USD payment is reconciled
- **WHEN** the payment box is shown and a reconciled payment in USD is detected
- **THEN** `multi_currency_invoice` auto-activates and locks (cannot be unchecked) until that payment is no longer reconciled

#### Scenario: Cannot disable multi-currency while a USD payment is linked
- **WHEN** a write attempts to turn off `multi_currency_invoice` while `show_payment_box` is set and a USD payment is still reconciled
- **THEN** the write is rejected with a validation error

### Requirement: Vendor Retention Digitalization (IVA/ISLR)
Unlike sales documents, vendor IVA/ISLR retentions digitalize synchronously at posting — they were not ported to the async queue by this module.

#### Scenario: Auto-digitalize on posting through the invoice
- **WHEN** a vendor bill with retentions posts via `account.move.action_post()` (which tags the context so `account.retention.action_post()` downstream knows the retention came from the invoice)
- **THEN** each eligible retention (`type_retention` in `iva`/`islr`, not already digitalized, company has TFHKA active) calls `generate_document_digital()` immediately, adopting the local correlative as if the sequence-alert wizard had been confirmed (no one is present to answer it in the automatic flow)

#### Scenario: Annul in TFHKA before cancelling in Odoo
- **WHEN** a digitalized, not-yet-annulled retention is cancelled
- **THEN** the user is routed through `tfhka.annul.wizard` to annul it in TFHKA first (with a reason), which then chains the native Odoo cancellation

### Requirement: Journal and Sequence Configuration Locks
Once a digital journal has real invoices, its TFHKA-relevant configuration can no longer change underneath already-reported documents.

#### Scenario: Cannot disable digital invoicing on a journal with digitalized invoices
- **WHEN** a journal has at least one move with `is_digitalized = True`
- **THEN** turning off `digital_invoice` on that journal is rejected

#### Scenario: Cannot change the series prefix of a sequence already in use
- **WHEN** an `ir.sequence` used as a digital journal's invoice/refund sequence already has invoices created against it
- **THEN** changing its `prefix` is rejected — TFHKA uses that prefix as the invoice series, and changing it would desync the series already reported from the one Odoo keeps using locally

### Requirement: TFHKA API Call Logging
Every HTTP call to TFHKA is logged, independent of the caller's transaction, so it survives a rollback and can be used for crash/duplicate recovery.

#### Scenario: Logged on its own cursor, outside the caller's transaction
- **WHEN** `tfhka.api.client._request` completes a call (success or failure)
- **THEN** the request (sanitized of credentials/tokens) and response are persisted via a separate database cursor with an immediate commit, so a later rollback in the caller never loses the record of what was actually sent

#### Scenario: Old logs are purged
- **WHEN** `ir_cron_purge_tfhka_api_log` runs (daily, `numbercall=-1`/`doall=False`)
- **THEN** log entries older than 3 months are deleted

### Requirement: Status Visibility in the UI
The digitalization state is visible and filterable from the invoice list and form, with the error detail restricted to admins.

#### Scenario: Status column in the invoice list
- **WHEN** viewing the sales invoice list (`out_invoice`/`out_refund`/`out_receipt` context)
- **THEN** a "Digitalization Status" badge column is shown after the document number, color-coded by state, and filterable/groupable (`TFHKA: Error`, `TFHKA: Queued`, group by status)

#### Scenario: Error detail restricted to the admin group
- **WHEN** a document is in `'error'`
- **THEN** the "Retry Digitalization" button is visible to any user, but the `tfhka_digitalization_error` field explaining the failure is only visible to `l10n_ve_invoice_digital.group_l10n_ve_invoice_digital_admin`

### Requirement: Backfill of Pre-Queue Digitalization State
Invoices digitalized before the state machine existed must show a consistent status after upgrading.

#### Scenario: Backfill on module upgrade
- **WHEN** the module upgrades past the version carrying this migration
- **THEN** every move with `is_digitalized = true` and `tfhka_digitalization_state = 'none'` is backfilled to `'success'`, without touching moves already in `'queued'`/`'processing'`/`'error'`
