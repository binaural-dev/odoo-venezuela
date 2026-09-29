/** @odoo-module **/

import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";
import { _t } from "@web/core/l10n/translation";
import { localization } from "@web/core/l10n/localization";
import { patch } from "@web/core/utils/patch";
import { usePopover } from "@web/core/popover/popover_hook";
import { Component, useRef, useState } from "@odoo/owl";

const CONTEXT_KEY = "l10n_ve_partial_paid_amount";

/**
 * Small popover asking for the amount to apply, shown when the user clicks
 * "Add" on an outstanding advance/credit line.
 */
class L10nVePartialPaymentPopover extends Component {
    static props = { "*": { optional: true } };
    static template = "l10n_ve_partial_payment.PartialPaymentAmountPopover";

    setup() {
        this.inputRef = useRef("l10nVePaidAmountInput");
        this.state = useState({ error: "" });
    }

    /**
     * Read the typed amount, validate it against the available balance, and
     * delegate to the caller-provided handler.
     *
     * An empty input applies the full available amount (same as clicking
     * "Add" without this module installed). A typed amount greater than
     * what's available is rejected client-side instead of silently clamped,
     * so the user notices instead of getting less than what they asked for.
     */
    onApplyClick() {
        const inputEl = this.inputRef.el;

        // A number input blanks its `.value` on anything it can't parse
        // (typed or pasted), so an empty value alone can't tell "left blank
        // on purpose" apart from "typed something invalid". `validity.badInput`
        // does: it's only set in the latter case.
        if (inputEl.validity.badInput) {
            this.state.error = _t("Enter a valid amount.");
            return;
        }

        const rawValue = inputEl.value.trim();
        const available = this.props.amount;
        const paidAmount = rawValue === "" ? available : parseFloat(rawValue);

        if (isNaN(paidAmount) || paidAmount <= 0) {
            this.state.error = _t("Enter an amount greater than zero.");
            return;
        }

        if (paidAmount > available) {
            this.state.error = _t("The amount can't exceed the available balance.");
            return;
        }

        this.state.error = "";
        this.props._onOutstandingCreditAssign(this.props.lineId, this.props.moveId, paidAmount);
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

        // Single source of truth on the server (company flag + group) --
        // see account_move.py:can_apply_partial_payment. Without this check
        // here, a disabled/unauthorized click would still show the amount
        // input and silently apply the full amount on submit, which is
        // confusing even though it's not incorrect (the server gate in
        // js_assign_outstanding_line holds either way).
        const allowed = await this.orm.call(
            this.props.record.resModel,
            "can_apply_partial_payment",
            [info.moveId]
        );
        if (!allowed) {
            return this.assignOutstandingCredit(info.moveId, line.id);
        }

        this.l10nVePartialPaymentPopover.open(anchorEl, {
            title: _t("Enter the amount to apply"),
            lineId: target.id,
            moveId: info.moveId,
            amount: target.amount,
            amountFormatted: target.amount_formatted,
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
