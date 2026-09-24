import { Component, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { KioskKeyboard } from "@l10n_ve_pos_self_order/app/components/kiosk_keyboard/kiosk_keyboard";

// Same cédula/RIF prefixes as l10n_ve_contact's prefix_vat Selection.
const PREFIX_VAT_OPTIONS = ["V", "E", "J", "G", "P", "C"];
// Cédula (V/E) and RIF (J/G) are digits-only; P (passport)/C are left free.
// Mirrors the server validation in controllers/orders.py (_ve_vat_format_error).
const NUMERIC_PREFIXES = ["V", "E", "J", "G"];

// Venezuelan mobile operator prefixes. Mirrors the server validation in
// controllers/orders.py (_ve_phone_format_error) — keep both lists in sync.
const PHONE_OPERATOR_CODES = ["0412", "0414", "0416", "0422", "0424", "0426"];
// Business format decided for the Kiosk: "<operator code>-<7 digits>", e.g.
// "0414-1234567". Composed client-side and sent as a single string so the
// server (and existing consumers of res.partner.phone) keep seeing one field.
const PHONE_NUMBER_LENGTH = 7;

export class IdentificationPage extends Component {
    static template = "l10n_ve_pos_self_order.IdentificationPage";
    static components = { KioskKeyboard };
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
            // Phone is split as operator code (dropdown) + 7-digit number so it
            // can be validated and composed into "0414-1234567" (see
            // PHONE_OPERATOR_CODES above and phoneValue()).
            phoneCode: "",
            phoneNumber: "",
            // Address (state/municipality dropdowns + street text), only
            // required when the box turns on self_ordering_require_address
            // (models/pos_config.py); always collected on the "create" step.
            stateId: "",
            municipalityId: "",
            street: "",
            // On-screen keyboard (KioskKeyboard): which state field it writes
            // into ("" = hidden) and which layout to show.
            activeField: "",
            keyboardMode: "text",
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

    // Legend shown above the required-fields steps (phone / new contact) so
    // the customer knows which inputs are mandatory before submitting.
    get requiredFieldsLegend() {
        return _t("Fields marked with * are mandatory");
    }

    get phoneNumberPlaceholder() {
        // Phone is required both for a new customer and when completing a
        // missing one on an existing customer (business rule: we register the
        // phone whenever it is not on file).
        return _t("Phone number") + " *";
    }

    get phoneCodeOptions() {
        return PHONE_OPERATOR_CODES;
    }

    get phoneCodePlaceholder() {
        return _t("Code");
    }

    // Composed "<operator code>-<7 digits>" phone, the format saved on
    // res.partner.phone (e.g. "0414-1234567"). Built even with incomplete
    // input so the caller can validate the whole string in one place.
    get phoneValue() {
        return `${this.state.phoneCode}-${this.state.phoneNumber}`;
    }

    // --- Address (state/municipality/street) ---------------------------
    // Optional unless the box turns on self_ordering_require_address.

    get addressRequired() {
        return Boolean(this.selfOrder.config.self_ordering_require_address);
    }

    get statePlaceholder() {
        return this.addressRequired ? _t("State") + " *" : _t("State");
    }

    get municipalityPlaceholder() {
        return this.addressRequired ? _t("Municipality") + " *" : _t("Municipality");
    }

    get streetPlaceholder() {
        return this.addressRequired ? _t("Street") + " *" : _t("Street");
    }

    // res.country.state is loaded for every Self Order mode by the core
    // (pos_self_order._load_self_data_models); restrict to Venezuela since
    // l10n_ve_location's municipalities only make sense for VE states.
    get stateOptions() {
        return (this.selfOrder.models["res.country.state"].getAll() || [])
            .filter((state) => state.country_id?.code === "VE")
            .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    }

    // res.country.municipality is exposed to the Kiosk by this module
    // (models/pos_config.py::_load_self_data_models +
    // models/res_country_municipality.py). Its state_id is a Many2many
    // (l10n_ve_location): a municipality can list more than one state.
    get municipalityOptions() {
        const stateId = this.state.stateId;
        if (!stateId) {
            return [];
        }
        return (this.selfOrder.models["res.country.municipality"].getAll() || [])
            .filter((municipality) =>
                (municipality.state_id || []).some((state) => state.id === stateId)
            )
            .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    }

    // Client-side format check, mirrored server-side
    // (controllers/orders.py::_ve_address_format_error). Returns an error
    // message (already translated) or "" when the address is valid (or the
    // box does not require one).
    addressFormatError(stateId, municipalityId, street) {
        if (!this.addressRequired) {
            return "";
        }
        if (!stateId) {
            return _t("Select the state.");
        }
        if (!municipalityId) {
            return _t("Select the municipality.");
        }
        if (!(street || "").trim()) {
            return _t("Enter the street address.");
        }
        return "";
    }

    get isAddressComplete() {
        return !this.addressFormatError(
            this.state.stateId,
            this.state.municipalityId,
            this.state.street
        );
    }

    onStateChange(ev) {
        this.state.error = "";
        this.state.stateId = ev.target.value ? Number(ev.target.value) : "";
        // The previously picked municipality may not belong to the new state.
        this.state.municipalityId = "";
    }

    onMunicipalityChange(ev) {
        this.state.error = "";
        this.state.municipalityId = ev.target.value ? Number(ev.target.value) : "";
    }

    // Soft (button-disabled) checks — the authoritative validation still runs
    // in onSavePhone/onCreate (and again server-side).
    get isPhoneValueComplete() {
        return !this.phoneFormatError(this.state.phoneCode, this.state.phoneNumber);
    }

    get phoneStepDisabled() {
        return this.state.loading || !this.isPhoneValueComplete;
    }

    get createDisabled() {
        return (
            this.state.loading ||
            !this.state.firstName.trim() ||
            !this.state.lastName.trim() ||
            !this.isPhoneValueComplete ||
            !this.isAddressComplete
        );
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

    // Client-side format check, mirrored server-side
    // (controllers/orders.py::_ve_phone_format_error). Returns an error
    // message (already translated) or "" when the phone is well formed.
    phoneFormatError(code, number) {
        if (!PHONE_OPERATOR_CODES.includes(code)) {
            return _t("Select a valid phone operator code.");
        }
        if (!/^\d+$/.test(number) || number.length !== PHONE_NUMBER_LENGTH) {
            return _t("The phone number must contain exactly 7 digits.");
        }
        return "";
    }

    // Digits-only, capped to 7 — keeps the on-screen/native keyboard from
    // leaving stray characters in a field the kiosk always sends as "code-digits".
    onPhoneNumberInput(ev) {
        this.state.error = "";
        this.state.phoneNumber = ev.target.value.replace(/\D/g, "").slice(0, PHONE_NUMBER_LENGTH);
    }

    // --- On-screen keyboard (KioskKeyboard) -----------------------------
    // The kiosk terminal has no reliable physical/native keyboard, so text
    // fields on this page show KioskKeyboard on focus and write into
    // whichever field is currently active. "field" is the name of a
    // this.state.* string property (firstName/lastName/street/phoneNumber).

    onFieldFocus(field, mode = "text") {
        this.state.activeField = field;
        this.state.keyboardMode = mode;
    }

    onKeyboardKey(key) {
        const field = this.state.activeField;
        if (!field) {
            return;
        }
        this.state.error = "";
        if (key === "backspace") {
            this.state[field] = this.state[field].slice(0, -1);
            return;
        }
        if (key === "clear") {
            this.state[field] = "";
            return;
        }
        if (key === "space") {
            // A space is meaningless in the phone number.
            if (field !== "phoneNumber") {
                this.state[field] += " ";
            }
            return;
        }
        if (field === "phoneNumber") {
            // Numeric mode already limits the layout to digits, but guard
            // here too and enforce the same 7-digit cap as onPhoneNumberInput.
            if (/^\d$/.test(key)) {
                this.state.phoneNumber = (this.state.phoneNumber + key).slice(
                    0,
                    PHONE_NUMBER_LENGTH
                );
            }
            return;
        }
        this.state[field] += key;
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
        const phoneError = this.phoneFormatError(this.state.phoneCode, this.state.phoneNumber);
        if (phoneError) {
            this.state.error = phoneError;
            return;
        }
        const addressError = this.addressFormatError(
            this.state.stateId,
            this.state.municipalityId,
            this.state.street
        );
        if (addressError) {
            this.state.error = addressError;
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
                phone: this.phoneValue,
                state_id: this.state.stateId || false,
                municipality_id: this.state.municipalityId || false,
                street: this.state.street.trim() || false,
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
        const phoneError = this.phoneFormatError(this.state.phoneCode, this.state.phoneNumber);
        if (phoneError) {
            this.state.error = phoneError;
            return;
        }
        this.state.error = "";
        this.state.loading = true;
        try {
            const result = await rpc("/l10n_ve_pos_self_order/kiosk/identify/set_phone", {
                access_token: this.selfOrder.access_token,
                prefix_vat: this.state.prefixVat,
                vat: this.state.vat.trim(),
                phone: this.phoneValue,
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
