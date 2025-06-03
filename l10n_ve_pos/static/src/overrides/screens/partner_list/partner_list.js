/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

// New orders are now associated with the current table, if any.
patch(PartnerListScreen.prototype, {
  async updatePartnerList(event) {
    await super.updatePartnerList(event)
    if (event.code === "Enter" && this.partners.length === 0) {
      this.env.services.ui.block()
      await this.searchPartner()
      if (this.partners.length === 0) {
        this.createPartner()
      } else {
        this.clickPartner(this.partners[0])
      }
      this.env.services.ui.unblock()
    }
    if (event.code === "Enter" && this.partners.length === 1) {
      this.clickPartner(this.partners[0])
    }
  },
  createPartner() {
    const { country_id, state_id } = this.pos.company;
    this.state.editModeProps.partner = {
      country_id,
      state_id,
      lang: session.user_context.lang,
      vat: this.state.query,
    };
    this.activateEditMode();
  }
})
