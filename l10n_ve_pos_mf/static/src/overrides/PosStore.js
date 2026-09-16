/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { floatIsZero, roundPrecision as round_pr } from "@web/core/utils/numbers";
import { LocalOrderHistory } from "../utils/LocalOrderHistory";

/**
 * Hand-off del puerto COM entre la máquina fiscal (Web Serial) y procesos
 * externos que necesitan el mismo puerto (p.ej. el VPOS de Megasoft, un
 * proceso Windows separado). Web Serial abre el puerto UNA vez y lo mantiene
 * con lock exclusivo toda la sesión, así que mientras el navegador lo tenga
 * abierto ningún otro proceso puede usarlo. Este módulo (dueño de la MF)
 * expone `withFiscalPrinterReleased()`: cede el puerto (disconnect), corre la
 * sección crítica externa y luego lo reclama con reintentos silenciosos.
 * Antes esta lógica vivía duplicada en binaural_megasoft/PosState.js.
 */
const MF_PORT_HANDOFF_GRACE_MS = 1000;
const MF_PORT_RECLAIM_MAX_ATTEMPTS = 3;
const MF_PORT_RECLAIM_RETRY_DELAY_MS = 750;

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

  _sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  },

  /**
   * Ejecuta `criticalSection` cediendo temporalmente el puerto de la máquina
   * fiscal a un proceso externo (p.ej. el VPOS de Megasoft) que necesita el
   * mismo COM. Si la MF está conectada: la desconecta antes, corre la
   * sección, y la reclama después (reconexión silenciosa con reintentos). Si
   * la MF no está instalada/conectada, simplemente corre la sección.
   *
   * El resultado devuelto y las excepciones lanzadas por `criticalSection`
   * se propagan intactos; el reclamo del puerto ocurre siempre (finally).
   *
   * @param {() => Promise<any>} criticalSection
   * @returns {Promise<any>}
   */
  async withFiscalPrinterReleased(criticalSection) {
    const fiscalPrinter = this.getFiscalPrinter();
    // Gestionar el puerto si el driver se dice conectado O si la conexión
    // todavía retiene el puerto físico (caso: autoConnect abrió pero getStatus
    // falló → driver.isConnected=false pero el COM sigue tomado con lock). Sin
    // esto, el proceso externo (Megasoft) no podría abrir el COM ocupado.
    const shouldManagePort = Boolean(
      fiscalPrinter && (fiscalPrinter.isConnected || fiscalPrinter.connection?.port)
    );

    if (shouldManagePort) {
      try {
        await fiscalPrinter.disconnect();
      } catch (e) {
        // No abortar la sección crítica solo porque nuestra propia
        // desconexión falló; el proceso externo puede necesitar el puerto
        // igual y seguiremos intentando reclamarlo después.
        console.warn(
          "[l10n_ve_pos_mf] falló la desconexión de la máquina fiscal antes de ceder el puerto, se continúa igual",
          e
        );
      }
    }

    try {
      return await criticalSection();
    } finally {
      if (shouldManagePort) {
        const reclaimed = await this._reclaimFiscalPrinterPort(fiscalPrinter);
        if (!reclaimed) {
          this._notifyFiscalPrinterReclaimFailed();
        }
        // Reflejar el estado real en el botón de la MF (que no observa el
        // driver directamente): tras un reclaim fallido no debe seguir verde.
        this._broadcastFiscalStatus(Boolean(fiscalPrinter.isConnected));
      }
    }
  },

  /**
   * Notifica el estado de conexión de la máquina fiscal a componentes que no
   * observan el driver directamente (p.ej. FiscalPrinterButton), vía evento
   * de ventana.
   * @param {boolean} connected
   */
  _broadcastFiscalStatus(connected) {
    try {
      window.dispatchEvent(
        new CustomEvent("mf-fiscal-status", { detail: { connected: Boolean(connected) } })
      );
    } catch (_e) {
      // dispatch no debe tirar por sí mismo
    }
  },

  /**
   * Espera el margen de gracia y reintenta reconectar la máquina fiscal
   * (autoConnect silencioso, sin gesto de usuario) hasta
   * MF_PORT_RECLAIM_MAX_ATTEMPTS veces.
   * @param {Object} fiscalPrinter
   * @returns {Promise<boolean>}
   */
  async _reclaimFiscalPrinterPort(fiscalPrinter) {
    await this._sleep(MF_PORT_HANDOFF_GRACE_MS);
    for (let attempt = 1; attempt <= MF_PORT_RECLAIM_MAX_ATTEMPTS; attempt++) {
      try {
        await fiscalPrinter.connect();
        if (fiscalPrinter.isConnected) {
          return true;
        }
      } catch (e) {
        console.warn(
          `[l10n_ve_pos_mf] intento ${attempt}/${MF_PORT_RECLAIM_MAX_ATTEMPTS} de reclamar la máquina fiscal falló`,
          e
        );
      }
      if (attempt < MF_PORT_RECLAIM_MAX_ATTEMPTS) {
        await this._sleep(MF_PORT_RECLAIM_RETRY_DELAY_MS);
      }
    }
    return false;
  },

  _notifyFiscalPrinterReclaimFailed() {
    try {
      this.env.services.notification.add(
        _t(
          "No se pudo reconectar automáticamente la máquina fiscal tras la operación externa. " +
            "Verifique la conexión desde el botón de máquina fiscal antes de validar la próxima orden."
        ),
        { type: "warning", sticky: true }
      );
    } catch (_e) {
      console.warn(
        "[l10n_ve_pos_mf] no se pudo mostrar el aviso de reconexión de la máquina fiscal",
        _e
      );
    }
  },

  async applyDiscount(percent, order = this.getOrder(), options = {}) {
    if (!order || order.state !== "draft") {
      return;
    }

    if (order._mf_applying_global_discount) {
      return;
    }

    const discountPercent = Number(percent || 0);
    const isManualTrigger = Boolean(
      options?.mfManualTrigger || this._mf_manual_discount_trigger
    );
    const hasPendingDiscountLines = [...(order.lines || [])].some(
      (line) =>
        this._isGlobalDiscountProductLine(line) &&
        Number(line.getUnitPrice?.() ?? line.price_unit ?? 0) < 0
    );

    // Evita loops por re-disparos debounced del pos_discount cuando
    // ya normalizamos la orden al modo descuento por línea.
    if (!isManualTrigger && !hasPendingDiscountLines) {
      return;
    }

    order._mf_applying_global_discount = true;
    try {
      const result = await super.applyDiscount(percent, order);

      if (discountPercent <= 0) {
        this._resetGlobalDiscountOnLines(order);
        order._mf_global_discount_applied = false;
        order._mf_global_discount_meta = null;
        order._mf_last_applied_discount_percent = 0;
        return result;
      }

      this._applyGlobalDiscountBeforeValidation(order, {
        force: true,
        expectedPercent: discountPercent,
      });
      return result;
    } finally {
      order._mf_applying_global_discount = false;
    }
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
          name: this.normalizeProductName(
            String(line.product_id?.display_name || "").replace(/^\[[^\]]*\]\s*/, "")
          ),
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

  _applyGlobalDiscountBeforeValidation(order, { force = false, expectedPercent = null } = {}) {
    if (!order || order.state !== "draft") {
      return order?._mf_global_discount_meta || null;
    }

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

    // Remover primero las líneas de descuento global para que
    // globalDiscountPc sea 0 antes de modificar líneas y evitar
    // re-disparos del debounce de pos_discount.
    //
    // Se usa `line.delete()` (borrado síncrono, igual que hace el propio
    // `pos_discount` con sus líneas de descuento) y NO `order.removeOrderline()`:
    // este último lo sobreescribe `binaural_pos_hr` como método ASYNC que, con
    // `pos_remove_orderline_require_supervisor_key`, abre un popup de supervisor
    // y sólo elimina la línea tras el PIN. Como aquí no se espera esa promesa,
    // la línea de descuento nunca se eliminaba: `globalDiscountPc` seguía ≠ 0 y
    // el `setDiscount()` de más abajo re-disparaba el debounce de `pos_discount`
    // → re-entrada infinita en applyDiscount → popups de supervisor apilados que
    // congelaban la caja (pantalla negra). Estas líneas son gestionadas por el
    // sistema, no por el cajero, así que su borrado no debe pasar por el gate.
    for (const line of inference.discountLines) {
      line.delete();
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
    order._mf_last_applied_discount_percent = Number(
      expectedPercent ?? inference.inferredPercent ?? 0
    );

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
