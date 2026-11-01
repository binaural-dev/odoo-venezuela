/** @odoo-module **/

import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";

patch(PartnerList.prototype, {
  /**
   * A customer searched by its ID number is created with that number: the
   * number is left in the store, which puts it in the context of the contact
   * form it opens (see PosStore.editPartnerContext).
   */
  async editPartner(p = false) {
    if (!p) {
      this.pos.newPartnerVat = this.searchedVat;
    }
    return super.editPartner(...arguments);
  },

  /**
   * The search input debounces, so its live value is read first, as onEnter
   * does. Only digits are kept as a VAT: it is the only format res.partner
   * accepts.
   */
  get searchedVat() {
    const query = this.searchInputRef?.el?.value ?? this.state.query ?? "";
    const vat = query.replace(/[\s.-]/g, "");
    return /^\d+$/.test(vat) ? vat : false;
  },
});
