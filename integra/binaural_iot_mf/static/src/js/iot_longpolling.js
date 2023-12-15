/** @odoo-module **/

import { registry } from '@web/core/registry';
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';
import { IoTLongpolling } from '@iot/iot_longpolling';

export class BinauralIoTLongpolling extends IoTLongpolling {
  constructor(dialogService) {
    super(...arguments);
  }

  action(iot_ip, device_identifier, data) {
    let res = super.action(...arguments)
    return res
  }
}

export const iotLongpollingService = {
  dependencies: ['dialog'],
  start(_, { dialog }) {
    return new BinauralIoTLongpolling(dialog);
  }
};

registry.category('services').add('iot_longpolling', iotLongpollingService, { force: true });
