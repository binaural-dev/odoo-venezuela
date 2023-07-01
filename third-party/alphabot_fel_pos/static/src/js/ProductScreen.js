odoo.define('point_of_sale.AlphabotProductScreen', function(require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');

    const AlphaProductScreen = ProductScreen => class extends ProductScreen {
        async _onClickPay() {
            let self = this;
            let order = this.env.pos.get_order();
            let lines = order.get_orderlines();
            let call_super = true;

            let has_zero_line = _.every(lines, function(line){
                return ((line.quantity !== 0.00)&&(line.price !== 0.00));
            });
            if(!has_zero_line){
                call_super = false;
                self.showPopup('ErrorPopup', {
                    title: self.env._t('Error: una línea en Cero'),
                    body: self.env._t('Verifique las líneas del pedido'),
                });
                return;
            }

            let all_positive = _.every(lines, function(line){
                let sub = line.quantity * line.price;
                return (sub > 0.00);
            });
            let all_negative = _.every(lines, function(line){
                let sub = line.quantity * line.price;
                return (sub < 0.00);
            });

            if((!all_positive)&&(!all_negative)){
                call_super = false;
                self.showPopup('ErrorPopup', {
                    title: self.env._t('Error en líneas de pedido'),
                    body: self.env._t('Todas las líneas de pedido deben ser del mismo signo'),
                });
                return;
            }

            if(call_super){
                super._onClickPay();
            }
        }
    };

    Registries.Component.extend(ProductScreen, AlphaProductScreen);

    return AlphaProductScreen;

});
