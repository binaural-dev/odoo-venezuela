/** @odoo-module **/

import { registry } from '@web/core/registry';
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';
import { IoTLongpolling } from '@iot/iot_longpolling';

export class BinauralIoTLongpolling extends IoTLongpolling {
  constructor(dialogService) {
    super(...arguments);
    this.ACTION_TIMEOUT = 160000;
  }

  action(iot_ip, device_identifier, data) {
    console.log("action")
    return super.action(...arguments);
  }
}

export const iotLongpollingService = {
  dependencies: ['dialog'],
  start(_, { dialog }) {
    return new BinauralIoTLongpolling(dialog);
  }
};

registry.category('services').add('iot_longpolling', iotLongpollingService, { force: true });
