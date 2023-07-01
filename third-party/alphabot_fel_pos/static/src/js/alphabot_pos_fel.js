odoo.define('alphabot_fel_pos.pos', function (require) {
    "use strict";

const { Gui } = require('point_of_sale.Gui');
var { PosGlobalState, Order } = require('point_of_sale.models');
const Registries = require('point_of_sale.Registries');
var field_utils = require('web.field_utils');
var models = require('point_of_sale.models');

const alphabotFelPosGlobalState = (PosGlobalState) => class alphabotFelPosGlobalState extends PosGlobalState {

    is_panama_country() {
//      console.log("*** is_panama_country");
      if (!this.company.country) {
        Gui.showPopup("ErrorPopup", {
            'title': _t("Pais no definido"),
            'body':  _.str.sprintf(_t('La empresa %s no tiene un pais definido.'), this.company.name),
        });
        return false;
      }
        return this.company.country.code === 'PA';
    }

    async get_order_fel_invoice_and_wait(order_id) {
        Gui.setSyncStatus('connecting');
//        console.log("get_order_fel_invoice_and_wait");
        var _alphabot_FEL_Doc = false;
        try {
            if(this.is_panama_country()) {
                var ciclo = 20;
                if (!this.company.alphabot_fel_active){
                    ciclo = 1;
                }
                while (ciclo>0)
                {
                    console.log(ciclo);
                    _alphabot_FEL_Doc = false;
//                    console.log('wwwwwwwwwwww rpc');
                    const result = await this.env.services.rpc({
                        model: 'pos.order',
                        method: 'get_invoice',
                        args: [order_id],
                    });
//                    console.log('wwwwwwwwwwww result');
//                    console.log(result);
                    _alphabot_FEL_Doc = (result || false);

                    if((_alphabot_FEL_Doc != false) && (_alphabot_FEL_Doc.Tipo != false))
                    {
//                        console.log('wwwwwwwwwwww bien');
                        ciclo = 0;
                    }
                    else
                    {
                        ciclo = ciclo - 1;
                    }
                }
            }
         } catch (error) {
            if (error instanceof Error) {
                throw error;
            } else {
                // NOTE: error here is most probably undefined
                Gui.showPopup("ErrorPopup", {
                    title: this.env._t('Network Error'),
                    body: this.env._t('Unable to download invoice.'),
                });
            }
        }
        Gui.setSyncStatus('connected');
    return _alphabot_FEL_Doc;
    }
}
Registries.Model.extend(PosGlobalState, alphabotFelPosGlobalState);

const alphabotFelPosOrder = (Order) => class alphabotFelPosOrder extends Order {

    export_for_printing() {
        var result = super.export_for_printing(...arguments);
        result.alphabot_FEL_Doc = this.get_alphabot_FEL_Doc();

//            console.log(result.alphabot_FEL_Doc);
        if(typeof result.date.localestring == 'undefined')
        {
            var d  = new Date();
            result.date.localestring = field_utils.format.datetime(moment(d), {}, {timezone: false});
        }

       var company = this.pos.company;
        result.company.alphabot_fel_pac_msg = company.alphabot_fel_pac_msg;
        result.company.street = company.street;

        return result;
    }
    set_alphabot_FEL_Doc(alphabot_FEL_Doc){
      this.alphabot_FEL_Doc = alphabot_FEL_Doc;
    }
    get_alphabot_FEL_Doc() {
        return this.alphabot_FEL_Doc;
    }
    wait_for_push_order() {
        var result = super.wait_for_push_order(...arguments);
        result = Boolean(result || this.pos.is_panama_country());
        return result;
    }
    _isValidEmptyOrder() {
        if(this.finalized == true)
        {
              return false;
        }
        return super._isValidEmptyOrder();
    }

}
Registries.Model.extend(Order, alphabotFelPosOrder);

});
