import { describe, expect, test } from "@odoo/hoot";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import "@l10n_ve_pos/overrides/screens/partner_list/partner_list";
import "@l10n_ve_pos/overrides/services/pos_store";

function makeList(query, liveValue) {
    return {
        state: { query },
        searchInputRef: liveValue === undefined ? null : { el: { value: liveValue } },
        pos: {
            newPartnerVat: false,
            editPartner: async () => false,
        },
        clickPartner() {},
    };
}

function searchedVat(list) {
    return Object.getOwnPropertyDescriptor(PartnerList.prototype, "searchedVat").get.call(list);
}

describe("l10n_ve_pos PartnerList searched VAT", () => {
    test("an ID number is kept as digits", () => {
        expect(searchedVat(makeList("304050110"))).toBe("304050110");
        expect(searchedVat(makeList(" 30.405.011 "))).toBe("30405011");
        expect(searchedVat(makeList("30-405-011"))).toBe("30405011");
    });

    test("a name or a prefixed number is not a VAT", () => {
        expect(searchedVat(makeList("Juan Pérez"))).toBe(false);
        expect(searchedVat(makeList("V30405011"))).toBe(false);
        expect(searchedVat(makeList(""))).toBe(false);
    });

    test("the live value of the search input wins over the debounced query", () => {
        expect(searchedVat(makeList("3040", "304050110"))).toBe("304050110");
    });

    test("creating leaves the searched VAT in the store", async () => {
        const list = makeList("304050110");
        await PartnerList.prototype.editPartner.call(list);
        expect(list.pos.newPartnerVat).toBe("304050110");
    });

    test("editing a customer does not touch the searched VAT", async () => {
        const list = makeList("304050110");
        await PartnerList.prototype.editPartner.call(list, { id: 7 });
        expect(list.pos.newPartnerVat).toBe(false);
    });
});

describe("l10n_ve_pos PosStore.editPartnerContext", () => {
    test("the searched VAT is the default of the next form only", () => {
        const store = { newPartnerVat: "304050110", config: {} };
        const editPartnerContext = PosStore.prototype.editPartnerContext;
        expect(editPartnerContext.call(store).default_vat).toBe("304050110");
        expect(store.newPartnerVat).toBe(false);
        expect("default_vat" in editPartnerContext.call(store)).toBe(false);
    });
});
