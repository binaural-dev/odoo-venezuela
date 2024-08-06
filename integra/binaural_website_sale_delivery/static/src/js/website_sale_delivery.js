odoo.define('binaural_website_sale_delivery.checkout', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

const BinauralWebsiteDelivery = publicWidget.registry.websiteSaleDelivery.extend({
    selector: '.oe_website_sale',

    _handleCarrierUpdateResult: function (result) {
        this._super.apply(this, arguments);
        var $amountForeignTotal = $('#foreign_order_total .monetary_field, #amount_total_summary.monetary_field');
        if (result.status === true) {
            $amountForeignTotal.html(result.new_foreign_total_billed);
        } else {
            $amountForeignTotal.html(result.new_foreign_total_billed);
        }
    },

    });
    publicWidget.registry.BinauralWebsiteDelivery = BinauralWebsiteDelivery

    return BinauralWebsiteDelivery;
});
