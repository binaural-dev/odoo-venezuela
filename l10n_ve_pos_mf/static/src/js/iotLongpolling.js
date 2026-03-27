/** @odoo-module */
/* global posmodel */

import { _t } from "@web/core/l10n/translation";
import { IoTLongpolling, iotLongpollingService } from "@iot/iot_longpolling";
import { patch } from "@web/core/utils/patch";

patch(IoTLongpolling.prototype, {
    setup({ popup, hardware_proxy }) {
        super.setup(...arguments);
        this.hardwareProxy = hardware_proxy;
        this.POLL_TIMEOUT = 100000;
        this.ACTION_TIMEOUT = 100000;
    },
});
