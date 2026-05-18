/** @odoo-module **/

import { registry } from '@web/core/registry';
import { IoTLongpolling } from '@iot_base/network_utils/longpolling';

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

registry.category('services').add('iot_longpolling', iotLongpollingService, { force: true });
