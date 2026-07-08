/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { floatIsZero, roundPrecision as round_pr } from "@web/core/utils/numbers";
import { LocalOrderHistory } from "../utils/LocalOrderHistory";

/**
 * Override del PosStore para integrar la máquina fiscal vía Web Serial API.
 *
 * Migración Odoo 17 → 19:
 * - Imports: @point_of_sale/app/store/pos_store → app/services/pos_store
 * - Popups: ErrorPopup → dialog service + AlertDialog
 * - Orden: order.uid → order.uuid, orderlines → lines,
 *   paymentlines → payment_ids, get_total_with_tax() → totalDue
 * - Refunds: toRefundLines → line.refunded_orderline_id (relación directa)
 * - Offline: el core 19 ya persiste órdenes pendientes (IndexedDB) y las
 *   re-sincroniza; se eliminó LocalOrderBuffer. LocalOrderHistory se mantiene
 *   para recuperar datos fiscales de la factura original en NC offline.
 * - El hook de flujo de validación vive en overrides/OrderPaymentValidation.js
 */
patch(PosStore.prototype, {
  /**
   * Abre la gaveta usando el comando directo a la máquina fiscal.
   * En 19 la firma es openCashbox(action) (cash in/out manual).
   */
  async openCashbox(action) {
    const fiscalPrinter = this.getFiscalPrinter();

    if (fiscalPrinter && fiscalPrinter.isConnected && this.config.has_cashbox) {
      try {
        const result = await fiscalPrinter.openDrawer();
        if (!result.success) {
          console.error("FiscalPrinter:: Error abriendo gaveta", result.error);
        }
        return;
      } catch (error) {
        console.error("FiscalPrinter:: Error abriendo gaveta", error);
        return super.openCashbox(...arguments);
      }
    }
    return super.openCashbox(...arguments);
  },

  /**
   * Obtiene la instancia del driver de la máquina fiscal
   * @returns {TfhkaDriver|null}
   */
  getFiscalPrinter() {
    return window.fiscalPrinter || null;
  },

  /**
   * Verifica si se debe usar la máquina fiscal
   * @returns {boolean}
   */
  useFiscalMachine() {
    const fiscalPrinter = this.getFiscalPrinter();
    return Boolean(fiscalPrinter && fiscalPrinter.isConnected);
  },

  aditionalInfo(order) {
    const res = [];
    const cashier = this.getCashier();
    if (cashier?.name) {
      res.push(`OPERADOR: ${cashier.name}`);
    }
    const reference = order?.pos_reference || order?.uuid || this.getOrder()?.uuid;
    if (reference) {
      res.push(`PEDIDO: ${reference}`);
    }
    return res;
  },

  get get_flag_21() {
    return this.config.flag_21;
  },

  get get_traditional_line() {
    return this.config.traditional_line;
  },

  get has_cashbox() {
    return this.config.has_cashbox;
  },

  is_same_mf(serial) {
    return true;
  },

  _mfShowError(title, body) {
    this.dialog.add(AlertDialog, { title, body });
  },

  /**
   * Devuelve las líneas de devolución de la orden (relación directa en 19)
   */
  _mfGetRefundLines(order) {
    return [...(order.lines || [])].filter((line) => line.refunded_orderline_id);
  },

  /**
   * Recupera los datos fiscales de la orden original afectada por una NC.
   * Prioridad: registro cargado en memoria → historial local (offline) →
   * RPC get_order_by_uid.
   */
  async _mfGetAffectedOrderData(order, refundLines) {
    const originalLine = refundLines[0]?.refunded_orderline_id;
    const originalOrder = originalLine?.order_id;

    if (originalOrder?.mf_invoice_number) {
      return {
        pos_reference: originalOrder.pos_reference,
        date_order: originalOrder.date_order,
        fiscal_machine: originalOrder.fiscal_machine,
        mf_invoice_number: originalOrder.mf_invoice_number,
        mf_reportz: originalOrder.mf_reportz,
        payment_lines: (originalOrder.payment_ids || []).map((p) => ({
          payment_method_code: p.payment_method_id?.code_fiscal_printer || false,
          payment_method_name: p.payment_method_id?.name || "",
          amount: p.amount,
        })),
      };
    }

    const originalUid = originalOrder?.uuid || originalOrder?.pos_reference;
    if (originalUid) {
      const localOrder = LocalOrderHistory.getByUid(originalUid);
      if (localOrder) {
        return localOrder;
      }

      try {
        const response = await this.data.call("pos.order", "get_order_by_uid", [
          [],
          originalUid,
        ]);
        if (response.length > 0) {
          return response[0];
        }
      } catch (err) {
        console.error("MF error: ", err);
      }
    }

    return null;
  },

  /**
   * Construye el objeto de datos de la factura para enviar a la máquina fiscal
   * @param {Object} order - Orden del POS (registro pos.order del modelo 19)
   * @returns {Promise<Object>}
   */
  async get_data_invoice(order) {
    const invoice = {
      company_id: {
        name: this.company.name,
      },
      flag_21: this.get_flag_21,
      traditional_line: this.get_traditional_line,
      has_cashbox: this.has_cashbox && order.isPaidWithCash(),
      time: Date.now(),
    };

    const client = order.getPartner();
    if (client) {
      invoice["partner_id"] = {
        vat: `${client.prefix_vat || ""}${client.vat || ""}`,
        name: this.normalizeProductName(client.name),
        address: client.street || false,
        phone: client.phone || client.mobile || false,
      };
    }

    invoice["info"] = this.aditionalInfo(order);

    const refundLines = this._mfGetRefundLines(order);
    const hasRefundLines = refundLines.length > 0;
    const total = order.totalDue;
    let affectedOrderData = null;

    if (total >= 0 && !hasRefundLines) {
      invoice["type"] = "out_invoice";
    } else {
      invoice["type"] = "out_refund";
    }

    if (invoice["type"] === "out_refund") {
      affectedOrderData = await this._mfGetAffectedOrderData(order, refundLines);

      if (!affectedOrderData) {
        return {
          valid: false,
          message: _t(
            "No se pudo recuperar la factura original para emitir la nota de credito"
          ),
        };
      }

      if (!affectedOrderData.mf_invoice_number) {
        return {
          valid: false,
          message: _t(
            "La orden original no tiene número de factura fiscal registrado"
          ),
        };
      }

      if (!this.is_same_mf(affectedOrderData.fiscal_machine)) {
        return {
          valid: false,
          message: `El documento fue impreso desde la Maquina ${affectedOrderData.fiscal_machine}`,
        };
      }

      const date = new Date(affectedOrderData.date_order);
      const format_date = date.toLocaleDateString("es-ES");

      invoice["invoice_affected"] = {
        number: affectedOrderData.mf_invoice_number,
        serial_machine: affectedOrderData.fiscal_machine,
        date: format_date,
      };
    }

    const orderLines = [...(order.lines || [])];
    if (orderLines.length > 0) {
      const vef_base = this.currency.name === "VEF" || this.currency.name === "VES";
      const foreignCurrency = this.config.foreign_currency_id;
      const decimalPlaces = vef_base
        ? this.currency.decimal_places
        : foreignCurrency?.decimal_places || this.currency.decimal_places;
      const rounding = vef_base
        ? this.currency.rounding
        : foreignCurrency?.rounding || this.currency.rounding;
      const roundAmount = (amount) => round_pr(amount, rounding);
      const isPositive = (amount) => {
        const rounded = roundAmount(amount);
        return !floatIsZero(rounded, decimalPlaces) && rounded > 0;
      };
      const isNegative = (amount) => {
        const rounded = roundAmount(amount);
        return !floatIsZero(rounded, decimalPlaces) && rounded < 0;
      };

      invoice["invoice_lines"] = orderLines.map((line) => {
        const note = line.customer_note || line.getCustomerNote?.() || "";
        if (note) {
          for (const noteLine of String(note).split("\n")) {
            invoice["info"].push(`${noteLine}`);
          }
        }

        const amount = vef_base
          ? line.price_unit
          : line.get_foreign_unit_price?.() ?? line.price_unit;

        const taxes = line.tax_ids || [];
        const fiscalCode =
          taxes.length > 0
            ? String(taxes[0]?.fiscal_code ?? "").replace(/^t/i, "") || "0"
            : "0";

        return {
          price_unit: amount,
          discount: line.getDiscount(),
          quantity: Math.abs(line.qty),
          name: this.normalizeProductName(line.product_id?.display_name),
          code: line.product_id?.default_code,
          tax: fiscalCode,
        };
      });

      invoice["payment_lines"] = [...(order.payment_ids || [])]
        .map((payment) => {
          const amount = vef_base
            ? payment.amount
            : payment.get_foreign_amount?.() ?? payment.amount;
          return {
            payment_method: payment.payment_method_id?.code_fiscal_printer || false,
            amount: roundAmount(amount),
          };
        })
        .filter((line) => {
          if (!line.payment_method) {
            return false;
          }
          if (invoice.type === "out_refund") {
            return isNegative(line.amount);
          }
          return isPositive(line.amount);
        });

      if (
        invoice.type === "out_refund" &&
        !invoice["payment_lines"].length &&
        affectedOrderData?.payment_lines?.length
      ) {
        const sourcePayments = affectedOrderData.payment_lines
          .map((line) => ({
            payment_method: line.payment_method_code || line.payment_method || false,
            amount: Math.abs(Number(line.amount || 0)),
          }))
          .filter((line) => !!line.payment_method && isPositive(line.amount));

        const refundTotal = Math.abs(
          roundAmount(
            vef_base
              ? order.totalDue
              : typeof order.get_foreign_total_with_tax === "function"
              ? order.get_foreign_total_with_tax()
              : order.totalDue
          )
        );

        if (sourcePayments.length && isPositive(refundTotal)) {
          const totalSource = sourcePayments.reduce((acc, line) => acc + line.amount, 0);
          let remaining = refundTotal;

          invoice["payment_lines"] = sourcePayments
            .map((line, index) => {
              const isLastLine = index === sourcePayments.length - 1;
              let amount =
                isLastLine || floatIsZero(totalSource, decimalPlaces)
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

      if (!invoice["payment_lines"].length) {
        return {
          valid: false,
          message: "No hay líneas de pago válidas para enviar a la máquina fiscal",
        };
      }
    }

    invoice["valid"] = true;
    return invoice;
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
    order.mf_reportz = String(response.reportZ || response.mf_reportz || "");
  },

  /**
   * Envía la orden a la máquina fiscal
   * @param {Object} order
   * @returns {Promise<Object>}
   */
  async pushToMF(order) {
    try {
      const fiscalPrinter = this.getFiscalPrinter();

      if (!fiscalPrinter || !fiscalPrinter.isConnected) {
        throw {
          valid: false,
          message:
            "Máquina fiscal no conectada. Haz clic en el botón de impresora para conectar.",
          printer_connection: false,
        };
      }

      // Construir datos de la factura
      const data = await this.get_data_invoice(order);
      if (!data["valid"]) {
        throw { valid: false, message: data["message"] };
      }

      // Convertir formato de Odoo a formato del driver
      const driverOrder = this._convertOrderForDriver(order, data);

      // Enviar a imprimir según tipo de documento
      let response;
      if (data.type === "out_invoice") {
        response = await fiscalPrinter.printInvoice(driverOrder);
      } else if (data.type === "out_refund") {
        response = await fiscalPrinter.printCreditNote(driverOrder);
      } else if (data.type === "out_debit") {
        response = await fiscalPrinter.printDebitNote(driverOrder);
      } else {
        response = {
          success: false,
          error: `Tipo de documento no soportado: ${data.type}`,
        };
      }

      if (!response.success) {
        throw {
          valid: false,
          message: response.error || "Error al imprimir en la máquina fiscal",
          printer_connection: true,
        };
      }

      // Aviso: descuento global POS excedió subtotal y fue clampeado a 100%
      if (response.global_clamped) {
        const amount = Number(response.global_discount_amount || 0);
        const appliedRate = Number(response.global_discount_rate || 0).toFixed(2);
        this._mfShowError(
          _t("Aviso de descuento"),
          _t(
            `El descuento global (${amount.toFixed(2)} Bs) excede el subtotal de las líneas. ` +
              `Se aplicó el máximo permitido (${appliedRate}%) en el comprobante.`
          )
        );
      }

      // Guardar datos de la MF en la orden
      this.set_data_from_fiscal_machine(order, response);
      LocalOrderHistory.add({
        uid: order.uuid,
        pos_reference: order.pos_reference,
        date_order: order.date_order,
        fiscal_machine: order.fiscal_machine,
        mf_invoice_number: order.mf_invoice_number,
        mf_reportz: order.mf_reportz,
        payment_lines: [...(order.payment_ids || [])].map((p) => ({
          payment_method_code: p.payment_method_id?.code_fiscal_printer || false,
          payment_method_name: p.payment_method_id?.name || "",
          amount: p.amount,
        })),
      });

      return {
        valid: true,
        message: "",
        printer_connection: true,
      };
    } catch (err) {
      console.error("MF error: ", err);

      if (err.valid === false) {
        this._mfShowError(
          _t("Error de Máquina Fiscal"),
          _t(err.message || "Error interno de la máquina fiscal")
        );
      }

      return err;
    }
  },

  /**
   * Aplica un descuento porcentual a un precio base.
   * (Estrategia A del documento DISCOUNT_STRATEGY.md)
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
    const discountProduct = this.config?.discount_product_id;
    const discountProductId = Array.isArray(discountProduct)
      ? discountProduct[0]
      : discountProduct?.id;
    if (!discountProductId) {
      return false;
    }
    return Number(line.product_id?.id || 0) === Number(discountProductId);
  },

  /**
   * Resetea el descuento de TODAS las líneas positivas a 0%.
   */
  _resetGlobalDiscountOnLines(order) {
    for (const line of [...(order.lines || [])]) {
      if (this._isGlobalDiscountProductLine(line)) {
        continue;
      }
      if (typeof line.setDiscount === "function") {
        line.setDiscount(0);
      } else {
        line.discount = 0;
      }
    }
  },

  /**
   * Infiere el porcentaje de descuento global tecleado por el usuario.
   * Ver DISCOUNT_STRATEGY.md (Estrategia A).
   *
   * @returns {{ discountLines: Array, pendingDiscountAmount: number, inferredPercent: number, clamped: boolean }|null}
   */
  _inferGlobalDiscountPercent(order) {
    const allLines = [...(order.lines || [])];
    const discountLines = [];
    let pendingDiscountAmount = 0;
    let currentDiscountedTotal = 0;

    for (const line of allLines) {
      const quantity = Math.abs(Number(line.getQuantity?.() ?? line.qty ?? 0));
      if (!quantity) {
        continue;
      }

      const unitPrice = Number(line.getUnitPrice?.() ?? line.price_unit ?? 0);

      if (this._isGlobalDiscountProductLine(line)) {
        if (unitPrice < 0) {
          pendingDiscountAmount += Math.abs(unitPrice * quantity);
          discountLines.push(line);
        }
        continue;
      }

      const lineDiscount = Number(line.getDiscount?.() ?? line.discount ?? 0);
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
    const hasPendingDiscountLines = [...(order.lines || [])].some(
      (line) =>
        this._isGlobalDiscountProductLine(line) &&
        Number(line.getUnitPrice?.() ?? line.price_unit ?? 0) < 0
    );

    if (!force && order._mf_global_discount_applied && !hasPendingDiscountLines) {
      return order._mf_global_discount_meta || null;
    }

    if (!hasPendingDiscountLines) {
      return order._mf_global_discount_meta || null;
    }

    // Inferir el % real ANTES de tocar ninguna línea
    const inference = this._inferGlobalDiscountPercent(order);
    if (!inference) {
      return order._mf_global_discount_meta || null;
    }

    // Resetear todas las líneas a 0% para aplicar la tasa sobre precios crudos
    this._resetGlobalDiscountOnLines(order);

    const positiveLines = [...(order.lines || [])].filter((line) => {
      const quantity = Math.abs(Number(line.getQuantity?.() ?? line.qty ?? 0));
      const unitPrice = Number(line.getUnitPrice?.() ?? line.price_unit ?? 0);
      return quantity > 0 && unitPrice >= 0;
    });

    for (const line of positiveLines) {
      if (typeof line.setDiscount === "function") {
        line.setDiscount(inference.inferredPercent);
      } else {
        line.discount = inference.inferredPercent;
      }
    }

    for (const line of inference.discountLines) {
      order.removeOrderline(line);
    }

    let rawTotal = 0;
    for (const line of positiveLines) {
      const quantity = Math.abs(Number(line.getQuantity?.() ?? line.qty ?? 0));
      const unitPrice = Number(line.getUnitPrice?.() ?? line.price_unit ?? 0);
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

  /**
   * Convierte la orden de Odoo al formato esperado por el driver.
   * (Estrategia A: ver DISCOUNT_STRATEGY.md)
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
    const allLines = invoiceData.invoice_lines || [];

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
        fiscal_code: line.tax, // 0=Exento, 1=General, 2=Reducido, 3=Adicional
        discount: 0,
      };
    });

    const payment_lines = (invoiceData.payment_lines || []).map((payment) => ({
      payment_method_code: payment.payment_method,
      amount: Math.abs(payment.amount),
    }));

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
});
