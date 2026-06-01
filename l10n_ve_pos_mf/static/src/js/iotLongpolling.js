/** @odoo-module **/
/* global posmodel */

import { IoTLongpolling } from "@iot_base/network_utils/longpolling";
import { patch } from "@web/core/utils/patch";

patch(IoTLongpolling.prototype, {
    setup({ popup, hardware_proxy }) {
        super.setup(...arguments);
        this.hardwareProxy = hardware_proxy;
        this.POLL_TIMEOUT = 100000;
        this.ACTION_TIMEOUT = 100000;
    },
});
