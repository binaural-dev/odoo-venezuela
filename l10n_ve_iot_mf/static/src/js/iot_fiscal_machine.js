/** @odoo-module **/

import { Widget } from "@web/views/widgets/widget";
import { registry } from "@web/core/registry";
import { DeviceController } from "@iot/device_controller";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';

const PRINT_OUT_INVOICE = "print_out_invoice";
const PRINT_OUT_REFUND = "print_out_refund";
const PRINT_DEBIT_NOTE = "print_debit_note";
const REPRINT = "reprint";

function onIoTActionResult(data, notification) {
  if (data.result === true) {
    notification.add(_t("Successfully sent to printer!"));
  } else {
    notification.add(_t("Check if the printer is still connected"), {
      title: _t("Connection to printer failed"),
      type: "danger",
    });
  }
}


const { xml, useState } = owl;

export class IoTFiscalMachineComponent extends Component {
  setup() {
    super.setup();
    const device = this.props.record.data
    this.orm = useService("orm")
    this.dialog = useService('dialog');
    this.notification = useService('notification');

    this.device = new DeviceController(
      this.env.services.iot_longpolling,
      { iot_ip: device.iot_ip, identifier: device.identifier }
    );


    this.button_names = {
      [PRINT_OUT_INVOICE]: _t("Print Invoice"),
      [PRINT_OUT_REFUND]: _t("Print Refund"),
      "generate_report_z": _t("Generate Report Z"),
      "generate_report_x": _t("Generate Report X"),
      "get_serial_machine": _t("Get Serial Machine"),
      "status_error": _t("Get Status / Error"),
      "programacion": _t("Programming"),
      "status_1": _t("Get Status 1"),
      "reprint_document": _t("Reprint Document"),
      "reprint_type": _t("Reprint"),
      "reprint_type_date": _t("Reprint Date"),
      "payment_method": _t("Set Payment Method"),
      "test": _t("Test"),
      "command": _t("Send Command"),
      "print_resume_date": _t("Print Resume"),
      "configure_device": _t("Configure Device"),
      [PRINT_DEBIT_NOTE]: _t("Print Debit Note"),
    }

    this.state = useState({
      action: this[this.props.action] || this.not_function,
      name: this.button_names[this.props.action] || "CLOWN"
    });

  }
  showFailedConnection() {
    this.dialog.add(IoTConnectionErrorDialog, { href: url });
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
  get_serial_machine() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
      if (!value.valid) {
        return
      }
      this.orm.call('iot.device', 'set_serial_machine', [this.props.record.evalContext.active_id, value])
        .then(() => {
          // window.location.reload()
        })
    });
    this.iotDevice.action({
      action: "get_last_invoice_number",
      data: { "me": "you" },
    }).then(data => {
      return onIoTActionResult(data, this.notification)
    })
  }

  async payment_method() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/get_data_to_payment_method", {
      model: 'iot.device',
      method: 'get_data_to_payment_method',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "logger",
      data: `PE${request.payment_methods}${request.payment_method_name}`.toUpperCase(),
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }


  async status_error() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
      console.log(this.env.services.notification.add(value.message))
    });

    this.iotDevice.action({
      action: "status",
      data: true,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }

  async print_resume_date() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/get_range_resume", {
      model: 'iot.device',
      method: 'get_range_resume',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "print_resume",
      data: request,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })
  }

  async reprint_type_date() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/get_range_reprint", {
      model: 'iot.device',
      method: 'get_range_reprint',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "reprint_date",
      data: request,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }
  async reprint_type() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/get_range_reprint", {
      model: 'iot.device',
      method: 'get_range_reprint',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "reprint_type",
      data: request,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }
  async configure_device() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/configure_device", {
      model: 'iot.device',
      method: 'configure_device',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "configure_device",
      data: request,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })
  }
  async test() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "test",
      data: true,
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }
  async command() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const device = this.props.record.resId

    const request = await this.env.services.rpc("web/dataset/call_kw/iot.device/get_command", {
      model: 'iot.device',
      method: 'get_command',
      args: [device],
      kwargs: {},
    })

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
    });

    this.iotDevice.action({
      action: "logger",
      data: request["command"],
    })
      .then(data => {
        onIoTActionResult(data, this.notification)
      })

  }
  async generate_report_z() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const request = await this.orm.call('account.move', 'check_report_z', [[], this.device.serial_machine])
    console.log(request)

    if (!request) {
      this.notification.add(_t("Not are invoices to Report Z"), {
        title: _t("Verify invoices with Serial Machine"),
        type: "danger",
      });
      return
    }

    this.iotDevice.addListener(({ value }) => {
      this.iotDevice.removeListener();
      this.orm.call('account.move', 'report_z', [[], this.device.serial_machine, value])
    });
    this.iotDevice.action({
      action: "report_z",
      data: { "me": "you" },
    })
    .then(data => {
      onIoTActionResult(data, this.notification)
    })
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
        onIoTActionResult(data, this.notification)
      })
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
        onIoTActionResult(data, this.notification)
      })
  }

  async print_out_invoice() {
    return await this.print_document(PRINT_OUT_INVOICE)
  }
  
  async print_out_refund() {
    return await this.print_document(PRINT_OUT_REFUND)
  }

  async print_debit_note() {
    return await this.print_document(PRINT_DEBIT_NOTE)
  }

  async reprint_document() {
    return await this.print_document(REPRINT)
  }

  async print_document(print_type) {

    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const check_print_type = `check_${print_type}`

    try {
      
      this.notification.add("Comunicando con la impresora, por favor espere...", {
            type: 'warning'
      });

      const move_id = this.props.record.resId

      const request = await this.call_model_method(
        "account.move", 
        check_print_type,
        [move_id]
      );

      this.device = new DeviceController(
        this.env.services.iot_longpolling,
        { iot_ip: request.iot_ip, identifier: request.identifier }
      );

      const deviceResponse = await this.device_response(print_type, request);

      if (print_type != "reprint") {
        
        await this.call_model_method(
          "account.move", 
          print_type,
          [move_id, deviceResponse]
        );
        
        window.location.reload()
      }

    }catch(error){
      onIoTError(error.data.message, this.notification)
    }
  }

  async call_model_method(model, method, args = [], kwargs = {}) {
    const endpoint = `web/dataset/call_kw/${model}/${method}`;
    const response = this.env.services.rpc(endpoint, {
      model,
      method,
      args,
      kwargs,
    });

    return response;
  }

  async device_response(action, data) {
    return new Promise((resolve, reject) => {
      const listener = ({value}) => {
        this.iotDevice.removeListener(listener);
        resolve(value);
      };
  
      this.iotDevice.addListener(listener);
  
      this.iotDevice.action({
        action: action,
        data: data,
      }).catch(reject);
    });
  }

  doWarnFail(url) {
    this.dialog.add(IoTConnectionErrorDialog, { href: url });
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

const fiscal_component = {
  component: IoTFiscalMachineComponent,
  extractProps: (values) => {
    return values.attrs
  },

};

registry.category("view_widgets").add("iot-mf-button", fiscal_component);
