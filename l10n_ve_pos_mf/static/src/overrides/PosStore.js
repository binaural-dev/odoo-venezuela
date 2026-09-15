/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { floatIsZero, roundPrecision as round_pr } from "@web/core/utils/numbers";
import { LocalOrderBuffer } from "../utils/LocalOrderBuffer";
import { LocalOrderHistory } from "../utils/LocalOrderHistory";

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

    if (fiscalPrinter && fiscalPrinter.isPaired && this.config.has_cashbox) {
      try {
        // withConnection abre el puerto bajo demanda solo por este comando
        // y lo libera al terminar.
        const result = await fiscalPrinter.withConnection(() => fiscalPrinter.openDrawer());
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
   * Verifica si hay máquina fiscal disponible para usar (reemplaza
   * useFiscalMachine del IoT). Bajo el modelo de conexión bajo demanda, el
   * puerto casi nunca está literalmente abierto (`isConnected`) fuera de
   * una impresión en curso — lo relevante aquí es si el dispositivo está
   * autorizado/pareado (`isPaired`), no si el puerto está abierto en este
   * instante.
   * @returns {boolean}
   */
  useFiscalMachine() {
    const fiscalPrinter = this.getFiscalPrinter();
    return !!(fiscalPrinter && fiscalPrinter.isPaired);
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
    let affectedOrderData = null
    
    for (let i = 0; i < values.length; i++) {
      if (values[i].destinationOrderUid == uid) {
        lines.push(values[i])
      }
    }

    // Determinar tipo de documento fiscal
    const total = order.get_total_with_tax();
    const hasRefundLines = lines.length > 0; // líneas de devolución detectadas arriba

    if (total >= 0 && !hasRefundLines) {
      invoice['type'] = 'out_invoice';  // Factura normal
    } else if (total < 0 || hasRefundLines) {
      invoice['type'] = 'out_refund';   // Nota de crédito (devolución)
    } else {
      invoice['type'] = 'out_invoice';  // Por defecto factura
    }

    if (lines.length > 0 && invoice['type'] == 'out_refund') {
      const originalOrderUid = lines[0].orderline.orderUid
      const localOrder = LocalOrderHistory.getByUid(originalOrderUid)

      if (localOrder) {
        affectedOrderData = localOrder
      } else {
        try {
          const response = await this.orm.call("pos.order", "get_order_by_uid", [[], originalOrderUid])
          if (response.length > 0) {
            affectedOrderData = response[0]
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

      if (!affectedOrderData) {
        return {
          valid: false,
          message: _t("No se pudo recuperar la factura original para emitir la nota de credito"),
        }
      }

      if (!this.is_same_mf(affectedOrderData.fiscal_machine)) {
        return { "valid": false, "message": `El documento fue impreso desde la Maquina ${affectedOrderData.fiscal_machine}` }
      }

      const date = new Date(affectedOrderData.date_order);
      const format_date = date.toLocaleDateString('es-ES');

      invoice["invoice_affected"] = {
        "number": affectedOrderData.mf_invoice_number,
        "serial_machine": affectedOrderData.fiscal_machine,
        "date": format_date,
      }
    }

    if (order.orderlines.length > 0) {
      let vef_base = this.currency.name === "VEF" || this.currency.name === "VES"
      const decimalPlaces = vef_base
        ? this.currency.decimal_places
        : (this.foreign_currency?.decimal_places || this.currency.decimal_places)
      const rounding = vef_base
        ? this.currency.rounding
        : (this.foreign_currency?.rounding || this.currency.rounding)
      const roundAmount = (amount) => round_pr(amount, rounding)
      const isPositive = (amount) => {
        const rounded = roundAmount(amount)
        return !floatIsZero(rounded, decimalPlaces) && rounded > 0
      }
      const isNegative = (amount) => {
        const rounded = roundAmount(amount)
        return !floatIsZero(rounded, decimalPlaces) && rounded < 0
      }

      invoice['invoice_lines'] = order.orderlines.map((el) => {
        if (!!el.customerNote) {
          let split = el.customerNote.split("\n")
          for (let i = 0; i < split.length; i++) {
            invoice["info"].push(`${split[i]}`)
          }
        }

        let amount = vef_base ? el.price : el.get_foreign_unit_price()
        const taxes = el.get_taxes()
        const fiscalCode = taxes.length > 0
          ? (String(taxes[0]?.fiscal_code || "").replace(/^t/i, "") || "0")
          : "0"

        return {
          price_unit: amount,
          discount: el.get_discount(),
          quantity: Math.abs(el.quantity),
          name: this.normalizeProductName(el.product.display_name),
          code: el.product.default_code,
          tax: fiscalCode,
        }
      })

      invoice['payment_lines'] = order.paymentlines
        .map((el) => {
          let amount = vef_base ? el.amount : el.get_foreign_amount()
          return {
            payment_method: el.payment_method?.code_fiscal_printer || false,
            amount: roundAmount(amount),
          }
        })
        .filter((line) => {
          if (!line.payment_method) {
            return false;
          }
          if (invoice.type === 'out_refund') {
            return isNegative(line.amount);
          }
          return isPositive(line.amount);
        })

      if (
        invoice.type === "out_refund" &&
        !invoice['payment_lines'].length &&
        affectedOrderData?.payment_lines?.length
      ) {
        const sourcePayments = affectedOrderData.payment_lines
          .map((line) => ({
            payment_method:
              line.payment_method_code ||
              line.payment_method ||
              false,
            amount: Math.abs(Number(line.amount || 0)),
          }))
          .filter((line) => !!line.payment_method && isPositive(line.amount));

        const refundTotal = Math.abs(
          roundAmount(
            vef_base
              ? order.get_total_with_tax()
              : (typeof order.get_foreign_total_with_tax === "function"
                ? order.get_foreign_total_with_tax()
                : order.get_total_with_tax())
          )
        );

        if (sourcePayments.length && isPositive(refundTotal)) {
          const totalSource = sourcePayments.reduce((acc, line) => acc + line.amount, 0);
          let remaining = refundTotal;

          invoice['payment_lines'] = sourcePayments
            .map((line, index) => {
              const isLastLine = index === sourcePayments.length - 1;
              let amount = isLastLine || floatIsZero(totalSource, decimalPlaces)
                ? remaining
                : roundAmount((refundTotal * line.amount) / totalSource);

              if (amount > remaining) {
                amount = remaining;
              }

              remaining = roundAmount(remaining - amount);

              return {
                payment_method: line.payment_method,
                amount: -Math.abs(amount),
              };
            })
            .filter((line) => isNegative(line.amount));
        }
      }

      if (!invoice['payment_lines'].length) {
        return {
          valid: false,
          message: "No hay líneas de pago válidas para enviar a la máquina fiscal",
        }
      }
    }
    
    invoice["valid"] = true
    console.log("MF::get_data_invoice - payment_lines generados:", JSON.stringify(invoice.payment_lines));
    console.log("MF::get_data_invoice - tipo:", invoice.type, "total:", total);
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

  _stripHtml(text) {
    return String(text || "").replace(/<[^>]*>/g, " ");
  },

  _extractReceiptLines(fieldName) {
    const source = this._stripHtml(this.config?.[fieldName] || "")
      .split("\n")
      .map((line) => line.replace(/\r/g, "").trim())
      .filter((line) => line.length > 0);

    const lines = [];
    for (const line of source) {
      if (lines.length >= 10) {
        break;
      }
      lines.push(line.substring(0, 127));
    }
    return lines;
  },

  /**
   * Guarda los datos de la máquina fiscal en la orden
   * @param {Object} order
   * @param {Object} response - Respuesta del driver
   */
  set_data_from_fiscal_machine(order, response) {
    order.fiscal_machine = response.serial || response.serial_machine || "TFHKA-LOCAL";
    order.mf_invoice_number = response.invoiceNumber || response.invoice_number || "";
    order.mf_reportz = response.reportZ || response.mf_reportz || "";
  },

  /**
   * Envía la orden a la máquina fiscal (reemplaza pushToMF del IoT)
   * @param {Object} order
   * @returns {Promise<Object>}
   */
  async pushToMF(order) {
    try {
      const fiscalPrinter = this.getFiscalPrinter();

      if (!fiscalPrinter) {
        throw {
          valid: false,
          message: "Máquina fiscal no configurada.",
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

      // Enviar a imprimir según tipo de documento. withConnection() abre el
      // puerto serial bajo demanda solo por la duración de esta impresión y
      // lo libera al terminar (evita disputar el puerto con Megasoft).
      let response;
      try {
        response = await fiscalPrinter.withConnection(async () => {
          if (data.type === 'out_invoice') {
            return await fiscalPrinter.printInvoice(driverOrder);
          } else if (data.type === 'out_refund') {
            return await fiscalPrinter.printCreditNote(driverOrder);
          } else if (data.type === 'out_debit') {
            return await fiscalPrinter.printDebitNote(driverOrder);
          }
          return { success: false, error: `Tipo de documento no soportado: ${data.type}` };
        });
      } catch (connError) {
        throw {
          valid: false,
          message: connError.message || "No se pudo conectar con la máquina fiscal.",
          printer_connection: false,
        };
      }

      if (!response.success) {
        throw { 
          valid: false, 
          message: response.error || "Error al imprimir en la máquina fiscal",
          printer_connection: true 
        };
      }

      // Aviso: descuento global POS excedió subtotal y fue clampeado a 100%
      if (response.global_clamped) {
        const amount = Number(response.global_discount_amount || 0);
        const appliedRate = Number(response.global_discount_rate || 0).toFixed(2);
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Aviso de descuento"),
          body: _t(
            `El descuento global (${amount.toFixed(2)} Bs) excede el subtotal de las líneas. ` +
            `Se aplicó el máximo permitido (${appliedRate}%) en el comprobante.`
          ),
        });
      }

      // Guardar datos de la MF en la orden
      this.set_data_from_fiscal_machine(order, response);
      LocalOrderHistory.add(order);

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
   * Aplica un descuento porcentual a un precio base.
   *
   * Función reutilizable: se invoca primero con `line.discount` y luego, si
   * hay descuento global POS, con la tasa global redistribuida sobre el neto
   * (Estrategia A del documento DISCOUNT_STRATEGY.md).
   *
   * @param {number} unitPrice - Precio base antes del descuento
   * @param {number} percent - Porcentaje a descontar (0-100)
   * @returns {number} Precio neto redondeado
   */
  _applyDiscount(unitPrice, percent) {
    const value = Number(unitPrice || 0) * (1 - Number(percent || 0) / 100);
    return round_pr(value, this.currency?.rounding || 0.01);
  },

  _isGlobalDiscountProductLine(line) {
    const discountProductId = this.config?.discount_product_id?.[0];
    if (!discountProductId || !line?.get_product) {
      return false;
    }
    return Number(line.get_product()?.id || 0) === Number(discountProductId);
  },

  /**
   * Resetea el descuento de TODAS las líneas positivas a 0%.
   *
   * El descuento global POS siempre sobreescribe cualquier descuento previo
   * (manual o de una asignación global anterior) en vez de componerse con
   * él. Esto evita que las líneas agregadas después de un descuento global
   * queden con una tasa distinta a las líneas originales.
   */
  _resetGlobalDiscountOnLines(order) {
    for (const line of [...(order.orderlines || [])]) {
      if (this._isGlobalDiscountProductLine(line)) {
        continue;
      }
      if (typeof line.set_discount === "function") {
        line.set_discount(0);
      } else {
        line.discount = 0;
      }
    }
  },

  /**
   * Infiere el porcentaje de descuento que el usuario realmente tecleó en
   * el botón de descuento global, y los datos crudos necesarios para
   * redistribuirlo.
   *
   * El botón de descuento (`pos_discount`/`binaural_pos_discount`) calcula
   * el monto de la línea de descuento con `order.calculate_base_amount`,
   * que suma los precios de línea YA netos de cualquier descuento previo
   * (incluyendo un descuento global anterior convertido en descuento por
   * línea). Por eso el monto de la línea de descuento NO representa
   * `pc% del precio crudo`, sino `pc% del subtotal ya descontado`.
   *
   * Aquí revertimos ese cálculo: `pc = montoDescuento / subtotalActual *
   * 100`. Ese `pc` es el que luego se aplica de forma plana sobre los
   * precios crudos (después de resetear todas las líneas a 0%).
   *
   * @returns {{ discountLines: Array, pendingDiscountAmount: number, inferredPercent: number, clamped: boolean }|null}
   */
  _inferGlobalDiscountPercent(order) {
    const allLines = [...(order.orderlines || [])];
    const discountLines = [];
    let pendingDiscountAmount = 0;
    let currentDiscountedTotal = 0;

    for (const line of allLines) {
      const quantity = Math.abs(Number(line.get_quantity?.() ?? line.quantity ?? 0));
      if (!quantity) {
        continue;
      }

      const unitPrice = Number(line.get_unit_price?.() ?? line.price ?? 0);

      if (this._isGlobalDiscountProductLine(line)) {
        if (unitPrice < 0) {
          pendingDiscountAmount += Math.abs(unitPrice * quantity);
          discountLines.push(line);
        }
        continue;
      }

      const lineDiscount = Number(line.get_discount?.() ?? line.discount ?? 0);
      const netAfterLineDiscount = this._applyDiscount(unitPrice, lineDiscount);
      currentDiscountedTotal += Math.abs(netAfterLineDiscount * quantity);
    }

    if (pendingDiscountAmount <= 0) {
      return null;
    }

    let inferredPercent = 100;
    let clamped = true;
    if (currentDiscountedTotal > 0) {
      const rawRate = (pendingDiscountAmount / currentDiscountedTotal) * 100;
      inferredPercent = rawRate > 100 ? 100 : round_pr(rawRate, 0.01);
      clamped = rawRate > 100;
    }

    return { discountLines, pendingDiscountAmount, inferredPercent, clamped };
  },

  _applyGlobalDiscountBeforeValidation(order, { force = false } = {}) {
    const hasPendingDiscountLines = [...(order.orderlines || [])].some(
      (line) => this._isGlobalDiscountProductLine(line) && Number(line.get_unit_price?.() ?? line.price ?? 0) < 0
    );

    if (!force && order._mf_global_discount_applied && !hasPendingDiscountLines) {
      return order._mf_global_discount_meta || null;
    }

    if (!hasPendingDiscountLines) {
      return order._mf_global_discount_meta || null;
    }

    // Inferir el % real ANTES de tocar ninguna línea (ver docstring de
    // _inferGlobalDiscountPercent).
    const inference = this._inferGlobalDiscountPercent(order);
    if (!inference) {
      return order._mf_global_discount_meta || null;
    }

    // Resetear todas las líneas a 0% para que la tasa se aplique sobre
    // precios crudos, sin componerse con descuentos previos.
    this._resetGlobalDiscountOnLines(order);

    const positiveLines = [...(order.orderlines || [])].filter((line) => {
      const quantity = Math.abs(Number(line.get_quantity?.() ?? line.quantity ?? 0));
      const unitPrice = Number(line.get_unit_price?.() ?? line.price ?? 0);
      return quantity > 0 && unitPrice >= 0;
    });

    for (const line of positiveLines) {
      if (typeof line.set_discount === "function") {
        line.set_discount(inference.inferredPercent);
      } else {
        line.discount = inference.inferredPercent;
      }
    }

    for (const line of inference.discountLines) {
      order.orderlines.remove(line);
    }

    let rawTotal = 0;
    for (const line of positiveLines) {
      const quantity = Math.abs(Number(line.get_quantity?.() ?? line.quantity ?? 0));
      const unitPrice = Number(line.get_unit_price?.() ?? line.price ?? 0);
      rawTotal += Math.abs(unitPrice * quantity);
    }
    const correctedAmount = round_pr(
      (rawTotal * inference.inferredPercent) / 100,
      this.currency?.rounding || 0.01
    );

    order._mf_global_discount_applied = true;
    order._mf_global_discount_meta = {
      global_discount_amount: correctedAmount,
      global_discount_rate: inference.inferredPercent,
      global_clamped: inference.clamped,
    };

    return order._mf_global_discount_meta;
  },

  _onReactiveOrderUpdated(order) {
    if (!this._mf_global_discount_syncing) {
      this._mf_global_discount_syncing = true;
      try {
        this._applyGlobalDiscountBeforeValidation(order, { force: true });
      } finally {
        this._mf_global_discount_syncing = false;
      }
    }

    return super._onReactiveOrderUpdated(...arguments);
  },

  /**
   * Convierte la orden de Odoo al formato esperado por el driver
   *
   * Estrategia A (ver DISCOUNT_STRATEGY.md):
   * - El descuento por línea se aplica primero al precio base.
   * - El descuento global POS (representado por líneas negativas en
   *   `invoice_lines`) se prorratea sobre la base ya neta de las líneas
   *   positivas y se aplica en cascada.
   * - Si la tasa global supera el 100%, se clampa a 100% y se marca
   *   `global_clamped` para que el driver emita una línea informativa de
   *   aviso y muestre un pop-up al usuario.
   *
   * @param {Object} order
   * @param {Object} invoiceData
   * @returns {Object}
   */
  _convertOrderForDriver(order, invoiceData) {
    const preAppliedMeta = order?._mf_global_discount_meta || null;
    let globalDiscountAmount = Number(preAppliedMeta?.global_discount_amount || 0);
    let globalRate = Number(preAppliedMeta?.global_discount_rate || 0);
    let globalClamped = Boolean(preAppliedMeta?.global_clamped);
    const POSITIVE_LINES = [];
    const allLines = (invoiceData.invoice_lines || []);

    for (const line of allLines) {
      const priceUnit = Number(line.price_unit || 0);
      if (priceUnit < 0) {
        if (!preAppliedMeta) {
          globalDiscountAmount += Math.abs(priceUnit);
        }
        continue;
      }
      POSITIVE_LINES.push(line);
    }

    if (!preAppliedMeta) {
      let positiveBaseSum = 0;
      for (const line of POSITIVE_LINES) {
        const priceUnit = Number(line.price_unit || 0);
        const quantity = Math.abs(Number(line.quantity || 1));
        const lineDiscount = Number(line.discount || 0);
        const netAfterLineDiscount = this._applyDiscount(priceUnit, lineDiscount);
        positiveBaseSum += Math.abs(netAfterLineDiscount * quantity);
      }

      globalRate = 0;
      globalClamped = false;
      if (globalDiscountAmount > 0 && positiveBaseSum > 0) {
        const rawRate = (globalDiscountAmount / positiveBaseSum) * 100;
        if (rawRate > 100) {
          globalRate = 100;
          globalClamped = true;
        } else {
          globalRate = rawRate;
        }
      }
    }

    const lines = POSITIVE_LINES.map((line) => {
      const priceUnit = Number(line.price_unit || 0);
      const lineDiscount = Number(line.discount || 0);
      const netAfterLineDiscount = this._applyDiscount(priceUnit, lineDiscount);
      const finalUnitPrice = preAppliedMeta
        ? netAfterLineDiscount
        : this._applyDiscount(netAfterLineDiscount, globalRate);
      return {
        product_name: line.name,
        product_code: line.code || line.default_code,
        price_unit: finalUnitPrice,
        quantity: line.quantity,
        fiscal_code: line.tax,  // 0=Exento, 1=General, 2=Reducido, 3=Adicional
        discount: 0,
      };
    });

    const payment_lines = (invoiceData.payment_lines || []).map(payment => ({
      payment_method_code: payment.payment_method,
      amount: Math.abs(payment.amount)
    }));

    console.log("MF::_convertOrderForDriver - payment_lines:", JSON.stringify(payment_lines));

    return {
      partner: invoiceData.partner_id || null,
      lines: lines,
      payment_lines: payment_lines,
      flag_21: invoiceData.flag_21 || this.get_flag_21 || "00",
      has_cashbox: invoiceData.has_cashbox || false,
      additional_lines: invoiceData.info || [],
      invoice_affected: invoiceData.invoice_affected || null,
      global_discount_amount: globalDiscountAmount,
      global_discount_rate: globalRate,
      global_clamped: globalClamped,
      header_lines: this._extractReceiptLines("receipt_header"),
      footer_lines: this._extractReceiptLines("receipt_footer"),
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
    this._applyGlobalDiscountBeforeValidation(order);

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
    // Solo si el pedido se marcó como "Factura" (order.is_to_invoice()) en la
    // pantalla de validación. Si se seleccionó "Recibo", el pedido se imprime
    // por la tickera comun (browser/kiosk-printing), nunca por la maquina fiscal.
    if (this.useFiscalMachine() && order.is_to_invoice() && !order.mf_invoice_number) {
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

    for (let i = buffer.length - 1; i >= 0; i--) {
      const entry = buffer[i];
      
      try {
        // Reconstruir la orden y sincronizar
        const orderPayload = [{
          'data': entry.orderData
        }];
        
        // Intentar crear la orden en el backend
        await this.orm.call("pos.order", "create_from_ui", [orderPayload]);
        
        LocalOrderBuffer.remove(i);
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
  },
})
