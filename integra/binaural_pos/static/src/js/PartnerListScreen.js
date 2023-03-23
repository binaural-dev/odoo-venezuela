odoo.define("binaural_pos.PartnerListScreen", function(require) {

  const PartnerListScreen = require("point_of_sale.PartnerListScreen")
  const Registries = require("point_of_sale.Registries")
  const { _t } = require('web.core');

  const { onMounted } = owl;

  const BinauralPartnerListScreen = (PartnerListScreen) =>
    class BinauralPartnerListScreen extends PartnerListScreen {
      setup() {
        super.setup()
        onMounted(() => {
          this.searchWordInputRef.el.focus()
        })
      }
      async _onPressEnterKey() {
        if (!this.state.query) return;
        const result = await this.searchPartner();

        if (this.partners.length < 1) {
          this.createPartner()
        }
      }

      async createPartner() {

        const data = await this.env.services.rpc({
          model: 'res.partner',
          method: 'get_default_name_by_vat_param',
          args: [[], "V", this.state.query],
        });
        // initialize the edit screen with default details about country & state
        this.state.editModeProps.partner = {
          country_id: this.env.pos.company.country_id,
          state_id: this.env.pos.company.state_id,
          vat: this.state.query,
          name: data,
        }
        this.activateEditMode();
      }
    }

  Registries.Component.extend(PartnerListScreen, BinauralPartnerListScreen)
  return BinauralPartnerListScreen
})
