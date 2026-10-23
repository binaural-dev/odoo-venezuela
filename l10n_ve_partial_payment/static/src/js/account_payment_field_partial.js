/** @odoo-module **/

import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";
import { _t } from "@web/core/l10n/translation";
import { getCurrency } from "@web/core/currency";
import { localization } from "@web/core/l10n/localization";
import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";
import { usePopover } from "@web/core/popover/popover_hook";
import { formatMonetary } from "@web/views/fields/formatters";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { KeepLast } from "@web/core/utils/concurrency";
import { Component, onMounted, onWillDestroy, useRef, useState } from "@odoo/owl";

const CONTEXT_KEY = "l10n_ve_partial_paid_amount";

/**
 * Decide what "Apply" would do for the amount input's current raw text:
 * either the exact ``{amount, remaining}`` pair it would submit/preview, or
 * the error it would show instead.
 *
 * Shared by the popover's live preview (the "Remaining payment balance"
 * line) and its "Apply" button, so the two can never disagree about what a
 * given input state means -- both call this with the same inputs.
 *
 * @param {Object} params
 * @param {string} params.rawValue - trimmed text currently in the amount input.
 * @param {boolean} params.badInput - ``input.validity.badInput`` at read
 *   time. A number input blanks its ``.value`` on anything it can't parse,
 *   so an empty ``rawValue`` alone can't tell "left blank on purpose" apart
 *   from "typed something invalid" -- ``badInput`` does.
 * @param {number} params.available - available balance of the outstanding
 *   line being applied (the payment/credit side, i.e. ``target.amount``).
 * @param {number} params.invoiceResidual - invoice's own pending balance
 *   (``abs(amount_residual)``); a separate ceiling from ``available``, since
 *   either one can be the smaller of the two depending on the case.
 * @param {number} params.suggestedAmount - pre-filled suggestion (the
 *   lesser of ``available``/``invoiceResidual``), used when the input is
 *   left/cleared empty.
 * @param {number} params.digits - currency decimal precision to round to.
 * @param {number} [params.igtfRate=0] - IGTF percentage charged ON TOP of the
 *   amount and consumed from the same advance (0 when no IGTF applies, in
 *   which case the result is identical to the one without IGTF support).
 * @returns {{ok: true, amount: number, igtf: number, total: number, remaining: number}
 *   | {ok: false, error: string}}
 */
export function computePartialPaymentAmount({
    rawValue,
    badInput,
    available,
    invoiceResidual,
    suggestedAmount,
    digits,
    igtfRate = 0,
}) {
    if (badInput) {
        return { ok: false, error: _t("Enter a valid amount.") };
    }

    const trimmed = (rawValue ?? "").trim();
    const amount = trimmed === "" ? suggestedAmount : parseFloat(trimmed);

    if (isNaN(amount) || amount <= 0) {
        return { ok: false, error: _t("Enter an amount greater than zero.") };
    }

    if (amount > available) {
        return { ok: false, error: _t("The amount can't exceed the available balance.") };
    }

    if (amount > invoiceResidual) {
        return { ok: false, error: _t("The amount can't exceed the invoice's pending balance.") };
    }

    const roundedAmount = roundDecimals(amount, digits);
    // Client-side IGTF estimate (the server value overrides it when it
    // arrives): the IGTF goes on top of the amount and is consumed from the
    // same advance.
    const igtf = igtfRate ? roundDecimals((roundedAmount * igtfRate) / 100, digits) : 0;
    const total = roundDecimals(roundedAmount + igtf, digits);
    return {
        ok: true,
        amount: roundedAmount,
        igtf,
        total,
        // Client-side estimate only, good enough for a live preview: exact
        // in the simple case (invoice and payment share a currency, no
        // IGTF involved), but can read slightly differently than what the
        // server actually applies for an advance routed through an IGTF
        // journal, or a genuine multi-currency pair -- the server does the
        // exact computation there (account_move.py:js_assign_outstanding_line
        // / l10n_ve_igtf._create_advance_payment_move); reproducing that
        // here would mean re-implementing fiscal calculation in JS, out of
        // scope for this preview. Clamped at zero: independently rounding
        // `amount` and this subtraction can otherwise print a cent-sized
        // negative (e.g. "-0.01") right at the boundary where the typed
        // amount equals `available`.
        remaining: Math.max(0, roundDecimals(available - total, digits)),
    };
}

