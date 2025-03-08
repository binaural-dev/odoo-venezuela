odoo.define("l10n_ve_pos.PartnerDetailsEdit", function(require) {
  const PartnerDetailsEdit = require("point_of_sale.PartnerDetailsEdit");
  const Registries = require("point_of_sale.Registries");
  const { _t } = require("web.core");
  const { useRef } = owl;

  const BinauralPartnerDetailsEdit = (PaymentScreenStatus) =>
    class BinauralPartnerDetailsEdit extends PaymentScreenStatus {
      setup() {
        super.setup();

        this.nameField = useRef('inputName');

        let countries = this.env.pos.countries;
        let country_ve = countries.filter((country) => country["code"] == "VE")

        if (!this.props.partner.hasOwnProperty("country_id")
          && this.props.partner["country_id"] == false) {
          this.props.partner["country_id"] = [country_ve[0]["id"], country_ve[0]["name"]]
        }
        this.changes = {
          ...this.changes,
          vat: this.props.partner.vat || "",
          prefix_vat: this.props.partner.prefix_vat || "V",
          name: this.props.partner.name || "",
          city_id: this.props.partner.city_id && this.props.partner.city_id[0],
        }
      }

      async onEnter(event) {
        if (event.code === "Enter") {
          let name = await this.searchRif(event.target.value)
          this.nameField.el.value = name
          this.changes.name = name
        }
      }

      async onblur(event) {
        if (this.nameField.el.value == "") {
          let name = await this.searchRif(event.target.value)
          this.nameField.el.value = name
          this.changes.name = name
        }
      }

      async searchRif(rif) {
        let data = ""
        if(!!this.env.pos.config.pos_search_cne){
          data = await this.env.services.rpc({
            model: 'res.partner',
            method: 'get_default_name_by_vat_param',
            args: [[], "V", rif],
          });

          if (data == "Esta cédula de identidad no se encuentra inscrito en el Registro Electoral.") {
            data = "N/D"
          }
        }
        return data
      }
      async saveChanges() {
        let processedChanges = {};
        for (let [key, value] of Object.entries(this.changes)) {
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
          return this.showPopup("ErrorPopup", {
            title: _t("A Customer VAT Is Required"),
          });
        }
        if (
          !processedChanges.phone &&
          this.env.pos.config.validate_phone_in_pos
        ) {
          return this.showPopup("ErrorPopup", {
            title: _t("A phone number is required"),
          });
        }
        if (
          !isValidPhone(processedChanges.phone)
          && this.env.pos.config.validate_phone_in_pos
        ) {
          return this.showPopup("ErrorPopup", {
            title: _t("A valid phone number is required"),
          });
        }
        if (!processedChanges.street) {
          return this.showPopup("ErrorPopup", {
            title: _t("A street is required"),
          });
        }
        if (!processedChanges.country_id) {
          return this.showPopup("ErrorPopup", {
            title: _t("A valid country is required"),
          });
        }
        function isValidPhone(phone) {
          const phoneRegex = /^0[24]\d{9}$/;
          return phoneRegex.test(phone);
        }

        super.saveChanges();
      }
    };

  Registries.Component.extend(PartnerDetailsEdit, BinauralPartnerDetailsEdit);
  return BinauralPartnerDetailsEdit;
});
