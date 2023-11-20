/** @odoo-module **/


import PosComponent from "point_of_sale.PosComponent";
import Registries from "point_of_sale.Registries";
import utils from "web.utils";

import { onWillUpdateProps } from "@odoo/owl";

const round_pr = utils.round_precision;

export class DeliveryCommand extends PosComponent {
  setup() {
    super.setup();
    this.round_pr = round_pr;
    this.currency = this.props.currency;
    this._receiptEnv = this.props.order.getOrderReceiptEnv();
    this.is_foreign_currency = this.env.pos.currency.name !== this.currency.name; 

    onWillUpdateProps((nextProps) => {
        this._receiptEnv = nextProps.order.getOrderReceiptEnv();
    });

  }
  get partner() {
    return this._receiptEnv.receipt.partner;
  }
  get order() {
    return this._receiptEnv.order;
  }
  get receipt() {
    return this._receiptEnv.receipt;
  }
  get isBodegon() {
    return this.env.pos.company.id == 1;
  }
  get foreign_tax_details(){
      var details = {};
      var fulldetails = [];

      this.order.orderlines.forEach(function(line){
          var ldetails = line.get_foreign_tax_details();
          for(var id in ldetails){
              if(ldetails.hasOwnProperty(id)){
                  details[id] = (details[id] || 0) + ldetails[id];
              }
          }
      });

      for(var id in details){
          if(details.hasOwnProperty(id)){
              fulldetails.push({amount: details[id], tax: this.env.pos.taxes_by_id[id], name: this.env.pos.taxes_by_id[id].name});
          }
      }
      return fulldetails;
  }
  isSimple(line) {
      return (
          line.discount === 0 &&
          line.is_in_unit &&
          line.quantity === 1 &&
          !(
              line.display_discount_policy == 'without_discount' &&
              line.price < line.price_lst
          )
      );
  }
  format_currency(amount){
    if (!amount) {
      amount = this.env.pos.format_currency_no_symbol(this.currency.rate, "Tasa", this.currency)
    } else {
      amount *= this.currency.rate
      amount = this.env.pos.format_currency_no_symbol(amount, "Tasa", this.currency)
    }

    if (this.currency.position === 'after') {
        return amount + ' ' + (this.currency.symbol || '');
    } 
    return (this.currency.symbol || '') + ' ' + amount;
  }
  convert_to_date(date_str) {
    return moment(date_str).format("D/MM/YYYY");
  }
  convert_to_time(date_str) {
    return moment(date_str).format("hh:mm A");
  }
  get_orderline(product_name) {
    const orderline = this.order.orderlines.filter((orderline) => orderline.product.display_name === product_name );
    return orderline[0];
  }
  get_taxed_products_total(tax) {
    let orderlines = this.order.orderlines.filter((orderline) => orderline.get_tax_details().hasOwnProperty(tax.id));
    if (this.is_foreign_currency) {
      return orderlines.reduce((accum, orderline) => (accum + orderline.get_foreign_price_without_tax()) , 0);
    }
    return orderlines.reduce((accum, orderline) => accum + orderline.get_price_without_tax(), 0);
  }
};
DeliveryCommand.template = "DeliveryCommand";

Registries.Component.add(DeliveryCommand);
