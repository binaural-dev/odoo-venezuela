/** @odoo-module */

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";

// Redirect the component to use our primary-inherited template.
//
// We could not use `t-inherit-mode="extension"` because the core template
// has two `PriceFormatter` occurrences (one per branch of the
// selected/not-selected t-if/t-else) and `//PriceFormatter position="replace"`
// with multiple matches is unreliable in qweb-inherit — it replaces only
// one of them.
//
// Instead we do a `primary` inherit under a new template name and rebind
// the component to it here.
//
// See:
//  - static/src/overrides/screens/payment_line/payment_line.xml
//  - engram discovery/odoo-19/qweb-inherit-multi-match-trap
PaymentScreenPaymentLines.template = "l10n_ve_pos.PaymentScreenPaymentLines";
