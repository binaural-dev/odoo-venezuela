/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CurrencyRateBadge } from "@l10n_ve_rate_systray/currency_rate_badge/currency_rate_badge";

registry.category("systray").add(
    "l10n_ve_rate_systray.CurrencyRateSystray",
    { Component: CurrencyRateBadge, props: { wrapperClass: "o_nav_entry" } },
    { sequence: 100 }
);
