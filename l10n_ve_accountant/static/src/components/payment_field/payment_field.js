/** @odoo-module **/

import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";

/**
 * Core hardcodes `currency_id` to company currency for any `is_exchange`
 * row (`_compute_payments_widget_reconciled_info`, core -- see
 * design-notes.md § widget de Pagos). Our own standalone alt-diff entries
 * are the only rows with BOTH `partial_id === false` and `is_exchange ===
 * true` (native exchange rows always carry a real `partial_id`) -- for
 * those we re-fetch the real alternate-currency amount straight from the
 * entry's closing line and relabel `amount_formatted` with it.
 */
patch(AccountPaymentField.prototype, {
    setup() {
        super.setup();
        // `getInfo()` runs synchronously from the template and can't await
        // an RPC -- results land here, keyed by move_id, so a re-render
        // (triggered by writing to this reactive state) picks them up.
        // First paint uses the default (company-currency) value; the fix
        // lands one render later, with no visible flicker in practice.
        this.l10nVeForeignDiffCache = useState({});
        onWillStart(() => this._loadForeignDiffAmounts(this.props.record.data[this.props.name]));
        onWillUpdateProps((nextProps) =>
            this._loadForeignDiffAmounts(nextProps.record.data[nextProps.name])
        );
    },

    async _loadForeignDiffAmounts(value) {
        const rows = (value && value.content) || [];
        const moveIds = [...new Set(
            rows
                .filter((row) => row.partial_id === false && row.is_exchange === true)
                .map((row) => row.move_id)
        )].filter((moveId) => !(moveId in this.l10nVeForeignDiffCache));
        if (!moveIds.length) {
            return;
        }
        const lines = await this.orm.searchRead(
            "account.move.line",
            [
                ["move_id", "in", moveIds],
                ["account_id.account_type", "in", ["asset_receivable", "liability_payable"]],
            ],
            ["move_id", "foreign_debit", "foreign_credit", "foreign_currency_id"],
        );
        // Mirrors the backend's own `[:1]` pick (`_get_all_reconciled_invoice_partials`):
        // only the first closing line found per move is kept.
        for (const line of lines) {
            const moveId = line.move_id[0];
            if (moveId in this.l10nVeForeignDiffCache) {
                continue;
            }
            this.l10nVeForeignDiffCache[moveId] = {
                amount: Math.abs(line.foreign_debit - line.foreign_credit),
                currencyId: line.foreign_currency_id && line.foreign_currency_id[0],
            };
        }
    },

    getInfo() {
        const info = super.getInfo();
        for (const line of info.lines) {
            if (line.partial_id !== false || line.is_exchange !== true) {
                continue;
            }
            const cached = this.l10nVeForeignDiffCache[line.move_id];
            if (cached && cached.currencyId) {
                line.amount_formatted = formatMonetary(cached.amount, { currencyId: cached.currencyId });
            }
        }
        return info;
    },
});
