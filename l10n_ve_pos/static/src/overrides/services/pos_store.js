/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

const { DateTime } = luxon;

patch(PosStore.prototype, {
  /**
   * The VAT PartnerList leaves for the customer it creates (newPartnerVat) is
   * the default of that form and is consumed here, so it never reaches a
   * later one.
   */
  editPartnerContext(partner) {
    const context = { ...super.editPartnerContext(...arguments) };
    if (this.newPartnerVat) {
      context.default_vat = this.newPartnerVat;
      this.newPartnerVat = false;
    }
    return context;
  },

  /**
   * "Permitir crear productos" (allow_product_creation_in_pos), apagado por
   * defecto. Solo un true explícito la enciende: con la sesión abierta antes
   * de actualizar el módulo, la caja sale de la caché del PdV sin el campo
   * (undefined) hasta "Volver a cargar datos", y en la base ya vale false.
   */
  get isProductCreationAllowed() {
    return this.config.allow_product_creation_in_pos === true;
  },

  // El core muestra "Crear producto" del menú según este getter.
  get hasProductCreationAccess() {
    return this.isProductCreationAllowed && super.hasProductCreationAccess;
  },

  /**
   * editProduct() sin producto abre el formulario de producto nuevo: lo usan
   * "Crear producto" del menú y "Crear manualmente" de la pantalla de
   * productos vacía. Con la creación apagada no se abre; editar un producto
   * existente no cambia.
   */
  async editProduct(product) {
    if (!product && !this.isProductCreationAllowed) {
      return;
    }
    return await super.editProduct(...arguments);
  },

  async pay() {
    if (!(await this._checkOrderBeforePayment(this.getOrder()))) {
      return;
    }
    this._notifySessionRateFromPreviousDay();
    return await super.pay(...arguments);
  },

  // El pago rápido (use_fast_payment) valida la orden sin pasar por pay():
  // las mismas verificaciones, antes de imprimir en la MF.
  async validateOrderFast() {
    if (!(await this._checkOrderBeforePayment(this.getOrder()))) {
      return;
    }
    this._notifySessionRateFromPreviousDay();
    return await super.validateOrderFast(...arguments);
  },

  async afterProcessServerData() {
    const res = await super.afterProcessServerData(...arguments);
    if (this.isSessionRateFromPreviousDay) {
      this.dialog.add(AlertDialog, {
        title: _t("Session from a previous day"),
        body: this._sessionRateFromPreviousDayMessage(),
      });
    }
    return res;
  },

  /**
   * Tasas que tiene este navegador: la de la caja (pos.config), las de las
   * monedas de cobro (tender_currency_rates) y el `rate` de cada moneda, con el
   * que el core pasa la lista de precios en divisa a la moneda de la caja.
   */
  _getLoadedRates() {
    const currencies = {};
    for (const currency of this.models["res.currency"].getAll()) {
      currencies[currency.id] = currency.rate;
    }
    return {
      foreign_inverse_rate: this.config.foreign_inverse_rate,
      currencies,
      tender_currency_rates: this.config.tender_currency_rates || {},
    };
  },

  /**
   * Antes de abrir la sesión: la tasa cargada en el navegador debe ser la de
   * la sesión (la del día). Devuelve:
   * - "ok": abrir como siempre.
   * - "blocked": no abrir (sin tasa del día, o se recargan los datos).
   * - "reload": la tasa es vieja pero hay órdenes pagadas sin sincronizar, que
   *   solo se envían con la sesión abierta y que una recarga perdería: abrir,
   *   y recargar los datos enseguida (reloadData sincroniza antes).
   */
  async checkOpeningRate() {
    let result;
    try {
      result = await this.data.call("pos.session", "check_opening_rate", [
        this.session.id,
        this._getLoadedRates(),
      ]);
    } catch (error) {
      // Sin conexión el core ya avisa que la caja no se puede abrir.
      if (error instanceof ConnectionLostError) {
        return "ok";
      }
      // Sesión borrada: el core recarga el PdV; cualquier otro error sube.
      await this.reloadIfSessionDeleted(error);
      return "blocked";
    }
    if (result?.status === "missing") {
      this.dialog.add(AlertDialog, {
        title: _t("No rate of the day"),
        body: _t(
          "There is no %(currency)s rate for %(date)s. Load the rate of the day before opening the register.",
          { currency: result.currency, date: result.date }
        ),
      });
      return "blocked";
    }
    if (result?.status === "outdated") {
      const values = { rate: result.rate, currency: result.currency, date: result.date };
      if (this.models["pos.order"].some((o) => o.isUnsyncedPaid && o.state !== "cancel")) {
        await makeAwaitable(this.dialog, AlertDialog, {
          title: _t("Outdated rate"),
          body: _t(
            "This register has an old rate loaded and paid orders that were not sent yet. The register will open to send them and then reload its data with the rate of the day, %(rate)s (%(currency)s, %(date)s). Do not sell before the reload.",
            values
          ),
        });
        return "reload";
      }
      await makeAwaitable(this.dialog, AlertDialog, {
        title: _t("Outdated rate"),
        body: _t(
          "This register has an old rate loaded. The rate of the day is %(rate)s (%(currency)s, %(date)s). The data will be reloaded before opening the register.",
          values
        ),
      });
      await this.reloadData(true);
      return "blocked";
    }
    return "ok";
  },

  /**
   * El popup de apertura solo marca la sesión como abierta: el navegador no
   * recibe el día de su tasa hasta la próxima carga. Sin él, el aviso de
   * sesión de un día anterior no saldría en el equipo que la abrió.
   */
  async loadSessionRateDate() {
    try {
      const [session] = await this.data.call("pos.session", "read", [
        [this.session.id],
        ["foreign_rate_date"],
      ]);
      if (session?.foreign_rate_date) {
        this.session.foreign_rate_date = deserializeDate(session.foreign_rate_date);
      }
    } catch (error) {
      // Sin conexión llega en la próxima carga; no impide vender.
      if (!(error instanceof ConnectionLostError)) {
        throw error;
      }
    }
  },

  /**
   * La sesión sigue abierta después de medianoche: cobra con la tasa del día
   * en que se abrió (no se mezclan tasas en una sesión).
   */
  get isSessionRateFromPreviousDay() {
    const rateDate = this.session?.foreign_rate_date;
    if (!rateDate || this.session.state !== "opened") {
      return false;
    }
    const rateDay = typeof rateDate === "string" ? rateDate : rateDate.toISODate();
    return rateDay < DateTime.now().toISODate();
  },

  _sessionRateFromPreviousDayMessage() {
    const rateDate = this.session.foreign_rate_date;
    const day = typeof rateDate === "string" ? rateDate : formatDate(rateDate);
    return _t(
      "This session was opened on %(date)s and every sale uses the rate of that day. Close it and open a new one to sell with today's rate.",
      { date: day }
    );
  },

  _notifySessionRateFromPreviousDay() {
    if (this.isSessionRateFromPreviousDay) {
      this.notification.add(this._sessionRateFromPreviousDayMessage(), {
        type: "warning",
      });
    }
  },

  /**
   * Verificaciones antes de cobrar. Muestra el aviso y devuelve false si la
   * orden no se puede cobrar.
   */
  async _checkOrderBeforePayment(order) {
    if (!order) {
      return true;
    }
    // Bloquea el paso a la pantalla de pago si hay líneas con cantidad en 0:
    // no se puede cobrar/facturar un producto sin cantidad. Se listan los
    // nombres para que el cajero los elimine o corrija antes de continuar.
    const zeroQtyLines = order.lines.filter((line) => line.getQuantity() === 0);
    if (zeroQtyLines.length) {
      const productNames = zeroQtyLines
        .map((line) => `• ${line.getFullProductName()}`)
        .join("\n");
      this.dialog.add(AlertDialog, {
        title: _t("Productos con cantidad en 0"),
        body: _t(
          "Los siguientes productos tienen cantidad en 0:\n\n%s\n\nElimínalos o colócales la cantidad correcta para continuar con el pago.",
          productNames
        ),
      });
      return false;
    }
    if (this.config.amount_to_zero) {
      const shortages = await this._getStockShortages(order);
      if (shortages.length) {
        const formatQty = (qty) => this.env.utils.formatProductQty(qty, false);
        const productLines = shortages
          .map(
            (shortage) =>
              `• ${shortage.name}: ${_t("ordered %(requested)s, on hand %(available)s", {
                requested: formatQty(shortage.requested),
                available: formatQty(shortage.available),
              })}`
          )
          .join("\n");
        this.dialog.add(AlertDialog, {
          title: _t("Insufficient stock"),
          body: _t(
            "There is not enough stock in the warehouse for:\n\n%s\n\nAdjust the quantities to continue with the payment.",
            productLines
          ),
        });
        return false;
      }
    }
    return true;
  },

  /**
   * "Cantidad en 0" (amount_to_zero): productos almacenables cuya cantidad en
   * la orden supera el stock a mano de la ubicación origen de la caja. Las
   * líneas negativas (devoluciones) no cuentan: devuelven stock.
   */
  async _getStockShortages(order) {
    const qtyByProduct = {};
    for (const line of order.lines) {
      const qty = line.getQuantity();
      if (qty <= 0) {
        continue;
      }
      const productId = line.getProduct().id;
      qtyByProduct[productId] = (qtyByProduct[productId] || 0) + qty;
    }
    if (!Object.keys(qtyByProduct).length) {
      return [];
    }
    try {
      return await this.data.call("pos.config", "check_stock_availability", [
        [this.config.id],
        qtyByProduct,
      ]);
    } catch (error) {
      if (!(error instanceof ConnectionLostError)) {
        throw error;
      }
      // Sin conexión: aproximación con el stock cargado al abrir la caja
      // (de la misma ubicación origen, pero puede estar desactualizado).
      return Object.entries(qtyByProduct)
        .map(([productId, requested]) => ({
          product: this.models["product.product"].get(parseInt(productId)),
          requested,
        }))
        .filter(({ product, requested }) => {
          if (!product?.is_storable) {
            return false;
          }
          const rounding = product.uom_id?.rounding || 0.01;
          return requested - product.qty_available > rounding / 2;
        })
        .map(({ product, requested }) => ({
          name: product.display_name,
          requested,
          available: product.qty_available,
        }));
    }
  },
});
