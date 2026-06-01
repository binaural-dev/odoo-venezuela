/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";



patch(PosStore.prototype, {
  async setup(...args) {
    await super.setup(...args);
    this.dialog = this.env.services.dialog;
    this.notification = this.env.services.notification;
    this.orm = this.env.services.orm;
  },

  _mfDebugEnabled() {
    return Boolean(this.config && this.config.mf_debug);
  },

  _mfLog(level, message, payload) {
    if (!this._mfDebugEnabled()) {
      return;
    }
    const prefix = "[l10n_ve_pos_mf]";
    const fn = console[level] || console.log;
    fn(`${prefix} ${message}`, payload ?? "");
  },
  open_cashbox() {
    if (this.useFiscalMachine() && this.config.has_cashbox) {
      const fdm = this.useFiscalMachine();
      fdm.action({
        action: `logger`,
        data: "0",
      })
    } else {
      return super.open_cashbox(...arguments);
    }
  },

  useFiscalMachine() {
    return this.hardwareProxy.deviceControllers.fiscal_data_module
  },

  get currentOrder() {
    return this.get_order();
  },



  aditionalInfo() {
    let res = []
    res.push(`OPERADOR: ${this.getCashier().name}`)
    res.push(`PEDIDO: ${this.getOrder().uuid}`)
    return res
  },
  get get_flag_21() {
    return this.config.flag_21
  },
  get get_traditional_line() {
    return this.config.traditional_line
  },
  get has_cashbox() {
    return this.config.has_cashbox
  },

  is_same_mf(serial) {
    return true
  },
  async get_data_invoice(order) {
    let invoice = {
      company_id: {
        name: this.company.name,
      },
      flag_21: this.get_flag_21,
      traditional_line: this.get_traditional_line,
      has_cashbox: this.has_cashbox && order.is_paid_with_cash(),
      time: Date.now(),
    }
    if (order.get_partner()) {

      invoice['partner_id'] = {}
      let client = order.get_partner()

      invoice['partner_id']['vat'] = client.prefix_vat + client.vat
      invoice['partner_id']['name'] = this.normalizeProductName(client.name)
      invoice['partner_id']['address'] = client.address || false
      invoice['partner_id']['phone'] = client.phone || false
    }

    invoice["info"] = this.aditionalInfo()

    let uid = order.uid
    const values = Object.values(this.toRefundLines)
    let lines = []
    //BUSCAR EL ORDEN 
    for (let i = 0; i < values.length; i++) {
      if (values[i].destinationOrderUid == uid) {
        lines.push(values[i])
      }
    }

    invoice['type'] = 'out_invoice'
    if (order.get_total_with_tax() < 0) {
      invoice['type'] = 'out_refund'
    }
    if (lines.length > 0 && invoice['type'] == 'out_refund') {
      try {
        const response = await this.orm.call("pos.order", "get_order_by_uid", [[], lines[0].orderline.orderUid])
        if (!this.is_same_mf(response[0].fiscal_machine)) {
          return { "valid": false, "message": `El documento fue impreso desde la Maquina ${response[0].fiscal_machine}` }
        }
        if (response.length > 0) {
          invoice["invoice_affected"] = {
            "number": response[0].mf_invoice_number,
            "serial_machine": response[0].fiscal_machine,
            "date": response[0].date_order,
          }
        }
      } catch (e) {
      }
    }

    if (order.orderlines.length > 0) {

      let vef_base = this.currency.name === "VEF"

      invoice['invoice_lines'] = order.orderlines.map((el) => {

        if (!!el.customerNote) {
          let split = el.customerNote.split("\n")
          for (let i = 0; i < split.length; i++) {
            invoice["info"].push(`${split[i]}`)
          }
        }


        let amount = vef_base ? el.price : el.get_foreign_unit_price()

        return {
          price_unit: amount,
          discount: el.get_discount(),
          quantity: Math.abs(el.quantity),
          name: this.normalizeProductName(el.product.display_name),
          code: el.product.default_code,
          tax: el.get_taxes().length > 0 ? el.get_taxes()[0]['fiscal_code'] : 0
        }
      })
      invoice['payment_lines'] = order.paymentlines.map((el) => {

        let amount = vef_base ? el.amount : el.get_foreign_amount()
        return {
          payment_method: el.payment_method.code_fiscal_printer,
          amount: amount,
        }
      })
    }
    invoice["valid"] = true
    invoice["iot_ip"] = this.config.iot_ip || false

    this._mfLog("info", "get_data_invoice: built payload", {
      uid: order?.uid,
      type: invoice.type,
      iot_ip: invoice.iot_ip,
      partner_vat: invoice.partner_id?.vat,
      lines: invoice.invoice_lines?.length || 0,
      payments: invoice.payment_lines?.length || 0,
      total: order?.get_total_with_tax?.(),
    });
    return invoice
  },

  normalizeProductName(text) {
    if (!text) return "";

    const normalized = text.normalize("NFKD");
    const noSpecialChars = normalized
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^\w\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    return noSpecialChars;
  },

  async print_out_invoice(data) {
    this._mfLog("info", "print_out_invoice: start", {
      uid: this.get_order()?.uid,
      type: data?.type,
      action: `print_${data?.type}`,
      has_fdm: Boolean(this.useFiscalMachine()),
      iot_ip: data?.iot_ip || this.config?.iot_ip,
    });

    // In v19 we route every print request through ORM to the server side.
    // The server then calls the IoT Box, avoiding browser-network constraints.
    const response = await this._print_via_server_proxy(data);
    if (!response || !response.value) {
      return {
        value: {
          valid: false,
          message: _t("Respuesta invalida del proxy del servidor"),
        },
      };
    }
    return response;
  },

  // _print_via_hardware_proxy(fdm, data) {
  //   const request_data = {
  //     action: `print_${data.type}`,
  //     data: data,
  //   }

  //   this._mfLog("info", "_print_via_hardware_proxy: sending", request_data);

  //   return new Promise((resolve, reject) => {
  //     const listener = (event) => {
  //       if (event?.request_data?.action === request_data.action) {
  //         this._mfLog("info", "_print_via_hardware_proxy: event", {
  //           status: event?.status?.status,
  //           value: event?.value,
  //         });
  //       }
  //       if (event.request_data.action === request_data.action) {
  //         if (event.status.status === "connected") {
  //           if (event.value && event.value.message === "No se ha completado") {
  //             return;
  //           }
  //           fdm.removeListener(listener);
  //           return resolve(event);
  //         } else {
  //           fdm.removeListener(listener);
  //           return reject(event);
  //         }
  //       }
  //     };

  //     fdm.addListener(listener);

  //     fdm.action(request_data).then(response => {
  //       this._mfLog("info", "_print_via_hardware_proxy: action response", response);
  //       if (!response.result) {
  //         fdm.removeListener(listener);
  //         reject({
  //           valid: false,
  //           message: _t("Error connecting to the fiscal machine, check if it is turned on or connected to the IoT"),
  //           printer_connection: false,
  //         });
  //       }
  //     }).catch(error => {
  //       this._mfLog("warn", "_print_via_hardware_proxy: action error", error);
  //       fdm.removeListener(listener);
  //       reject({
  //         valid: false,
  //         message: error.statusText === "timeout"
  //           ? _t("The tax machine did not respond in time")
  //           : _t("Error with the tax machine"),
  //         printer_connection: false,
  //       });
  //     });
  //   });
  // },

  async _print_via_server_proxy(data) {
    const iot_ip = data.iot_ip || this.config.iot_ip;
    if (!iot_ip) {
      this._mfLog("warn", "_print_via_server_proxy: missing iot_ip", { data, config: this.config });
      return { value: { valid: false, message: _t("No se pudo determinar la IP del IoT Box") } };
    }

    try {
      const action = `print_${data.type}`;
      this._mfLog("info", "_print_via_server_proxy: orm.call", {
        session_id: this.pos_session?.id,
        iot_ip,
        action,
      });

      const response = await this.orm.call(
        "pos.session",
        "proxy_fiscal_action",
        [this.pos_session.id, action, data]
      );

      this._mfLog("info", "_print_via_server_proxy: orm.call response", response);
      return response;
    } catch (e) {
      this._mfLog("warn", "_print_via_server_proxy: exception", e);
      return { value: { valid: false, message: _t("Error de conexion con el proxy del servidor") } };
    }
  },

  set_data_from_fiscal_machine(order, data) {
    order.fiscal_machine = data["serial_machine"] || false;
    order.mf_invoice_number = data["sequence"] || false;
    order.mf_reportz = data["mf_reportz"] || false;
  },

  // async pushToMF(order) {
  //   try {
  //     this._mfLog("info", "pushToMF: start", { uid: order?.uid, mf_invoice_number: order?.mf_invoice_number });
  //     let data = await this.get_data_invoice(order)

  //     if (!data["valid"]) {
  //       throw data["message"]
  //     }

  //     const response = await this.print_out_invoice(data)
  //     const { value } = response

  //     this._mfLog("info", "pushToMF: print_out_invoice returned", { value });

  //     if (!value.valid) {
  //       throw value
  //     }

  //     this.set_data_from_fiscal_machine(order, value)

  //     this._mfLog("info", "pushToMF: stored MF values", {
  //       uid: order?.uid,
  //       fiscal_machine: order?.fiscal_machine,
  //       mf_invoice_number: order?.mf_invoice_number,
  //       mf_reportz: order?.mf_reportz,
  //     });

  //     return {
  //       valid: true,
  //       message: "",
  //       printer_connection: true
  //     }

  //   } catch (err) {

  //     this._mfLog("warn", "pushToMF: error", err);

  //     if (!err.valid) {
  //       this.dialog.add(AlertDialog, {
  //         title: _t("MF error"),
  //         body: _t(err.message ? err.message : "Internal MF error"),
  //       });

  //       return err

  //     } else {
  //       this.dialog.add(AlertDialog, {
  //         title: _t("MF error"),
  //         body: _t(err.status ? err.status : "Internal MF error"),
  //       });
  //       return err;
  //     }
  //   }
  // },

  // //   generate_report_x() {
  // //   const fdm = this.useFiscalMachine();
  // //   if (!fdm) return
  // //   new Promise(async (resolve, reject) => {
  // //     await fdm.action({
  // //       action: 'print_out_invoice',
  // //       data: {},
  // //     })
  // //   });
  // // },

  // async pushSingleOrder(order, opts) {
  //   const hasMF = Boolean(this.useFiscalMachine()) || Boolean(this.config?.iot_ip);
  //   if (hasMF && !order.mf_invoice_number) {
  //     const response = await this.pushToMF(order)
  //     if (response.printer_connection === false) {
  //       console.warn("Fiscal machine not connected, syncing order without fiscal print", response)
  //     }
  //   }
  //   this._mfLog("info", "pushSingleOrder: calling super", { uid: order?.uid });
  //   return await super.pushSingleOrder.apply(this, [order, opts]);
  // },

})
