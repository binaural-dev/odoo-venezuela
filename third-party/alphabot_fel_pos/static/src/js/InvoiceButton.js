odoo.define('point_of_sale.AlphabotInvoiceButton', function (require) {
    'use strict';

    const InvoiceButton = require('point_of_sale.InvoiceButton');
    const Registries = require('point_of_sale.Registries');
    const session = require('web.session');

    const AlphabotInvoiceButton = InvoiceButton => class extends InvoiceButton {

        async _downloadInvoice(orderId) {
            try {
                const [orderWithInvoice] = await this.rpc({
                    method: 'read',
                    model: 'pos.order',
                    args: [orderId, ['account_move']],
                    kwargs: { load: false },
                });
                if (orderWithInvoice && orderWithInvoice.account_move) {
//                    console.log("done push_and_invoice_order");
//                    console.log(orderWithInvoice);
                    var active_ids =  [orderWithInvoice.account_move];
                    await this.rpc({
                        method: 'action_fel_move_from_pos',
                        model: 'account.move',
                        args: [[],active_ids],
                    });
//                    const order = this.props.order;
//                    console.log("xxxxxxxxxxxxxxxxx");
//                    console.log(order);
                    var _alphabot_FEL_Doc = false;
                    _alphabot_FEL_Doc = await this.env.pos.get_order_fel_invoice_and_wait(orderId);
                    this.props.order.set_alphabot_FEL_Doc(_alphabot_FEL_Doc);
                    this.showScreen('ReprintReceiptScreen', { order: this.props.order });
                }
            } catch (error) {
                if (error instanceof Error) {
                    throw error;
                } else {
                    // NOTE: error here is most probably undefined
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Network Error'),
                        body: this.env._t('Unable to download invoice.'),
                    });
                }
            }
        }


    };

    Registries.Component.extend(InvoiceButton, AlphabotInvoiceButton);

    return AlphabotInvoiceButton;
});

