/** @odoo-module **/

import { Widget } from "@web/views/widgets/widget";
import { registry } from "@web/core/registry";
import { DeviceController } from "@iot/device_controller";
import { useService } from "@web/core/utils/hooks";

var core = require('web.core');
var _t = core._t;

function onIoTActionResult(data, env) {
  if (data.result === true) {
    env.services.notification.add(env._t("Successfully sent to printer!"));
  } else {
    const errorMessage = data.message ? env._t(data.message) : env._t("Check if the printer is still connected");
    env.services.notification.add(errorMessage, {
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
    const orm = useService("orm")

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
      "reprint_type": _t("Reprint"),
      "reprint_type_date": _t("Reprint Date"),
      "payment_method": _t("Set Payment Method"),
      "test": _t("Test"),
      "command": _t("Send Command"),
      "print_resume_date": _t("Print Resume"),
      "configure_device": _t("Configure Device"),
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
    console.log(this.device)
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
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
        onIoTActionResult(data, this.env)
      })
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));

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
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
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
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
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
      .guardedCatch(() => this.iotDevice.iotLongpolling._doWarnFail(this.device.iotIp));
  }

  async print_out_invoice() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const move_id = this.props.record.__bm_load_params__.res_id

    try {
      const request = await this.env.services.rpc("web/dataset/call_kw/account.move/check_print_out_invoice", {
        model: 'account.move',
        method: 'check_print_out_invoice',
        args: [move_id],
        kwargs: {},
      })


      const request2 = await this.env.services.rpc("web/dataset/call_kw/account.move/check_config_tax", {
        model: 'account.move',
        method: 'check_config_tax',
        args: [move_id],
        kwargs: {},
      })

      if (request2) {
        throw new Error("La configuración de impuestos no es válida.");
      }

      if (!this.device || this.device.iotIp !== request.iot_ip) {
        this.device = new DeviceController(this.env.services.iot_longpolling, {
          iot_ip: request.iot_ip,
          identifier: request.identifier,
        });
      }

      const printResponse = await new Promise((resolve, reject) => {
        try {
          const result = this.iotDevice.action({
            action: "print_out_invoice",
            data: request,
          });
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });

      if (printResponse.result) {

        onIoTActionResult(printResponse, this.env);

        await this.iotDevice.action({
          action: "get_last_invoice_number",
          data: { me: "you" },
        });

        this.listener = async ({ value }) => {
          await this.env.services.rpc("web/dataset/call_kw/account.move/print_out_invoice", {
            model: "account.move",
            method: "print_out_invoice",
            args: [this.props.record.data.id, value],
            kwargs: {},
          }).then(data => {

            setTimeout(function() { }, 2000);

            if (data) {
              window.location.reload();
            }

          });
        };

        this.iotDevice.addListener(this.listener);
      }

    } catch (error) {
      let errorMessage = error.data?.message || error.message || "Ocurrió un error desconocido.";
      console.error("Error en print_out_refund:", errorMessage);
      onIoTActionResult({ result: false, message: errorMessage }, this.env);
    }
  }

  async print_out_refund() {
    if (!this.device) {
      this.showFailedConnection();
      return;
    }

    const move_id = this.props.record.__bm_load_params__.res_id;

    try {
      const request = await this.env.services.rpc("web/dataset/call_kw/account.move/check_print_out_refund", {
        model: 'account.move',
        method: 'check_print_out_refund',
        args: [move_id],
        kwargs: {},
      });

      if (!this.device || this.device.iotIp !== request.iot_ip) {
        this.device = new DeviceController(this.env.services.iot_longpolling, {
          iot_ip: request.iot_ip,
          identifier: request.identifier,
        });
      }

      const printResponse = await new Promise((resolve, reject) => {
        try {
          const result = this.iotDevice.action({
            action: "print_out_refund",
            data: request,
          });
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });

      if (printResponse.result) {
        onIoTActionResult(printResponse, this.env);

        await this.iotDevice.action({
          action: "get_last_out_refund_number",
          data: { me: "you" },
        });

        this.listener = async ({ value }) => {
          await this.env.services.rpc("web/dataset/call_kw/account.move/print_out_refund", {
            model: "account.move",
            method: "print_out_refund",
            args: [this.props.record.data.id, value],
            kwargs: {},
          }).then(data => {

            setTimeout(function() { }, 5000);

            if (data) {
              window.location.reload();
            }

          });
        };
        this.iotDevice.addListener(this.listener);
      }

    } catch (error) {
      let errorMessage = error.data?.message || error.message || "Ocurrió un error desconocido.";
      console.error("Error en print_out_refund:", errorMessage);
      onIoTActionResult({ result: false, message: errorMessage }, this.env);
    }
  }

  async reprint_document() {
    if (!this.device) {
      this.showFailedConnection()
      return
    }

    const move_id = this.props.record.__bm_load_params__.res_id;


    const request = await this.env.services.rpc("web/dataset/call_kw/account.move/check_reprint", {
      model: 'account.move',
      method: 'check_reprint',
      args: [move_id],
      kwargs: {},
    })

    if (!this.device || this.device.iotIp !== request.iot_ip) {
      this.device = new DeviceController(this.env.services.iot_longpolling, {
        iot_ip: request.iot_ip,
        identifier: request.identifier,
      });
    }

    await new Promise((resolve, reject) => {
      try {
        const result = this.iotDevice.action({
          action: "reprint",
          data: request,
        });
        resolve(result);
      } catch (error) {
        reject(error);
      }
    });
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
