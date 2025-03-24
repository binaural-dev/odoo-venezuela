/** @odoo-module */

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

// New orders are now associated with the current table, if any.
patch(PartnerDetailsEdit.prototype, {
  setup() {
    super.setup();
    this.intFields = [...this.intFields, "city_id"];
    this.changes = {
      ...this.changes,
      prefix_vat: this.props.partner.prefix_vat || "V",
      city_id: this.props.partner.city_id && this.props.partner.city_id[0],
    }
  },
  saveChanges() {
    const processedChanges = {};
    for (const [key, value] of Object.entries(this.changes)) {
      if (this.intFields.includes(key)) {
        processedChanges[key] = parseInt(value) || false;
      } else {
        processedChanges[key] = value;
      }
    }
    if ((!this.props.partner.vat && !processedChanges.vat) || processedChanges.vat === "") {
      return this.popup.add(ErrorPopup, {
        title: _t("La Cédula o RIF es obligatoria"),
      });
    }
    return super.saveChanges();
  }
})
