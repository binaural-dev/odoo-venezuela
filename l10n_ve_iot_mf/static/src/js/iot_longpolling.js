/** @odoo-module **/

import { registry } from "@web/core/registry";
import { IoTConnectionErrorDialog } from "@iot/iot_connection_error_dialog";
import { IoTLongpolling } from "@iot/iot_longpolling";
import { patch } from "@web/core/utils/patch";

patch(IoTLongpolling.prototype, {
	setup({ dialog }) {
		super.setup(...arguments);
		console.log("PINGA");
		this.POLL_TIMEOUT = 6000000;
		this.ACTION_TIMEOUT = 1600000;
	},
	addListener(iot_ip, devices, listener_id, callback, fallback = false) {
		console.log("PROBANDO");
		return super.addListener(...arguments);
	},
});
