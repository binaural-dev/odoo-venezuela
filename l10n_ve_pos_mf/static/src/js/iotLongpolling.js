/** @odoo-module */
/* global posmodel */

import { _t } from "@web/core/l10n/translation";
import { IoTLongpolling, iotLongpollingService } from "@iot/iot_longpolling";
import { patch } from "@web/core/utils/patch";
import { IoTErrorPopup } from "@pos_iot/app/io_t_error_popup/io_t_error_popup";

patch(IoTLongpolling.prototype, {
    setup({ popup, hardware_proxy }) {
        super.setup(...arguments);
        this.hardwareProxy = hardware_proxy;
        this.POLL_TIMEOUT = 100000;
        this.ACTION_TIMEOUT = 100000;
    },
});
