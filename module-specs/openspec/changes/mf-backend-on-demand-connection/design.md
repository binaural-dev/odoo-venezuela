## Context

`l10n_ve_mf_base` already implements an on-demand connection model on `TfhkaDriver`: `withConnection(fn)` opens the port, runs `fn`, and closes the port in a `finally`, ref-counted so nested calls reuse one open cycle; `acquireConnection()`/`releaseConnection()` expose the same ref-counted open/close pair for callers that need to hold the port across several discrete operations (an interactive session) instead of one. `l10n_ve_pos_mf` (`pos_app.js`, `ClosePosPopup.js`, `ReprintInvoiceButton.js`, `PrintPendingOrderButton.js`, `FiscalDebuggerPopup.js`) already uses this model exclusively and works correctly.

`l10n_ve_iot_mf`'s backend widgets predate that model. Its `getBackendFiscalPrinter()` singleton comment stated the intent explicitly: "El puerto queda con lock exclusivo mientras la pestaña viva" (the port stays exclusively locked for the tab's lifetime). `ensureConnected()` called `driver.connect()` and never `disconnect()`, and `mf_systray.js` additionally auto-invoked that connect on every backend page mount (`onMounted`) — so simply having a backoffice tab open, without printing anything, silently grabbed and held the fiscal printer's COM port, starving the POS or any other tab of it.

## Goals / Non-Goals

**Goals:**
- Make `l10n_ve_iot_mf`'s backend widgets release the serial port as soon as an operation finishes, matching `l10n_ve_pos_mf`'s proven on-demand model.
- Preserve existing UX (button labels, notifications, confirmation dialogs, chatter logging) — this is a connection-lifecycle fix, not a UI redesign.
- Keep the Fiscalizador dialog responsive (no reconnect per console click) without leaking the port after it closes.

**Non-Goals:**
- Changing the `l10n_ve_mf_base` driver itself (`withConnection`/`acquireConnection`/`releaseConnection` already do what's needed).
- Re-architecting module dependencies — verified separately that `l10n_ve_pos_mf` and `l10n_ve_iot_mf` already depend only on `l10n_ve_mf_base` and not on each other; no change needed there.
- Touching the legacy IoT Box widgets (`l10n_ve_iot_mf/static/src/js/*`) kept for administering physical IoT Box hardware — unrelated to the Web Serial connection lifecycle.

## Decisions

- **One-shot buttons (`mf_webserial_button.js`, `mf_reports_webserial_button.js`) use `withConnection()`.** These are single user-triggered actions (print one document, print one report). Wrapping the whole operation in `withConnection()` is the simplest correct pattern and mirrors `l10n_ve_pos_mf`'s `ClosePosPopup.js`/`ReprintInvoiceButton.js`. Alternative considered: hold the connection open across the button's lifetime like the systray used to — rejected, since it reintroduces the same class of bug (nothing bounds "lifetime" to an actual need for the port).
- **Interactive console (`mf_fiscalizador_dialog.js`) uses `acquireConnection()`/`releaseConnection()`.** It has many small back-to-back actions (status, S1, S4, raw commands) where reconnecting per click would be slow and noisy in the log. This mirrors `l10n_ve_pos_mf`'s `FiscalDebuggerPopup.js` exactly, including releasing in `onWillUnmount`. Alternative considered: `withConnection()` per action — rejected for UX (visible reconnect latency on every click) even though it would be simpler and slightly safer (no reliance on unmount firing).
- **Pairing is split from opening.** New `ensurePaired()` helper only guarantees the device is authorized in this browser (`navigator.serial.getPorts()`, or a connect+disconnect probe if not yet authorized) — it never leaves the port open. Every caller pairs first, then opens via `withConnection()`/`acquireConnection()` for the actual operation. This avoids conflating "is this device known to this browser" with "is the port physically open right now", which was the root confusion in the original code.
- **Systray changes from "connected" to "paired" semantics.** It no longer auto-connects on mount; it polls `getPorts()` (cheap, no port access) every 10s to stay in sync if pairing happens from another tab, and its click handler pairs (if needed) or does a one-shot `withConnection()` status probe (if already paired). This is the change with the most user-visible impact (icon no longer means "port is open"), called out as **BREAKING** in the proposal.

## Risks / Trade-offs

- [Risk] `acquireConnection()`/`releaseConnection()` in the Fiscalizador dialog relies on `onWillUnmount` firing to release the port; if the dialog is destroyed in a way that skips the hook, the port would leak until the next successful `withConnection()`/`acquireConnection()` cycle elsewhere recovers it (those still work independently since the ref-count model is per-driver-instance and TfhkaDriver's own retry/status-check logic tolerates a stale open handle). → Mitigation: same pattern already relied upon in production by `l10n_ve_pos_mf`'s `FiscalDebuggerPopup.js`; no new risk class introduced.
- [Risk] Removing the systray's persistent "connected" indicator changes what the green icon means (paired vs. physically open) — an operator watching for "is it currently talking to the printer" loses that signal. → Mitigation: the click-to-test action still surfaces real-time communication status via notification; documented as a breaking UX change in the proposal instead of silently changed.
- [Trade-off] Every print/report operation now pays the cost of a fresh port open (already the case in the POS today) instead of reusing an already-open handle. → Accepted: TFHKA reconnects are fast (`autoConnect()` needs no user gesture once paired) and this is the same cost the POS has always paid without issue.

## Migration Plan

No data/schema migration needed (pure frontend JS). Deploy as a normal module asset update; browser tabs pick up the new bundle on next reload. Rollback is a plain revert of the five changed files if issues surface in manual browser testing.
