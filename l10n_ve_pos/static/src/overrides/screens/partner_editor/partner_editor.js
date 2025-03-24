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
		};
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
		if (
			(!this.props.partner.vat && !processedChanges.vat) ||
			processedChanges.vat === ""
		) {
			return this.popup.add(ErrorPopup, {
				title: _t("A Customer VAT Is Required"),
			});
		}
		if (
			!this.props.partner.phone &&
			!processedChanges.phone &&
			this.pos.config.validate_phone_in_pos
		) {
			return this.popup.add(ErrorPopup, {
				title: _t("A phone number is required"),
			});
		}
		if (
			!isValidPhone(
				processedChanges.phone && this.pos.config.validate_phone_in_pos,
			)
		) {
			return this.popup.add(ErrorPopup, {
				title: _t("A valid phone number is required"),
			});
		}
		if (!this.props.partner.street && !processedChanges.street) {
			return this.popup.add(ErrorPopup, {
				title: _t("A street is required"),
			});
		}
		if (!this.props.partner.country_id && !processedChanges.country_id) {
			return this.popup.add(ErrorPopup, {
				title: _t("A valid country is required"),
			});
		}
		function isValidPhone(phone) {
			const phoneRegex = /^0[24]\d{9}$/;
			return phoneRegex.test(phone);
		}
		return super.saveChanges();
	},
});
