odoo.define("l10n_ve_pos.PartnerListScreen", function(require) {

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
        if (event.code === "Enter" && this.partners.length === 0) {
          try {
            this.env.services.ui.block()
            await this.searchPartner()
            if (this.partners.length === 0) {
              this.createPartner()
            } else {
              this.clickPartner(this.partners[0])
            }
            if (event.code === "Enter" && this.partners.length === 1) {
              this.clickPartner(this.partners[0])
            }
          } catch (error) {
            this.createPartner()
          } finally {
            this.env.services.ui.unblock()

          }
        }
      }

      async createPartner() {
        this.env.services.ui.block()
        try {
          let data = ""
          if (!!this.env.pos.config.pos_search_cne) {
            data = await this.env.services.rpc({
              model: 'res.partner',
              method: 'get_default_name_by_vat_param',
              args: [[], "V", this.state.query],
            });
            if (data === "Esta cédula de identidad no se encuentra inscrito en el Registro Electoral.") {
              data = "N/D"
            }
          }
          // initialize the edit screen with default details about country & state
          this.state.editModeProps.partner = {
            country_id: this.env.pos.company.country_id,
            state_id: this.env.pos.company.state_id,
            vat: this.state.query,
            name: data,
          }
          this.activateEditMode();
        } catch (e) {
          this.env.services.ui.unblock()
          this.state.editModeProps.partner = {
            country_id: this.env.pos.company.country_id,
            state_id: this.env.pos.company.state_id,
          }
          this.activateEditMode();
          return this.showPopup('ErrorPopup', {
            title: _t('Failed connection'),
          });
        }
        this.activateEditMode();
        this.env.services.ui.unblock()
      }

      /*
       *TODO: OVERWRITE BECAUSE DOMAIN IS NOT INHERIT
       */

      async getNewPartners() {
        let domain = [];
        const limit = 30;
        if (this.state.query) {
          domain = ['|', '|', ["name", "ilike", this.state.query + "%"],
            ["vat", "ilike", this.state.query + "%"],
            ["parent_name", "ilike", this.state.query + "%"]];
        }
        const result = await this.env.services.rpc(
          {
            model: 'pos.session',
            method: 'get_pos_ui_res_partner_by_params',
            args: [
              [odoo.pos_session_id],
              {
                domain,
                limit: limit,
                offset: this.state.currentOffset,
              },
            ],
            context: this.env.session.user_context,
          },
          {
            timeout: 3000,
            shadow: true,
          }
        );
        return result;
      }
    }

  Registries.Component.extend(PartnerListScreen, BinauralPartnerListScreen)
  return BinauralPartnerListScreen
})
