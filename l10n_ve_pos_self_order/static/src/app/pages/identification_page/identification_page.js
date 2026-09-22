import { Component, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Same cédula/RIF prefixes as l10n_ve_contact's prefix_vat Selection.
const PREFIX_VAT_OPTIONS = ["V", "E", "J", "G", "P", "C"];
// Cédula (V/E) and RIF (J/G) are digits-only; P (passport)/C are left free.
// Mirrors the server validation in controllers/orders.py (_ve_vat_format_error).
const NUMERIC_PREFIXES = ["V", "E", "J", "G"];

export class IdentificationPage extends Component {
    static template = "l10n_ve_pos_self_order.IdentificationPage";
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        this.state = useState({
            // "identify" = ask for cédula; "create" = cédula not found, ask
            // for the rest of the contact data (cédula stays fixed); "phone" =
            // cédula found but the partner has no phone on file, ask for it.
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

    // Placeholders built from the already-translated base terms plus the
    // required marker appended outside the translatable string, so the "*"
    // never becomes part of the msgid (which would fall back to English).
    get firstNamePlaceholder() {
        return _t("First name") + " *";
    }

    get lastNamePlaceholder() {
        return _t("Last name") + " *";
    }

    get phonePlaceholder() {
        // Phone is required both for a new customer and when completing a
        // missing one on an existing customer (business rule: we register the
        // phone whenever it is not on file).
        return _t("Phone") + " *";
    }

    get numpadKeys() {
        // On-screen numeric keypad laid out as a 3×4 grid: 1-9, then
        // backspace / 0 / clear on the last row.
        return [
            { label: "1", value: "1" },
            { label: "2", value: "2" },
            { label: "3", value: "3" },
            { label: "4", value: "4" },
            { label: "5", value: "5" },
            { label: "6", value: "6" },
            { label: "7", value: "7" },
            { label: "8", value: "8" },
            { label: "9", value: "9" },
            { label: "⌫", value: "backspace", action: true },
            { label: "0", value: "0" },
            { label: "C", value: "clear", action: true },
        ];
    }

    // Client-side format check, mirrored server-side. Returns an error message
    // (already translated) or "" when the cédula/RIF is well formed.
    vatFormatError(prefix, vat) {
        const value = (vat || "").trim();
        if (!value) {
            return _t("Enter the ID number.");
        }
        if (NUMERIC_PREFIXES.includes(prefix) && !/^\d+$/.test(value)) {
            return _t("The ID number must contain only digits.");
        }
        return "";
    }

    onNumpadKey(value) {
        // Feeds the on-screen keypad into the cédula/RIF field so the kiosk
        // does not depend on a physical keyboard.
        this.state.error = "";
        if (value === "backspace") {
            this.state.vat = this.state.vat.slice(0, -1);
        } else if (value === "clear") {
            this.state.vat = "";
        } else {
            this.state.vat += value;
        }
    }

    async onIdentify() {
        const vat = this.state.vat.trim();
        const formatError = this.vatFormatError(this.state.prefixVat, vat);
        if (formatError) {
            this.state.error = formatError;
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
            // Soft error (e.g. rate-limited): show it, do not navigate.
            if (result?.error) {
                this.state.error = result.error;
                return;
            }
            const partner = result?.["res.partner"]?.[0];
            if (partner?.id) {
                if (result.has_phone) {
                    this.assignPartner(result);
                    this.navigateNext();
                } else {
                    // Found but with no phone on file: ask for it before
                    // continuing (the partner is re-fetched server-side by
                    // cédula in set_phone, so nothing to carry here).
                    this.state.step = "phone";
                }
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
        const phone = this.state.phone.trim();
        const formatError = this.vatFormatError(this.state.prefixVat, this.state.vat.trim());
        if (formatError) {
            this.state.error = formatError;
            return;
        }
        if (!firstName) {
            this.state.error = _t("Enter the first name.");
            return;
        }
        if (!lastName) {
            this.state.error = _t("Enter the last name.");
            return;
        }
        if (!phone) {
            this.state.error = _t("Enter the phone number.");
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
                phone,
            });
            if (result?.error) {
                this.state.error = result.error;
                return;
            }
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

    async onSavePhone() {
        const phone = this.state.phone.trim();
        if (!phone) {
            this.state.error = _t("Enter the phone number.");
            return;
        }
        this.state.error = "";
        this.state.loading = true;
        try {
            const result = await rpc("/l10n_ve_pos_self_order/kiosk/identify/set_phone", {
                access_token: this.selfOrder.access_token,
                prefix_vat: this.state.prefixVat,
                vat: this.state.vat.trim(),
                phone,
            });
            if (result?.error) {
                this.state.error = result.error;
                return;
            }
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
        // Only forward the res.partner records — the response also carries
        // scalar keys (has_phone/error) that are not models.
        const payload = { "res.partner": result["res.partner"] };
        this.selfOrder.data.synchronizeServerDataInIndexedDB(payload);
        const connectedData = this.selfOrder.models.connectNewData(payload);
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
        if (this.state.step === "create" || this.state.step === "phone") {
            // Step back to the cédula screen without losing what was typed.
            this.state.step = "identify";
            this.state.error = "";
            return;
        }
        this.router.navigate("default");
    }
}
