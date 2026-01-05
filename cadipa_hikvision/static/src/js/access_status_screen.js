/** @odoo-module **/

import { Component, mount, onWillStart, useState } from "@odoo/owl";
import { PublicWidget } from "@web/legacy/js/public/public_widget";
import { registry } from "@web/core/registry";
import { useService,  } from "@web/core/utils/hooks";


class AccessStatusScreen extends Component {
    static template = "cadipa_hikvision.access_status_screen";

    setup() {
        this.busService = useService("bus_service");
        this.state = useState({
            name: "Esperando evento...",
            status_text: "El sistema está listo para recibir un evento de acceso.",
            bg_class: "bg-secondary",
            image_url: false,
        });

        const channelName = "hikvision_access_channel";

        onWillStart(() => {
            this.busService.addChannel(channelName);
            this.busService.addEventListener("notification", ({ detail: notifications }) => {
                for (const { payload, type } of notifications) {
                    if (type === "access_control_event") {
                        console.log("Evento recibido:", payload);
                        this.state.name = payload.name;
                        this.state.status_text = payload.status_text;
                        this.state.bg_class = payload.bg_class;
                        this.state.image_url = payload.image_url;
                    }
                }
            });
        });
    }
}


const AccessStatusWidget = PublicWidget.extend({
    selector: '#access-status-root',

    /**
     * @override
     */
    start: function () {
        mount(AccessStatusScreen, { target: this.el });
        return this._super.apply(this, arguments);
    },
});

registry.category("public_widgets").add("accessStatusScreenWidget", AccessStatusWidget);

export default AccessStatusWidget;