import { describe, expect, getFixture, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import {
    clickSave,
    defineModels,
    editSelectMenu,
    fieldInput,
    fields,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

import { keepVatDigits, VatField } from "@l10n_ve_contact/fields/vat_field/vat_field";

// l10n_ve_contact depends on account, so mail is always installed: the form
// needs mail's mock models (its services ask for discuss.channel and others).
class ResPartner extends mailModels.ResPartner {
    prefix_vat = fields.Selection({
        selection: [
            ["V", "V"],
            ["E", "E"],
            ["J", "J"],
            ["G", "G"],
            ["P", "P"],
            ["C", "C"],
        ],
        default: "V",
    });
    vat = fields.Char();
}

defineModels({ ...mailModels, ResPartner });

const ARCH = `
    <form>
        <field name="name"/>
        <field name="prefix_vat"/>
        <field name="vat" widget="l10n_ve_vat"/>
    </form>`;

/** Mounts a new contact form and returns the vat sent to the server on save. */
async function mountPartnerForm() {
    const saved = {};
    onRpc("res.partner", "web_save", ({ args }) => {
        saved.vat = args[1].vat;
    });
    await mountView({ type: "form", resModel: "res.partner", arch: ARCH });
    return saved;
}

describe("l10n_ve_contact CI/RIF widget (ticket 16093)", () => {
    test("typed letters never reach the input nor the record", async () => {
        const saved = await mountPartnerForm();

        await fieldInput("vat").edit("12a3B4ñ", { confirm: false });
        expect(".o_field_widget[name=vat] input").toHaveValue("1234");

        await clickSave();
        expect(saved.vat).toBe("1234");
    });

    test("a pasted CI/RIF keeps only its digits", async () => {
        const saved = await mountPartnerForm();

        await fieldInput("vat").edit("V-12.345.678 ", { instantly: true, confirm: false });
        expect(".o_field_widget[name=vat] input").toHaveValue("12345678");

        await clickSave();
        expect(saved.vat).toBe("12345678");
    });

    test("the passport prefix also takes digits only", async () => {
        const saved = await mountPartnerForm();

        await editSelectMenu(".o_field_widget[name='prefix_vat'] input", { value: "P" });
        await fieldInput("vat").edit("AB98765", { confirm: false });
        expect(".o_field_widget[name=vat] input").toHaveValue("98765");

        await clickSave();
        expect(saved.vat).toBe("98765");
    });

    test("a letter typed alone leaves the field as it was", async () => {
        await mountPartnerForm();
        await fieldInput("vat").edit("1234", { confirm: false });
        await clickSave();

        await fieldInput("vat").fill("x", { confirm: false });
        await animationFrame();
        expect(".o_field_widget[name=vat] input").toHaveValue("1234");
        expect(".o_form_status_indicator_buttons").not.toBeVisible();
    });

    test("the numeric keypad is requested on touch devices", async () => {
        await mountPartnerForm();
        expect(".o_field_widget[name=vat] input").toHaveAttribute("inputmode", "numeric");
    });
});

describe("l10n_ve_contact VatField.onVatInput", () => {
    test("keeps the caret where the user was typing", () => {
        const input = document.createElement("input");
        getFixture().append(input);
        // "12x|34": the "x" was just typed after "12", the caret is behind it.
        input.value = "12x34";
        input.setSelectionRange(3, 3);

        VatField.prototype.onVatInput.call({}, { target: input });

        expect(input.value).toBe("1234");
        expect(input.selectionStart).toBe(2);
        expect(input.selectionEnd).toBe(2);
    });

    test("leaves a digits-only value untouched", () => {
        const input = document.createElement("input");
        getFixture().append(input);
        input.value = "1234";
        input.setSelectionRange(1, 1);

        VatField.prototype.onVatInput.call({}, { target: input });

        expect(input.value).toBe("1234");
        expect(input.selectionStart).toBe(1);
    });
});

describe("l10n_ve_contact keepVatDigits", () => {
    test("drops everything that is not an ASCII digit", () => {
        expect(keepVatDigits("J-40.123.456-7")).toBe("401234567");
        expect(keepVatDigits(" 12 34 ")).toBe("1234");
        expect(keepVatDigits("١٢٣")).toBe("");
        expect(keepVatDigits("")).toBe("");
        expect(keepVatDigits(undefined)).toBe("");
        expect(keepVatDigits(null)).toBe("");
    });
});
