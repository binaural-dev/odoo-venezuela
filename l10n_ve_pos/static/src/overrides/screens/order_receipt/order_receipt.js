/** @odoo-module */

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt, {
  props: {
    ...OrderReceipt.props,
    conversion_rate: { optional: true },
    foreign_inverse_rate: { optional: true },
    foreign_total_with_taxes: { optional: true },
    foreign_total_tax: { optional: true },
    foreign_tax_total: { optional: true },
    quantity_products: { optional: true },
  },
});

patch(OrderReceipt.prototype, {
  get currentOrder() {
    return this.props?.order || null;
  },

  get orderPayments() {
    const order = this.props?.order;
    const paymentsFromOrder = order?.payment_ids || order?.paymentlines || [];
    if (!paymentsFromOrder.length) {
      return [];
    }

    return paymentsFromOrder.map((line) => {
      const rawMethod = line.payment_method_id;
      const methodName =
        rawMethod?.name ||
        (Array.isArray(rawMethod) ? rawMethod[1] : null) ||
        line.name ||
        "";

      const foreignFromLine =
        (typeof line.get_foreign_amount === "function" && line.get_foreign_amount()) ??
        line.foreign_amount;

      const fallbackByConfig =
        (line.amount ?? 0) * (this.posConfig.foreign_inverse_rate || 0);

      return {
        amount: line.amount ?? null,
        foreignAmount: Number.isFinite(foreignFromLine)
          ? foreignFromLine
          : fallbackByConfig,
        name: methodName,
      };
    });
  },

  get posConfig() {
    const order = this.props?.order;
    return (
      order?.config ||
      order?.pos?.config ||
      this.pos?.config ||
      this.env?.services?.pos?.config ||
      this.env?.pos?.config ||
      {}
    );
  },

  get orderDisplayData() {
    const data = this.props?.data || {};
    const order = this.currentOrder;
    const payments = this.orderPayments;
    const config = this.posConfig;
    const conversionRate = Number(config.foreign_rate) || 1;

    return {
      conversion_rate: config.foreign_rate ?? 0,
      amount_total: order?.amount_total ?? data.amount_total ?? 0,
      foreign_inverse_rate: config.foreign_inverse_rate ?? 0,
      paymentsLine: payments,
      foreign_total_with_taxes:
        this.props?.foreign_total_with_taxes ??
        ((order?.amount_total ?? data.amount_total ?? 0) / conversionRate),
    };
  },
});