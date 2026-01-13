/** @odoo-module **/

import { registry } from '@web/core/registry';
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';
import { IoTLongpolling } from '@iot/iot_longpolling';

export class BinauralIoTLongpolling extends IoTLongpolling {
  constructor(dialogService) {
    super(...arguments);
    this.dialogService = dialogService;
    this.POLL_TIMEOUT = 6000000;
    this.ACTION_TIMEOUT = 1600000;
  }

  _doWarnFail(url) {
    if (this.dialogService && typeof this.dialogService.add === 'function') {
      this.dialogService.add(IoTConnectionErrorDialog, { href: url });
    } else {
      console.warn("Servicio de diálogo no disponible para mostrar el error de conexión IoT.");
    }
  }
}

export const iotLongpollingService = {
  dependencies: ['dialog'],
  start(_, { dialog }) {
    return new BinauralIoTLongpolling(dialog);
  }
};

registry.category('services').add('iot_longpolling', iotLongpollingService, { force: true });
