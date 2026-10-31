import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";

/**
 * Keeps only the ASCII digits of a value (the letter of a CI/RIF lives in
 * `prefix_vat`, never in `vat`). Same rule as `res.partner._check_vat`.
 *
 * @param {string} value
 * @returns {string}
 */
export function keepVatDigits(value) {
    return (value || "").replace(/\D/g, "");
}

/**
 * CI/RIF (`vat`) of a contact: only digits can be typed or pasted. Any other
 * character (letters, dots, dashes, spaces) is dropped as soon as it reaches
 * the input, so the cashier or the user never has to erase it.
 *
 * The contact form of the PoS is the backend form (l10n_ve_pos renders
 * `base.view_partner_form` in a dialog), so the same widget applies there.
 */
export class VatField extends CharField {
    static template = "l10n_ve_contact.VatField";

    /**
     * Runs before the `input` listener of `useInputField`: Owl binds the
     * template `t-on-input` when it creates the node, and the hook adds its
     * own listener later, in a `useEffect`. So the field is marked dirty (or
     * not) with the value already cleaned.
     *
     * @param {InputEvent} ev
     */
    onVatInput(ev) {
        const input = ev.target;
        const value = input.value;
        const digits = keepVatDigits(value);
        if (digits === value) {
            return;
        }
        // Keep the caret where the user was typing: it moves back as many
        // characters as were dropped before it.
        const caret = input.selectionStart ?? value.length;
        const newCaret = keepVatDigits(value.slice(0, caret)).length;
        input.value = digits;
        input.setSelectionRange(newCaret, newCaret);
    }
}

export const vatField = {
    ...charField,
    component: VatField,
    displayName: _t("CI/RIF (digits only)"),
    supportedTypes: ["char"],
};

registry.category("fields").add("l10n_ve_vat", vatField);
