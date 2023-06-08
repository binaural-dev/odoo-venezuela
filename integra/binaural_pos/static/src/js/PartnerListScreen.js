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
      async updatePartnerList(event) {
        await super.updatePartnerList(event)
        if(event.code === "Enter" && this.partners.length === 0){
          this.createPartner()
        }
        if(event.code === "Enter" && this.partners.length === 1){
          this.editPartner(this.partners[0])
        }
      }

      async createPartner() {
        let data = await this.env.services.rpc({
          model: 'res.partner',
          method: 'get_default_name_by_vat_param',
          args: [[], "V", this.state.query],
        });
        if (data === "Esta cédula de identidad no se encuentra inscrito en el Registro Electoral."){
          data = "N/D"
        }
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
