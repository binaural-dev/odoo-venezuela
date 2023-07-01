odoo.define('point_of_sale.AlphabotPaymentScreen', function (require) {
    'use strict';

    const { Gui } = require('point_of_sale.Gui');
    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const session = require('web.session');
    const { isConnectionError } = require('point_of_sale.utils');

    const AlphabotPaymentScreen = PaymentScreen => class extends PaymentScreen {

            async _postPushOrderResolve(order, order_server_ids) {
//                console.log("*** _postPushOrderResolve");
//                console.log("order_server_ids");
//                console.log(order_server_ids);
//                console.log("order");
//                console.log(order);
                try {
                       var _alphabot_FEL_Doc = false;
                       if(order.to_invoice==true)
                        {
                            Gui.setSyncStatus('connecting');
                            _alphabot_FEL_Doc = await this.env.pos.get_order_fel_invoice_and_wait(order_server_ids);
                             Gui.setSyncStatus('connected');
                        }
    //                    console.log(_alphabot_FEL_Doc);
                        order.set_alphabot_FEL_Doc(_alphabot_FEL_Doc);
                } finally {
                    return super._postPushOrderResolve(...arguments);
                }
            }


         async _finalizeValidation() {
//            console.log("*** _finalizeValidation");

            if (!this.env.pos.company.alphabot_fel_active){
                return  super._finalizeValidation(...arguments);
            }

            Gui.setSyncStatus('connecting');

            if ((this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) && this.env.pos.config.iface_cashdrawer) {
                this.env.proxy.printer.open_cashbox();
            }

            if(this.currentOrder.finalized === true) return;

            this.currentOrder.initialize_validation_date();
            this.currentOrder.finalized = true;

            let syncOrderResult, hasError;

            try {
                // 1. Save order to server.
                syncOrderResult = await this.env.pos.push_single_order(this.currentOrder);

                // 2. Invoice.
                if (this.currentOrder.is_to_invoice()) {
                    if (syncOrderResult.length) {
                        try {
                            if (this.env.pos.is_panama_country()) {

                                var active_ids = syncOrderResult.map((res) => res.account_move)
//                                console.log("*** active_ids");
//                                console.log(active_ids);
                                await this.rpc({
                                    method: 'action_fel_move_from_pos',
                                    model: 'account.move',
                                    args: [[],active_ids],
                                });
                            }
                      } catch (error) {
                            console.warn(error);
                            throw error;
                        }
                    } else {
                        throw { code: 401, message: 'Backend Invoice', data: { order: this.currentOrder } };
                    }
                }

                // 3. Post process.
                if (syncOrderResult.length && this.currentOrder.wait_for_push_order()) {
                    const postPushResult = await this._postPushOrderResolve(
                        this.currentOrder,
                        syncOrderResult.map((res) => res.id)
                    );
//                    console.log("*** cccccccc");
//                    console.log(postPushResult);
                    if (!postPushResult) {
                        this.showPopup('ErrorPopup', {
                            title: this.env._t('Error: no internet connection.'),
                            body: this.env._t('Some, if not all, post-processing after syncing order failed.'),
                        });
                    }
                }
            } catch (error) {
                if (error.code == 700 || error.code == 701)
                    this.error = true;

                if ('code' in error) {
                    // We started putting `code` in the rejected object for invoicing error.
                    // We can continue with that convention such that when the error has `code`,
                    // then it is an error when invoicing. Besides, _handlePushOrderError was
                    // introduce to handle invoicing error logic.
                    await this._handlePushOrderError(error);
                } else {
                    // We don't block for connection error. But we rethrow for any other errors.
                    if (isConnectionError(error)) {
                        this.showPopup('OfflineErrorPopup', {
                            title: this.env._t('Connection Error'),
                            body: this.env._t('Order is not synced. Check your internet connection'),
                        });
                    } else {
                        throw error;
                    }
                }
            } finally {
                // Always show the next screen regardless of error since pos has to
                // continue working even offline.
                this.showScreen(this.nextScreen);
                // Remove the order from the local storage so that when we refresh the page, the order
                // won't be there
                this.env.pos.db.remove_unpaid_order(this.currentOrder);

                // Ask the user to sync the remaining unsynced orders.
                if (!hasError && syncOrderResult && this.env.pos.db.get_orders().length) {
                    const { confirmed } = await this.showPopup('ConfirmPopup', {
                        title: this.env._t('Remaining unsynced orders'),
                        body: this.env._t(
                            'There are unsynced orders. Do you want to sync these orders?'
                        ),
                    });
                    if (confirmed) {
                        // NOTE: Not yet sure if this should be awaited or not.
                        // If awaited, some operations like changing screen
                        // might not work.
                        this.env.pos.push_orders();
                    }
                }
            }

            Gui.setSyncStatus('connected');
         };

    };

    Registries.Component.extend(PaymentScreen, AlphabotPaymentScreen);

    return PaymentScreen;
});