/**
 * Small popover asking for the amount to apply, shown when the user clicks
 * "Add" on an outstanding advance/credit line.
 */
class L10nVePartialPaymentPopover extends Component {
    static props = { "*": { optional: true } };
    static template = "l10n_ve_partial_payment.PartialPaymentAmountPopover";

    setup() {
        this.orm = useService("orm");
        this.inputRef = useRef("l10nVePaidAmountInput");
        // Only the raw, uninterpreted input state: `computePartialPaymentAmount`
        // is the single place that turns this into an amount/error. An
        // empty `rawValue` here (the initial state) is indistinguishable
        // from "not touched yet", which is harmless: the pure function
        // already treats empty the same way the input itself starts out,
        // i.e. as `suggestedAmount` (see `onMounted` below).
        // `igtfPreview` holds the server's last `preview_advance_igtf`
        // response (or `null`) -- a server-side concern, deliberately
        // separate from the client-only `computePartialPaymentAmount`
        // estimate above. It is NOT cleared while typing (avoids flicker):
        // it is only used while its `requested` matches the current amount.
        this.state = useState({ rawValue: "", badInput: false, error: "", igtfPreview: null });

        // `KeepLast` drops any in-flight response once a newer request is
        // issued, so fast typing can never let a stale RPC overwrite the
        // alert with outdated numbers.
        this._keepLastIgtfPreview = new KeepLast();
        this._destroyed = false;
        onWillDestroy(() => {
            this._destroyed = true;
        });

        this._requestIgtfPreviewDebounced = useDebounced(
            (amount) => this._requestIgtfPreview(amount),
            300
        );

        onMounted(() => {
            const inputEl = this.inputRef.el;
            // Plain numeric text, never the currency-formatted string: it
            // has to stay parseable by the same `parseFloat` the pure
            // function above uses. Set imperatively, once, here -- never
            // via `t-att-value`/component state. A `t-att-value` binding
            // would make OWL rewrite `input.value` on every re-render, and
            // for a `type="number"` input that wipes out whatever the user
            // is mid-typing as soon as it passes through a momentarily
            // invalid state (e.g. "12." briefly reports `value === ""` and
            // `validity.badInput === true` in Chrome).
            inputEl.value = String(this.props.suggestedAmount);
            inputEl.focus();
            inputEl.select();
            // The input is pre-filled with `suggestedAmount` on open (never
            // actually blank), so a user who applies without typing anything
            // should still see the IGTF warning if it applies -- preview it
            // once up front, same as a real keystroke would.
            this._requestIgtfPreviewDebounced(this.props.suggestedAmount);
        });
    }

    /**
     * Call the server's read-only IGTF preview for `amount` and store the
     * result in `state.igtfPreview`.
     *
     * Never awaited by the "Apply" button -- this is purely advisory and
     * must not block/delay submitting the popover.
     *
     * @param {number} amount
     */
    async _requestIgtfPreview(amount) {
        if (!this.props.igtfApplies) {
            return;
        }
        if (!amount || amount <= 0) {
            this.state.igtfPreview = null;
            return;
        }
        let result;
        try {
            result = await this._keepLastIgtfPreview.add(
                this.orm.call("account.move", "preview_advance_igtf", [
                    this.props.moveId,
                    this.props.lineId,
                    amount,
                ])
            );
        } catch {
            // Advisory-only: a failed/aborted preview request must never
            // surface as an error to the user, nor block "Apply".
            return;
        }
        // The popover can be closed/destroyed while this RPC is in flight
        // (e.g. the user clicked "Apply" or dismissed it) -- never write to
        // reactive state after that point.
        if (this._destroyed) {
            return;
        }
        this.state.igtfPreview = result && result.applies ? result : null;
    }

    get digits() {
        return getCurrency(this.props.currencyId)?.digits?.[1] ?? 2;
    }

    /** Formatted suggested amount, used only as the input's placeholder. */
    get suggestedAmountFormatted() {
        return formatMonetary(this.props.suggestedAmount, { currencyId: this.props.currencyId });
    }

