import { Component, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Same cédula/RIF prefixes as l10n_ve_contact's prefix_vat Selection.
const PREFIX_VAT_OPTIONS = ["V", "E", "J", "G", "P", "C"];

export class IdentificationPage extends Component {
    static template = "l10n_ve_pos_self_order.IdentificationPage";
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        this.state = useState({
            // "identify" = ask for cédula; "create" = cédula not found, ask
            // for the rest of the contact data (cédula stays fixed).
            step: "identify",
            prefixVat: "V",
            vat: "",
            firstName: "",
            lastName: "",
            phone: "",
            loading: false,
            error: "",
        });
    }

    get prefixOptions() {
        return PREFIX_VAT_OPTIONS;
    }

    async onIdentify() {
        const vat = this.state.vat.trim();
        if (!vat) {
            this.state.error = _t("Enter the ID number.");
            return;
        }
        this.state.error = "";
        this.state.loading = true;
        try {
            const result = await rpc("/l10n_ve_pos_self_order/kiosk/identify", {
                access_token: this.selfOrder.access_token,
                prefix_vat: this.state.prefixVat,
                vat,
            });
            const partner = result?.["res.partner"]?.[0];
            if (partner?.id) {
                this.assignPartner(result);
                this.navigateNext();
            } else {
                // Not found: move to the creation step keeping the typed cédula.
                this.state.step = "create";
            }
        } finally {
            this.state.loading = false;
        }
    }

    async onCreate() {
        const firstName = this.state.firstName.trim();
        const lastName = this.state.lastName.trim();
        if (!firstName) {
            this.state.error = _t("Enter the first name.");
            return;
        }
        this.state.error = "";
        this.state.loading = true;
        try {
            // res.partner.name is a single Char (l10n_ve_contact); concatenate
            // the two UX inputs into one name at creation time.
            const name = [firstName, lastName].filter(Boolean).join(" ");
            const result = await rpc("/l10n_ve_pos_self_order/kiosk/identify/create", {
                access_token: this.selfOrder.access_token,
                prefix_vat: this.state.prefixVat,
                vat: this.state.vat.trim(),
                name,
                phone: this.state.phone.trim(),
            });
            const partner = result?.["res.partner"]?.[0];
            if (!partner?.id) {
                return;
            }
            this.assignPartner(result);
            this.navigateNext();
        } finally {
            this.state.loading = false;
        }
    }

    assignPartner(result) {
        // Same wiring the native PresetInfoPopup uses to attach a partner to
        // the current order: persist, connect into the local models, assign.
        this.selfOrder.data.synchronizeServerDataInIndexedDB(result);
        const connectedData = this.selfOrder.models.connectNewData(result);
        const partner = connectedData["res.partner"][0];
        this.selfOrder.currentOrder.partner_id = partner;
    }

    navigateNext() {
        // Same criterion as LandingPage.start(): presets first if any.
        if (this.selfOrder.hasPresets() && !this.selfOrder.currentOrder.preset_id) {
            this.router.navigate("location");
        } else {
            this.router.navigate("product_list");
        }
    }

    onClickBack() {
        if (this.state.step === "create") {
            // Step back to the cédula screen without losing what was typed.
            this.state.step = "identify";
            this.state.error = "";
            return;
        }
        this.router.navigate("default");
    }
}
