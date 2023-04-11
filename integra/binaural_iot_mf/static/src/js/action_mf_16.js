/** @odoo-module **/

import { Widget } from "@web/views/widgets/widget";
import { registry } from "@web/core/registry";
import { DeviceController } from "@iot/device_controller";

var core = require('web.core');
var _t = core._t;

function onIoTActionResult(data, env) {
  if (data.result === true) {
    env.services.notification.add(env._t("Successfully sent to printer!"));
  } else {
    env.services.notification.add(env._t("Check if the printer is still connected"), {
      title: env._t("Connection to printer failed"),
      type: "danger",
    });
  }
}


const { xml, useState } = owl;

export class IoTFiscalMachineComponent extends Widget {
  setup() {
    super.setup();
    const device = this.props.record.data
    this.device = new DeviceController(
      this.env.services.iot_longpolling,
      { iot_ip: device.iot_ip, identifier: device.identifier }
    );

    this.button_names = {
      "print_out_invoice": _t("Print Invoice"),
      "print_out_refund": _t("Print Refund"),
      "generate_report_z": _t("Generate Report Z"),
      "generate_report_x": _t("Generate Report X"),
      "get_serial_machine": _t("Get Serial Machine"),
      "status_error": _t("Get Status / Error"),
      "programacion": _t("Programming"),
      "status_1": _t("Get Status 1"),
      "reprint_document": _t("Reprint Document"),
    }
    this.state = useState({
      action: this[this.props.action] || this.not_function,
      name: this.button_names[this.props.action] || "CLOWN"
    });
  }
  showFailedConnection() {
    this.env.services.notification.add(_t("Device is not connected"), {
      title: _t("Connection to printer failed"),
      type: "danger"
    })
  }
  get iotDevice() {
    return this.device
  }
  /*--------------------------------------------------------
   *                       Handlers
   *-------------------------------------------------------*/
  not_function() {
    console.log("CLOWN, please set a function name")
  }
  print_out_invoice() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

  }
  get_serial_machine() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
      this.env.services.rpc("web/dataset/call_kw/iot.device/set_serial_machine", {
        model: 'iot.device',
        method: 'set_serial_machine',
        args: [this.props.record.data.id, value],
        kwargs: {},
      })
        .then(() => {
          window.location.reload()
        })
    });
    this.iotDevice.action({
      action: "get_last_invoice_number",
      data: { "me": "you" },
    })
      .then(data => {
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.ip));
  }

  async generate_report_z() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const request = await this.env.services.rpc("web/dataset/call_kw/account.move/check_report_z", {
      model: 'account.move',
      method: 'check_report_z',
      args: [[], this.device.serial_machine],
      kwargs: {},
    })

    if (!request) {
      this.env.services.notification.add(_t("Not are invoices to Report Z"), {
        title: _t("Verify invoices with Serial Machine"),
        type: "danger",
      });
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
      this.env.services.rpc("web/dataset/call_kw/iot.device/set_serial_machine", {
        model: 'account.move',
        method: 'report_z',
        args: [[], this.device.serial_machine, value],
        kwargs: {},
      })
    });
    this.iotDevice.action({
      action: "report_z",
      data: { "me": "you" },
    })
      .then(data => {
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.ip));
  }

  async generate_report_x() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(() => {
      this.iotDevice.removeListener();
    });
    this.iotDevice.action({
      action: "report_x",
      data: { "me": "you" },
    })
      .then(data => {
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.ip));
  }

  async programacion() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(() => {
      this.iotDevice.removeListener();
    });
    this.iotDevice.action({
      action: "programacion",
      data: { "me": "you" },
    })
      .then(data => {
        console.log(data)
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.ip));
  }
}

IoTFiscalMachineComponent.extractProps = ({ attrs }) => {
  return {
    action: attrs.action,
  };
};

IoTFiscalMachineComponent.template = xml
  `<button class="btn btn-primary" t-on-click="state.action">
    <span t-esc="state.name"/>
  </button>`;

registry.category("view_widgets").add("iot-mf-button", IoTFiscalMachineComponent);
