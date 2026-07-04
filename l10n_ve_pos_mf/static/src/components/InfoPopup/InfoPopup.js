/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";

export class InfoPopup extends AbstractAwaitablePopup {
    static template = "l10n_ve_pos_mf.InfoPopup";
    static defaultProps = {
        title: _t("Informacion"),
        body: "",
        confirmText: _t("Aceptar"),
    };
}