    /** What "Apply" would do for the input's current text (see the pure function). */
    get resolvedAmount() {
        return computePartialPaymentAmount({
            rawValue: this.state.rawValue,
            badInput: this.state.badInput,
            available: this.props.amount,
            invoiceResidual: this.props.invoiceResidual,
            suggestedAmount: this.props.suggestedAmount,
            digits: this.digits,
            igtfRate: this.props.igtfApplies ? this.props.igtfRate : 0,
        });
    }

    /**
     * Server preview, only while it refers to the amount currently resolved
     * (a stale response for a previous amount is ignored, not cleared).
     */
    get currentIgtfPreview() {
        const preview = this.state.igtfPreview;
        const resolved = this.resolvedAmount;
        if (!this.props.igtfApplies || !preview || !resolved.ok) {
            return null;
        }
        const tolerance = 0.5 * Math.pow(10, -this.digits);
        return Math.abs(preview.requested - resolved.amount) < tolerance ? preview : null;
    }

    /**
     * IGTF breakdown for the informational block (``null`` when IGTF doesn't
     * apply or the input is invalid): client estimate, overridden by the
     * server value when available.
     */
    get igtfBreakdown() {
        const resolved = this.resolvedAmount;
        if (!this.props.igtfApplies || !resolved.ok) {
            return null;
        }
        const preview = this.currentIgtfPreview;
        return {
            applied: preview ? preview.applied_to_invoice : resolved.amount,
            igtf: preview ? preview.igtf : resolved.igtf,
            total: preview ? preview.total_consumed : resolved.total,
        };
    }

    get igtfLabel() {
        return _t("IGTF (%(rate)s%)", { rate: roundDecimals(this.props.igtfRate, 2) });
    }

    formatAmount(value) {
        return formatMonetary(value, { currencyId: this.props.currencyId });
    }

    /**
     * Text for the "Remaining payment balance" preview line: exactly what
     * "Apply" would submit right now, or an em-dash when the current input
     * would be rejected (see `computePartialPaymentAmount`). With IGTF, the
     * balance is the available amount minus the TOTAL consumed (amount +
     * IGTF), using the server value when it exists.
     */
    get remainingPreview() {
        const resolved = this.resolvedAmount;
        if (!resolved.ok) {
            return "—";
        }
        let remaining = resolved.remaining;
        const breakdown = this.igtfBreakdown;
        if (breakdown) {
            remaining = Math.max(
                0,
                roundDecimals(this.props.amount - breakdown.total, this.digits)
            );
        }
        return formatMonetary(remaining, { currencyId: this.props.currencyId });
    }

    /**
     * Human-readable warning for the server's shortfall (``""`` while
     * there's nothing to warn about / no matching response yet).
     */
    get igtfShortfallMessage() {
        const preview = this.currentIgtfPreview;
        if (!preview || !preview.shortfall) {
            return "";
        }
        const currencyId = preview.currency_id;
        return _t(
            "This advance doesn't have enough balance left over to also cover its IGTF: only %(realApplied)s will actually be applied to the invoice, instead of the %(requested)s entered.",
            {
                realApplied: formatMonetary(preview.applied_to_invoice, { currencyId }),
                requested: formatMonetary(preview.requested, { currencyId }),
            }
        );
    }

    /**
     * Track the input's raw text/validity as the user types. Never writes
     * back to `inputEl.value`: this component's input is intentionally
     * uncontrolled (see `onMounted`).
     */
    onAmountInput(ev) {
        this.state.rawValue = ev.target.value;
        this.state.badInput = ev.target.validity.badInput;
        this.state.error = "";
        // The previous server preview is kept (no flicker) but ignored while
        // it doesn't match the typed amount (see `currentIgtfPreview`);
        // an invalid amount drops it.
        const resolved = this.resolvedAmount;
        if (resolved.ok) {
            this._requestIgtfPreviewDebounced(resolved.amount);
        } else {
            this.state.igtfPreview = null;
        }
    }

