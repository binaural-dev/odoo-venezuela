/** @odoo-module **/

import { registry } from '@web/core/registry';
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';
import { IoTLongpolling } from '@iot/iot_longpolling';

export class BinauralIoTLongpolling extends IoTLongpolling {
  constructor(dialogService) {
    super(...arguments);
    this.POLL_TIMEOUT = 6000000;
    this.ACTION_TIMEOUT = 1600000;
  }
}

export const iotLongpollingService = {
  dependencies: ['dialog'],
  start(_, { dialog }) {
    return new BinauralIoTLongpolling(dialog);
  }
};

const fieldsRegistry = registry.category("services");

if (!fieldsRegistry.contains("iot_longpolling")) {
    fieldsRegistry.add('iot_longpolling', iotLongpollingService, { force: true });
}
