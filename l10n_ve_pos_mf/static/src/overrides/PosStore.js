/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { LocalOrderBuffer } from "../utils/LocalOrderBuffer";

/**
 * Override del PosStore para integrar la máquina fiscal vía Web Serial API
 * Reemplaza la lógica del IoT Box por comunicación directa con el driver TFHKA
 */
patch(PosStore.prototype, {
  
  /**
   * Abre la gaveta usando el comando directo a la máquina fiscal
   */
  async open_cashbox() {
    const fiscalPrinter = this.getFiscalPrinter();
    
    if (fiscalPrinter && fiscalPrinter.isConnected && this.config.has_cashbox) {
      try {
        const result = await fiscalPrinter.openDrawer();
        if (!result.success) {
          console.error("FiscalPrinter:: Error abriendo gaveta", result.error);
        }
      } catch (error) {
        console.error("FiscalPrinter:: Error abriendo gaveta", error);
        // Fallback al método padre si falla
        return super.open_cashbox(...arguments);
      }
    } else {
      return super.open_cashbox(...arguments);
    }
  },

  /**
   * Obtiene la instancia del driver de la máquina fiscal
   * @returns {TfhkaDriver|null}
   */
  getFiscalPrinter() {
    return window.fiscalPrinter || null;
  },

  /**
   * Verifica si se debe usar la máquina fiscal (reemplaza useFiscalMachine del IoT)
   * @returns {boolean}
   */
  useFiscalMachine() {
    const fiscalPrinter = this.getFiscalPrinter();
    return fiscalPrinter && fiscalPrinter.isConnected;
  },

  get currentOrder() {
    return this.get_order();
  },

  aditionalInfo() {
    let res = []
    res.push(`OPERADOR: ${this.get_cashier().name}`)
    res.push(`PEDIDO: ${this.get_order().uid}`)
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

  /**
   * Construye el objeto de datos de la factura para enviar a la máquina fiscal
   * @param {Object} order - Orden del POS
   * @returns {Promise<Object>}
   */
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
          const date = new Date(response[0].date_order);
          const format_date = date.toLocaleDateString('es-ES');

          invoice["invoice_affected"] = {
            "number": response[0].mf_invoice_number,
            "serial_machine": response[0].fiscal_machine,
            "date": format_date,
          }
        }
      } catch (err) {
        console.error("MF error: ", err)
        if (!err.valid) { 
          this.env.services.popup.add(ErrorPopup, {
            title: _t("MF error"),
            body: _t(err.message ? err.message : "Internal MF error"),
          });
          return err
        }
      }
    }

    if (order.orderlines.length > 0) {
      let vef_base = this.currency.name === "VEF" || this.currency.name === "VES"

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

      invoice['payment_lines'] = order.paymentlines
        .map((el) => {
          let amount = vef_base ? el.amount : el.get_foreign_amount()
          return {
            payment_method: el.payment_method?.code_fiscal_printer || false,
            amount: amount,
          }
        })
        .filter((line) => line.amount > 0 && !!line.payment_method)

      if (!invoice['payment_lines'].length) {
        return {
          valid: false,
          message: "No hay líneas de pago válidas para enviar a la máquina fiscal",
        }
      }
    }
    
    invoice["valid"] = true
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

  /**
   * Guarda los datos de la máquina fiscal en la orden
   * @param {Object} order
   * @param {Object} response - Respuesta del driver
   */
  set_data_from_fiscal_machine(order, response) {
    order.fiscal_machine = response.serial || "TFHKA-LOCAL";
    order.mf_invoice_number = response.invoiceNumber || "";
    order.mf_reportz = response.reportZ || "";
  },

  /**
   * Envía la orden a la máquina fiscal (reemplaza pushToMF del IoT)
   * @param {Object} order
   * @returns {Promise<Object>}
   */
  async pushToMF(order) {
    try {
      const fiscalPrinter = this.getFiscalPrinter();
      
      if (!fiscalPrinter || !fiscalPrinter.isConnected) {
        throw { 
          valid: false, 
          message: "Máquina fiscal no conectada. Haz clic en el botón de impresora para conectar.",
          printer_connection: false 
        };
      }

      // Construir datos de la factura
      let data = await this.get_data_invoice(order);
      if (!data["valid"]) {
        throw { valid: false, message: data["message"] };
      }

      // Convertir formato de Odoo a formato del driver
      const driverOrder = this._convertOrderForDriver(order, data);

      // Enviar a imprimir
      let response;
      if (data.type === 'out_invoice') {
        response = await fiscalPrinter.printInvoice(driverOrder);
      } else if (data.type === 'out_refund') {
        response = await fiscalPrinter.printCreditNote(driverOrder);
      }

      if (!response.success) {
        throw { 
          valid: false, 
          message: response.error || "Error al imprimir en la máquina fiscal",
          printer_connection: true 
        };
      }

      // Guardar datos de la MF en la orden
      this.set_data_from_fiscal_machine(order, response);

      return {
        valid: true,
        message: "",
        printer_connection: true
      };

    } catch (err) {
      console.error("MF error: ", err);
      
      if (err.valid === false) {
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Error de Máquina Fiscal"),
          body: _t(err.message || "Error interno de la máquina fiscal"),
        });
      }
      
      return err;
    }
  },

  /**
   * Convierte la orden de Odoo al formato esperado por el driver
   * @param {Object} order
   * @param {Object} invoiceData
   * @returns {Object}
   */
  _convertOrderForDriver(order, invoiceData) {
    return {
      partner: invoiceData.partner_id || null,
      lines: invoiceData.invoice_lines || [],
      payment_ids: invoiceData.payment_lines || [],
      total_discount: order.get_total_discount() || 0,
    };
  },

  /**
   * Override del método push_single_order con soporte offline-first.
   * 
   * Flujo:
   * 1. Validación contable (dry-run) - tolerante a fallos de red
   * 2. Impresión fiscal (offline) - SIEMPRE se ejecuta
   * 3. Sincronización con backend - con buffer offline si falla
   */
  async push_single_order(order, opts) {
    // 1. Validación contable previa (dry-run) - tolerante a fallos de red
    try {
      const order_payload = [{
        'data': order.export_as_JSON()
      }];
      
      await this.orm.call("pos.order", "validate_order_dry_run", [order_payload]);
      
    } catch (error) {
      // Si el backend no está disponible, permitimos continuar (offline-first)
      const isNetworkError = !error.message || error.message.includes("NetworkError") || 
                              error.message.includes("fetch") || error.message.includes("connection");
      
      if (!isNetworkError) {
        // Error de validación real (datos inválidos) - mostrar y bloquear
        let msg = _t("Error desconocido en Odoo");
        if (error.data && error.data.message) {
          msg = error.data.message;
        } else if (error.message) {
          msg = error.message;
        }
        
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Validación Contable"),
          body: msg,
        });
        return;
      }
      
      // Error de red: permitimos continuar, el pedido se sincronizará después
      console.warn("PosStore:: Validación dry-run omitida (offline)");
    }
    
    // 2. Imprimir en máquina fiscal (offline - no requiere internet)
    if (this.useFiscalMachine() && !order.mf_invoice_number) {
      const response = await this.pushToMF(order);

      if (response.printer_connection === false || !("printer_connection" in response)) {
        return;
      }
    }

    // 3. Sincronizar con el backend de Odoo (con buffer offline si falla)
    try {
      return await super.push_single_order.apply(this, [order, opts]);
    } catch (syncError) {
      // Si la sincronización falla, guardamos en buffer local
      console.warn("PosStore:: Sincronización fallida, guardando en buffer offline", syncError);
      
      const orderData = order.export_as_JSON();
      const fiscalData = {
        fiscal_machine: order.fiscal_machine || "",
        mf_invoice_number: order.mf_invoice_number || "",
        mf_reportz: order.mf_reportz || "",
      };
      
      LocalOrderBuffer.add(orderData, fiscalData);
      
      this.env.services.popup.add(ErrorPopup, {
        title: _t("Pedido guardado localmente"),
        body: _t("La factura fiscal se imprimió correctamente. El pedido se sincronizará con Odoo cuando se restablezca la conexión."),
      });
      
      // No lanzamos el error - el pedido está seguro en el buffer local
      return;
    }
  },

  /**
   * Intenta sincronizar los pedidos pendientes del buffer local
   * Se llama automáticamente al abrir el POS y después de cada sincronización exitosa
   */
  async flushOrderBuffer() {
    const buffer = LocalOrderBuffer.getAll();
    
    if (buffer.length === 0) return;
    
    console.log(`PosStore:: Intentando sincronizar ${buffer.length} pedidos pendientes...`);
    
    for (let i = buffer.length - 1; i >= 0; i--) {
      const entry = buffer[i];
      
      try {
        // Reconstruir la orden y sincronizar
        const orderPayload = [{
          'data': entry.orderData
        }];
        
        // Intentar crear la orden en el backend
        await this.orm.call("pos.order", "create_from_ui", [orderPayload]);
        
        // Si llega aquí, la sincronización fue exitosa
        LocalOrderBuffer.remove(i);
        console.log(`PosStore:: Pedido #${i} sincronizado correctamente`);
        
      } catch (error) {
        entry.retries++;
        console.warn(`PosStore:: Pedido #${i} falló (intento ${entry.retries}):`, error.message);
        
        // Si ya intentó muchas veces, abandonar
        if (entry.retries >= 5) {
          console.error(`PosStore:: Pedido #${i} abandonado después de ${entry.retries} intentos`);
          LocalOrderBuffer.remove(i);
        }
      }
    }
    
    const remaining = LocalOrderBuffer.count();
    if (remaining > 0) {
      console.log(`PosStore:: ${remaining} pedidos siguen pendientes`);
    } else {
      console.log("PosStore:: Todos los pedidos sincronizados");
    }
  },
})