    /**
     * Validate the typed amount with `computePartialPaymentAmount` and
     * delegate to the caller-provided handler.
     *
     * Reads `inputRef.el` directly rather than `this.state`, so this stays
     * correct even for a value `onAmountInput` never saw (e.g. browser
     * autofill restoring a previous entry without dispatching `input`).
     *
     * An empty input applies the pre-filled suggested amount (the lesser of
     * the available balance and the invoice's own pending balance), not the
     * full available balance: unlike before this module had a live preview,
     * the input is never actually blank on open -- `onMounted` pre-fills it
     * with that same suggested amount, so "left empty" here really means
     * "cleared it back out on purpose".
     */
    onApplyClick() {
        const inputEl = this.inputRef.el;
        const resolved = computePartialPaymentAmount({
            rawValue: inputEl.value.trim(),
            badInput: inputEl.validity.badInput,
            available: this.props.amount,
            invoiceResidual: this.props.invoiceResidual,
            suggestedAmount: this.props.suggestedAmount,
            digits: this.digits,
            igtfRate: this.props.igtfApplies ? this.props.igtfRate : 0,
        });

        if (!resolved.ok) {
            this.state.error = resolved.error;
            return;
        }

        this.state.error = "";
        this.props._onOutstandingCreditAssign(this.props.lineId, this.props.moveId, resolved.amount);
    }
}

// Coexists with l10n_ve_igtf's own patch() on the same component (both call
// super.setup() and add disjoint methods, so patches chain cleanly).
patch(AccountPaymentField.prototype, {
    setup() {
        super.setup();
        this.l10nVePartialPaymentPopover = usePopover(L10nVePartialPaymentPopover, {
            position: localization.direction === "rtl" ? "bottom" : "left",
        });
    },

    /**
     * Open the amount popover for a given outstanding line.
     *
     * Resolves the line via ``this.getInfo()`` (derived by the core from
     * ``this.props.name``), so this works for both
     * ``invoice_outstanding_credits_debits_widget`` and
     * ``invoice_outstanding_credits_debits_widget_advance_payment`` fields.
     *
     * @param {Event} ev - click event on the "Add" link.
     * @param {Object} line - line data from the template's ``t-foreach``.
     */
    async popoverPartialOutstanding(ev, line) {
        // Odoo recycles/detaches the synthetic event once this handler
        // yields on the first `await`, so `ev.currentTarget` reads back
        // `null` after that point -- capture the anchor element now.
        const anchorEl = ev.currentTarget;
        const info = this.getInfo();
        const target = info.lines.find((candidate) => candidate.id === line.id);
        if (!target) {
            return;
        }

        // Single round-trip to the server for everything the popover needs:
        // the gate (company flag + group, see
        // account_move.py:get_partial_popover_data), whether an IGTF is
        // charged on top, and the suggested amount (which, with IGTF, is
        // the largest amount that fits in the advance together with its IGTF).
        // Plain args: [ids, line_id] (nesting them in another array is a bug).
        const popoverData = await this.orm.call(
            this.props.record.resModel,
            "get_partial_popover_data",
            [info.moveId, line.id]
        );
        if (!popoverData.allowed) {
            return this.assignOutstandingCredit(info.moveId, line.id);
        }

        // `target.currency_id` -- the outstanding line's own currency (the
        // same one `amount_formatted` above was built with), NOT
        // `this.props.record.data.currency_id`: on the invoice record that's
        // a `{id, display_name}` object in Odoo 19, not a plain id.
        const currencyId = target.currency_id;
        const invoiceResidual = Math.abs(this.props.record.data.amount_residual);
        const suggestedAmount = popoverData.suggested_amount;

        this.l10nVePartialPaymentPopover.open(anchorEl, {
            title: _t("Enter the amount to apply"),
            lineId: target.id,
            moveId: info.moveId,
            amount: target.amount,
            amountFormatted: target.amount_formatted,
            invoiceResidual,
            suggestedAmount,
            igtfApplies: popoverData.igtf_applies,
            igtfRate: popoverData.igtf_rate,
            currencyId,
            _onOutstandingCreditAssign: this._onOutstandingCreditAssign.bind(this),
        });
    },

    /**
     * Call ``js_assign_outstanding_line`` with the typed amount in context.
     *
     * @param {number} lineId - outstanding ``account.move.line`` id.
     * @param {number} moveId - invoice ``account.move`` id.
     * @param {number} paidAmount - amount typed by the user.
     */
    async _onOutstandingCreditAssign(lineId, moveId, paidAmount) {
        this.l10nVePartialPaymentPopover.close();
        await this.orm.call(
            this.props.record.resModel,
            "js_assign_outstanding_line",
            [moveId, lineId],
            { context: { [CONTEXT_KEY]: paidAmount } }
        );
        await this.props.record.model.root.load();
    },
});
