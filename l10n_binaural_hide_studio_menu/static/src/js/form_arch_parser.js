/** @odoo-module */

import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { StudioSystray } from "@web_studio/systray_item/systray_item";
import { onMounted, onRendered } from "@odoo/owl";


const systrayRegistry = registry.category("systray");
const studioItem = systrayRegistry.get("StudioSystrayItem");
const always_block = ["account.action_move_out_invoice_type"];


patch(ControlPanel.prototype, {

    setup() {

        super.setup();
        this.orm = useService("orm");
        this.user = useService("user"); 
        let action_id = this.env.config ? this.env.config.actionId : false;

        onMounted(() => {
            if (action_id) {
                this.fetchModelName(this.orm,action_id);
            }
        });

        onRendered(() => {
            if (action_id) {
                this.fetchModelName(this.orm,action_id);
            }
        });
        
    },

    async fetchModelName(orm,actionId) {

        let action = await orm.read("ir.actions.act_window", [actionId], ["res_model", "name", "xml_id"]);
        let actionData = action[0];
        let xmlId = actionData.xml_id ? actionData.xml_id : null;
        let hasPermission = await this.user.hasGroup("l10n_binaural_hide_studio_menu.binaural_show_studio_menu");
        let remove = true

    
        if (xmlId) {

            if (xmlId && always_block.includes(xmlId)){
                remove = true

            }

            if (hasPermission){
                if (xmlId && !always_block.includes(xmlId)){
                    remove = false
                } 

            } else {
                remove = true
            }
            
        } 

    


        this.env.bus.trigger("studio_visibility_change", { visible: remove });
    }

});


if (studioItem) {

    patch(studioItem.Component.prototype, {
        setup() {
            super.setup();
            this.user = useService("user"); 
            this.hasPermission = false
            this.get_permision_user().then(hasPermission => {
                this.hasPermission = hasPermission;
            });


            this.env.bus.addEventListener("studio_visibility_change", (ev) => {
                this.isCustomVisible = ev.detail.visible;
                if (this.rootRef.el) { 
                    if (this.isCustomVisible) {
                        if (!this.rootRef.el.classList.contains("o_disabled")) {
                            this.rootRef.el.classList.add("o_disabled");
                        }
                    } else {
                        if (this.rootRef.el.classList.contains("o_disabled")) {
                            this.rootRef.el.classList.remove("o_disabled");
                        }
                    }
                }
            });

            this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", (ev) => {
                this.isLoading = false;
                const mode = ev.detail;

                if (this.hasPermission) {
                    this.isLoading = false;
                    if (mode !== "new" && this.rootRef.el) {
                        
                        this.rootRef.el.classList.toggle("o_disabled", this.buttonDisabled);

                    }
                    
                } else {
                    this.isLoading = true;
                    if (mode !== "new" && this.rootRef.el) {
                        this.rootRef.el.classList.toggle("o_disabled", this.buttonDisabled);
                    }
                    
                }

            });

        },
        async get_permision_user(){
            let hasPermission = await this.user.hasGroup("l10n_binaural_hide_studio_menu.binaural_show_studio_menu");
            return hasPermission;
        }

    });
} else {
    console.warn("StudioSystrayItem no se encontró en el registro. No se puede parchar.");
}
