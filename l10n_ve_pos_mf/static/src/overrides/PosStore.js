/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { floatIsZero, roundPrecision as round_pr } from "@web/core/utils/numbers";
import { LocalOrderBuffer } from "../utils/LocalOrderBuffer";
import { LocalOrderHistory } from "../utils/LocalOrderHistory";
import { composeDiscountPercent, computeLineDiscountAmount } from "@l10n_ve_mf_base/core/DiscountMath";

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
          // % PURO de la regla de campaña (categoría/temporada/antigüedad),
          // ANTES de componerse con el descuento global del botón. Lo escribe
          // binaural_pos_pricelist_line_discount en `campaignDiscountPercent`
          // (su hermano `campaignDiscountAppliedPercent` es el ya compuesto, y
          // por eso NO sirve aquí). `_convertOrderForDriver` lo usa para
          // separar el descuento propio de la línea —que sale impreso con su
          // `q-`— del descuento global agregado, que va al pie del ticket.
          // Una línea sin campaña (o con descuento manual del cajero) llega
          // con 0 y su descuento entero se contabiliza como global.
          campaign_discount_percent: (el.campaignDiscountPercent != null ? Number(el.campaignDiscountPercent) : 0),
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
        // `amount` es un MONTO en la moneda de la orden: sus decimales deben
        // salir de la moneda de Odoo, no de un `toFixed(2)` fijo (una moneda
        // con más o menos de 2 decimales quedaría truncada/rellenada mal).
        // `appliedRate` es una TASA (%), no un monto: sus 2 decimales fijos
        // no cambian.
        const decimalPlaces = this.currency?.decimal_places ?? 2;
        const appliedRate = Number(response.global_discount_rate || 0).toFixed(2);
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Aviso de descuento"),
          body: _t(
            `El descuento global (${amount.toFixed(decimalPlaces)} Bs) excede el subtotal de las líneas. ` +
            `Se aplicó el máximo permitido (${appliedRate}%) en el comprobante.`
          ),
        });
      }

      // Aviso: el MONTO de descuento de una o más líneas no cabía en los
      // dígitos enteros que el Flag 21 reserva para el comando `q-`. El driver
      // imprimió esas líneas a su precio bruto SIN el renglón "DESC" para no
      // construir una trama malformada. Mismo mecanismo que el aviso de
      // `global_clamped` de arriba.
      const overflowLines = response.line_discount_overflow_lines || [];
      if (overflowLines.length) {
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Aviso de descuento"),
          body: _t(
            "El monto de descuento de %s línea(s) (%s) excede lo que la máquina fiscal puede imprimir. Esas líneas se imprimieron sin el renglón de descuento.",
            overflowLines.length,
            overflowLines.join(", ")
          ),
        });
      }

      // Aviso: el PRECIO BRUTO de una o más líneas no cabía en los dígitos
      // enteros que el Flag 21 reserva para el precio del ítem. Con el fix de
      // C2 (revisión formal), esto ya NO degrada sólo esas líneas: el driver
      // degrada TODO el documento a Estrategia A (precio neto, sin `q-` por
      // línea, pie con los montos históricos) para evitar duplicar el
      // descuento global en las líneas degradadas. El mensaje distingue ambos
      // casos usando `line_discount_via_q_document_degraded`.
      const grossOverflowLines = response.line_gross_price_overflow_lines || [];
      if (grossOverflowLines.length) {
        const body = response.line_discount_via_q_document_degraded
          ? _t(
              "El precio sin descuento de %s línea(s) (%s) excede lo que la máquina fiscal puede imprimir. " +
              "TODA la factura se imprimió en su formato histórico (precio ya descontado, sin renglones de descuento por línea) para no duplicar el descuento.",
              grossOverflowLines.length,
              grossOverflowLines.join(", ")
            )
          : _t(
              "El precio sin descuento de %s línea(s) (%s) excede lo que la máquina fiscal puede imprimir. Esas líneas se imprimieron a su precio ya descontado, sin el renglón de descuento.",
              grossOverflowLines.length,
              grossOverflowLines.join(", ")
            );
        this.env.services.popup.add(ErrorPopup, {
          title: _t("Aviso de descuento"),
          body,
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
   *
   * Excepción: las líneas con un descuento de campaña aplicado por un módulo
   * externo NO se resetean, se componen (ver abajo).
   */
  _resetGlobalDiscountOnLines(order) {
    for (const line of [...(order.orderlines || [])]) {
      if (this._isGlobalDiscountProductLine(line)) {
        continue;
      }
      if (line.campaignDiscountPercent != null) {
        // Descuento de línea aplicado por un módulo de campaña externo
        // (categoría/temporada/antigüedad, ej.
        // binaural_pos_pricelist_line_discount). Se preserva y se compone
        // con el % global en vez de resetear — ver el loop de aplicación
        // más abajo en _applyGlobalDiscountBeforeValidation.
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

    // El % inferido se calculó contra el subtotal YA neto de los descuentos
    // de línea vigentes (incluido el de campaña), así que sobre una línea con
    // campaña es la porción INCREMENTAL: hay que componerlo multiplicativamente
    // con el de campaña, no sumarlo ni reemplazarlo.
    for (const line of positiveLines) {
      // `!= null` y no truthy: una campaña de 0% es una marca válida (el
      // módulo de campaña la serializa como tal). Con truthy, esa línea no
      // actualizaría `campaignDiscountAppliedPercent` y quedaría con la marca
      // desfasada respecto del descuento realmente escrito — la misma
      // incoherencia que se corrigió del lado del módulo de campaña.
      const hasCampaign = line.campaignDiscountPercent != null;
      const campaignPct = Number(line.campaignDiscountPercent || 0);
      const combinedPct = hasCampaign
        ? composeDiscountPercent(campaignPct, inference.inferredPercent)
        : inference.inferredPercent;
      if (hasCampaign) {
        // Dejar registrado el % que realmente queda escrito en la línea (el
        // compuesto, no el puro de campaña). El módulo de campaña compara
        // contra este valor para decidir si puede limpiar el descuento
        // cuando su regla deja de aplicar; si aquí quedara el puro, nunca
        // coincidiría y el descuento compuesto se quedaría pegado.
        line.campaignDiscountAppliedPercent = combinedPct;
      }
      if (typeof line.set_discount === "function") {
        line.set_discount(combinedPct);
      } else {
        line.discount = combinedPct;
      }
    }

    for (const line of inference.discountLines) {
      order.orderlines.remove(line);
    }

    // Monto total realmente descontado, sumando el efectivo por línea con el
    // `discount` YA FINAL (campaña compuesta con global). No se puede usar
    // `subtotalCrudo * inferredPercent`: eso subestimaría el total en las
    // líneas con campaña, porque ignoraría la parte ya descontada por ella.
    // Este monto alimenta el texto "DESC. GLOBAL = X" del ticket fiscal y el
    // aviso de clamp.
    let totalDiscountAmount = 0;
    for (const line of positiveLines) {
      const quantity = Math.abs(Number(line.get_quantity?.() ?? line.quantity ?? 0));
      const unitPrice = Number(line.get_unit_price?.() ?? line.price ?? 0);
      const lineDiscount = Number(line.get_discount?.() ?? line.discount ?? 0);
      const discountedUnit = this._applyDiscount(unitPrice, lineDiscount);
      totalDiscountAmount += Math.abs((unitPrice - discountedUnit) * quantity);
    }
    const correctedAmount = round_pr(totalDiscountAmount, this.currency?.rounding || 0.01);

    order._mf_global_discount_applied = true;
    order._mf_global_discount_meta = {
      global_discount_amount: correctedAmount,
      global_discount_rate: inference.inferredPercent,
      global_clamped: inference.clamped,
    };

    return order._mf_global_discount_meta;
  },

  _onReactiveOrderUpdated(order) {
    if (!this.config.native_global_discount_line && !this._mf_global_discount_syncing) {
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
   * Estrategia C (ver DISCOUNT_STRATEGY.md, sección "Evolución"): además del
   * precio neto de arriba, cada línea lleva `gross_price_unit` (precio antes
   * de descuento) y `discount_amount`. Si el interruptor
   * `mf_line_discount_via_q_command` está en ON, `printInvoice` registra el
   * ítem con el BRUTO y emite `q-` con ese monto para que el descuento salga
   * impreso bajo cada producto. Con el interruptor en OFF (default) el driver
   * ignora ambos campos y el comportamiento es exactamente el de la
   * Estrategia A. `printCreditNote`/`printDebitNote` siempre usan `price_unit`
   * (neto), sin cambio alguno de comportamiento.
   *
   * Estrategia C corregida — SEPARACIÓN campaña / global:
   * Los dos descuentos son de naturaleza distinta y el ticket debe reflejarlo:
   *
   *  - El de CAMPAÑA se calcula sobre CADA producto (regla de lista de
   *    precios). Es el único que viaja en `discount_amount`, y por lo tanto el
   *    único que sale impreso como renglón "DESC" bajo su propio producto.
   *  - El GLOBAL (botón "Descuento Global") se calcula sobre el TOTAL del
   *    pedido. Viaja agregado en `global_only_discount_amount` y el driver lo
   *    imprime como UNA línea al pie ("DESC. GLOBAL = X"), igual que en la
   *    Estrategia A — pero ahora COEXISTIENDO con los `q-` por línea en vez de
   *    reemplazarlos.
   *
   * Antes de esta corrección los dos se fusionaban en un solo % por línea y el
   * `q-` salía con el monto ya combinado, mientras la línea agregada del pie
   * quedaba suprimida. Era incorrecto conceptualmente: mezclaba un descuento
   * por producto con uno sobre el total del pedido.
   *
   * `global_only_discount_amount` / `global_only_discount_rate` (C3, revisión
   * formal, ticket físico 2026-09-23): en el camino ON, `global_only_discount_amount`
   * es `globalDiscountAmount` DIRECTO (ya exacto, sin resta); en el camino OFF
   * es `globalDiscountAmount − Σ lineCampaignDiscountAmount` (SÍ hace falta la
   * resta ahí, porque en OFF ese monto es el descuento TOTAL combinado). El
   * bug original medía SIEMPRE por diferencia de dos sumas por línea ya
   * redondeadas (`Σ lineTotalDiscountAmount − Σ lineCampaignDiscountAmount`),
   * y el problema estaba en que, en el camino ON, `lineTotalDiscountAmount` se
   * recomputaba cascadeando una tasa (`globalRate`) YA redondeada por línea en
   * vez de usar el monto exacto `globalDiscountAmount` que ya estaba en scope
   * — eso fue lo que causó el desfase de 1 céntimo confirmado en hardware
   * real. `globalOnlyRate` es la MISMA `globalRate` en ambos caminos, sin
   * recalcular. Ver el comentario junto a `globalOnlyDiscountAmount` más abajo
   * para el detalle numérico completo, incluida una variante alternativa que
   * se descartó por no reproducir correctamente el camino OFF.
   *
   * Limitación conocida: un descuento MANUAL por línea (el cajero teclea un %
   * directamente) no tiene marca de campaña, así que llega con
   * `campaign_discount_percent = 0` y su descuento completo se contabiliza en
   * el agregado del pie en vez de en su propio `q-`.
   *
   * C1 (revisión formal): si la marca de campaña de una línea (ver
   * `binaural_pos_pricelist_line_discount/orderline_model.js`) quedó desfasada
   * por un descuento MANUAL posterior distinto sobre esa misma línea,
   * `campaign_discount_percent` podría venir mayor que el descuento real que
   * Odoo cobra en esa línea. `lineCampaignDiscountAmount` se acota con
   * `Math.min(..., lineTotalDiscountAmount)` para que el `q-` de campaña
   * nunca exceda el descuento total real de la línea, sin depender de
   * arreglar el desfase de la marca en origen.
   *
   * `global_discount_amount` / `global_discount_rate` / `global_clamped`
   * conservan su semántica histórica SIN CAMBIOS: los consumen el pop-up de
   * clamp, `printInvoice` con el interruptor en OFF y —de forma crítica— el
   * `q-` fiscal agregado de `printCreditNote`/`printDebitNote`. Por eso la
   * porción "solo global" viaja en campos NUEVOS y no pisando esos.
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

    const rounding = this.currency?.rounding || 0.01;
    // Σ del descuento de campaña (ya acotado por C1) de cada línea. Hace falta
    // a nivel de documento para aislar la porción "solo global" en el camino
    // OFF (ver comentario junto a `globalOnlyDiscountAmount` más abajo).
    let totalCampaignDiscountAmount = 0;

    const lines = POSITIVE_LINES.map((line) => {
      const priceUnit = Number(line.price_unit || 0);
      const quantity = Math.abs(Number(line.quantity || 1));
      const lineDiscount = Number(line.discount || 0);
      const netAfterLineDiscount = this._applyDiscount(priceUnit, lineDiscount);
      const finalUnitPrice = preAppliedMeta
        ? netAfterLineDiscount
        : this._applyDiscount(netAfterLineDiscount, globalRate);

      // --- Descuento TOTAL real de la línea (campaña + global) ----------
      // Es el que efectivamente cobra Odoo. NO se imprime por línea, pero
      // (C1, ver más abajo) sirve de tope para el `q-` de campaña.
      //
      // `finalUnitPrice` ya contempla los dos caminos del flag
      // `native_global_discount_line`:
      // - Con `preAppliedMeta` (flag en OFF):
      //   `_applyGlobalDiscountBeforeValidation` ya reescribió `line.discount`
      //   con el % FINAL (campaña compuesta con global).
      // - Sin `preAppliedMeta` (flag en ON): la línea de descuento nativa de
      //   Odoo sigue presente como producto aparte, así que `globalRate` se
      //   derivó aquí arriba y se aplica en cascada sobre el neto de campaña
      //   (dos `_applyDiscount` sucesivos, aritméticamente equivalentes a la
      //   composición multiplicativa de `composeDiscountPercent`).
      // Así el ticket impreso es idéntico con el checkbox en ON o en OFF.
      const lineTotalDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: priceUnit,
        netUnitPrice: finalUnitPrice,
        quantity,
        rounding,
      });

      // --- Descuento de CAMPAÑA, aislado del global ---------------------
      // Precio neto considerando ÚNICAMENTE la regla de campaña de esta línea.
      // No se puede partir de `line.discount`: con el flag
      // `native_global_discount_line` en OFF ese campo ya fue reescrito con el
      // % COMPUESTO por `_applyGlobalDiscountBeforeValidation`. El % puro sólo
      // sobrevive en `campaign_discount_percent`, que propaga
      // `get_data_invoice` desde `campaignDiscountPercent`.
      const campaignPct = Number(line.campaign_discount_percent || 0);
      const campaignOnlyNet = this._applyDiscount(priceUnit, campaignPct);

      // MONTO exacto en Bs del descuento PROPIO de esta línea: el argumento
      // del `q-` que sale impreso como renglón "DESC" bajo su producto. La
      // impresora no rehace ninguna aritmética: sólo resta este número del
      // total de la línea que acaba de registrar. Por eso no hay riesgo de que
      // su redondeo difiera del de Odoo, ni límite de 99,99% (que sí tenía el
      // porcentaje de `p-`).
      //
      // La fórmula vive en DiscountMath.computeLineDiscountAmount: redondea
      // CADA total por separado antes de restar, para que
      // `round(bruto × qty) − descuento === round(neto × qty)` se cumpla
      // exacto incluso con cantidad fraccionaria (ver su docblock).
      const lineCampaignDiscountAmountRaw = computeLineDiscountAmount({
        grossUnitPrice: priceUnit,
        netUnitPrice: campaignOnlyNet,
        quantity,
        rounding,
      });

      // C1 (revisión formal): `campaign_discount_percent` viene de la marca
      // `campaignDiscountPercent` que pone `binaural_pos_pricelist_line_discount`.
      // Esa marca sólo se limpia cuando el descuento vigente de la línea
      // coincide EXACTO con el último que ella misma escribió
      // (`campaignDiscountAppliedPercent`); si el cajero teclea a mano un %
      // distinto sobre una línea que ya traía campaña, la marca queda
      // desfasada — sigue apuntando al % de campaña original aunque
      // `line.discount` ya no lo refleje. Sin este tope, `lineCampaignDiscountAmountRaw`
      // podría superar `lineTotalDiscountAmount` (lo que la línea descuenta en
      // TOTAL) y el `q-` de campaña saldría más grande que el descuento real
      // que Odoo está cobrando en esa línea.
      //
      // El `Math.min` es defensivo y no depende de arreglar el desfase de la
      // marca en `orderline_model.js`: garantiza el invariante "nunca se
      // imprime por campaña más de lo que la línea descuenta en total" pase
      // lo que pase con esa marca.
      const lineCampaignDiscountAmount = Math.min(
        lineCampaignDiscountAmountRaw,
        lineTotalDiscountAmount
      );
      totalCampaignDiscountAmount += lineCampaignDiscountAmount;

      return {
        product_name: line.name,
        product_code: line.code || line.default_code,
        // Precio YA NETO. Sigue siendo el que consumen printCreditNote /
        // printDebitNote sin cambios; printInvoice usa `gross_price_unit`
        // sólo cuando el interruptor `mf_line_discount_via_q_command` está ON.
        price_unit: finalUnitPrice,
        // Precio BRUTO, antes de cualquier descuento. printInvoice registra el
        // ítem con este precio y emite `q-<monto>` justo después.
        gross_price_unit: priceUnit,
        // SÓLO el descuento de campaña de esta línea (acotado, ver C1 arriba).
        // El global agregado NO va aquí: viaja en `global_only_discount_amount`
        // a nivel de orden.
        discount_amount: lineCampaignDiscountAmount,
        quantity: line.quantity,
        fiscal_code: line.tax,  // 0=Exento, 1=General, 2=Reducido, 3=Adicional
        discount: 0,
      };
    });

    // Porción del descuento total que NO viene de ninguna regla de campaña.
    //
    // C3 (revisión formal, ticket físico 2026-09-23) — fórmula corregida y
    // VERIFICADA numéricamente (con las funciones reales de `DiscountMath` y
    // el caso de referencia de `DISCOUNT_STRATEGY.md`) contra los dos caminos
    // del flag `native_global_discount_line`:
    //
    // - Camino ON (`preAppliedMeta` es `null`): `globalDiscountAmount` (ya
    //   calculado arriba) es la suma directa de los montos de las líneas
    //   NEGATIVAS (la línea nativa "Descuento" de Odoo) — exacta y YA "sólo
    //   global": en este camino la campaña vive enteramente en el % propio de
    //   cada línea de producto, nunca mezclada en la línea negativa. No hace
    //   falta restarle nada.
    // - Camino OFF (`preAppliedMeta` presente): `preAppliedMeta.global_discount_amount`
    //   es el descuento TOTAL COMBINADO (campaña + global, porque
    //   `_applyGlobalDiscountBeforeValidation` compuso ambos en `line.discount`
    //   y luego sumó el descuento real ya con el % final). Aquí SÍ hay que
    //   restarle `totalCampaignDiscountAmount` para aislar la porción global.
    //
    // ⚠ Una versión anterior de este fix intentó usar, para el camino OFF, el
    // monto CRUDO de la línea de descuento nativa ANTES de componerse
    // (`inference.pendingDiscountAmount`, expuesto como
    // `global_only_discount_amount` en `_mf_global_discount_meta`). Parecía
    // "más exacto" porque no pasa por ninguna resta de sumas redondeadas, pero
    // se verificó numéricamente (con el caso de referencia de 3 líneas de
    // `DISCOUNT_STRATEGY.md`: 34.266,88 × 3, 90% campaña, global compuesto al
    // 91,5%) que NO reproduce lo que Odoo realmente cobra: da 1.542,01 cuando
    // el total real que resulta de aplicar el % COMPUESTO (91,5%, ya
    // redondeado por `composeDiscountPercent`) y sumar los subtotales reales
    // por línea es 1.542,03. La diferencia (2 céntimos en ese caso) es el
    // redondeo que introduce `composeDiscountPercent` al fusionar campaña y
    // global en un solo % antes de aplicarlo — un redondeo real que Odoo SÍ
    // aplica al cobrar, y que el monto crudo pre-composición no puede conocer.
    // Usar el monto crudo ahí habría hecho que el total registrado en la
    // impresora (bruto − campaña − globalOnly) NO coincidiera con lo que Odoo
    // realmente cobra, arriesgando un NAK en el cierre `199` — exactamente el
    // tipo de descuadre que este documento existe para evitar. Se descartó esa
    // variante; el campo `global_only_discount_amount` NO se agregó a
    // `_mf_global_discount_meta`.
    //
    // La resta SÍ es segura en el camino OFF (a diferencia del camino ON,
    // donde el bug original vivía) porque `totalCampaignDiscountAmount` y
    // `preAppliedMeta.global_discount_amount` provienen ambos, en última
    // instancia, del MISMO `line.discount` real que Odoo aplicó — no de una
    // tasa re-derivada y cascada por línea (que sí introducía el desfase en el
    // camino ON, ver `DISCOUNT_STRATEGY.md`).
    const globalOnlyDiscountAmount = preAppliedMeta
      ? Math.max(0, round_pr(globalDiscountAmount - totalCampaignDiscountAmount, rounding))
      : globalDiscountAmount;

    // La tasa "sólo global" es la MISMA `globalRate` de arriba en AMBOS
    // caminos: en OFF es `inference.inferredPercent` (calculado contra la base
    // YA neta de campaña, antes de componer); en ON se computa aquí mismo
    // contra `positiveBaseSum` (también neta de campaña). Las dos son exactas
    // y ya "sólo global" — no hace falta recalcular nada contra una base
    // aparte.
    const globalOnlyRate = globalRate;

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
      // Semántica HISTÓRICA intacta: el descuento global medido como siempre.
      // Lo consumen el pop-up de clamp del PosStore, `printInvoice` con el
      // interruptor en OFF y el `q-` FISCAL agregado de
      // `printCreditNote`/`printDebitNote`. Tocarlo cambiaría el total de las
      // NC/ND, por eso la porción "solo global" viaja aparte.
      global_discount_amount: globalDiscountAmount,
      global_discount_rate: globalRate,
      global_clamped: globalClamped,
      // Porción del descuento NO atribuible a ninguna regla de campaña. SÓLO
      // la consume `printInvoice` con el interruptor en ON: la aplica como
      // `q-` agregado tras el subtotal y la imprime como "DESC. GLOBAL = X" al
      // pie. Con el interruptor en OFF y en NC/ND se ignora por completo.
      global_only_discount_amount: globalOnlyDiscountAmount,
      global_only_discount_rate: globalOnlyRate,
      // Interruptor de activación gradual del descuento visible por línea
      // (comando `q-`). En OFF (default) el driver ignora `gross_price_unit` /
      // `discount_amount` y la factura se imprime exactamente como en la
      // Estrategia A: precio neto por ítem + línea agregada "DESC. GLOBAL".
      line_discount_via_q: Boolean(this.config?.mf_line_discount_via_q_command),
      header_lines: this._extractReceiptLines("receipt_header"),
      footer_lines: this._extractReceiptLines("receipt_footer"),
      // Decimales de la moneda de la orden. La consume
      // `TfhkaDriver._formatDisplayAmount` para formatear MONTOS en las líneas
      // informativas del pie (p. ej. "DESC. GLOBAL = X"), en vez de asumir
      // 2 decimales fijos. No confundir con `disc_int`/`disc_decimal` o
      // `max_amount_int`/`_decimal` (`FLAG21_CONFIGS`): esos son el ANCHO DE
      // CAMPO fijo del protocolo TFHKA, un requisito de hardware independiente
      // de la moneda.
      currency_decimal_places: this.currency?.decimal_places ?? 2,
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
    if (!this.config.native_global_discount_line) {
      this._applyGlobalDiscountBeforeValidation(order);
    }

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
