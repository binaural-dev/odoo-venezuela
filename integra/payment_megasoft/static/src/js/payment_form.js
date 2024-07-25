/** @odoo-module */
/* global Stripe */

import checkoutForm from 'payment.checkout_form';
import manageForm from 'payment.manage_form';
// import { useService } from "@web/core/utils/hooks";



const ajax = require('web.ajax');


const MegasoftMixin = {

    /**
     * Redirect the customer to Stripe hosted payment page.
     *
     * @override method from payment.payment_form_mixin
     * @private
     * @param {string} code - The code of the payment option
     * @param {number} paymentOptionId - The id of the payment option handling the transaction
     * @param {object} processingValues - The processing values of the transaction
     * @return {undefined}
     */

    _processRedirectPayment: async function (code, paymentOptionId, processingValues) {
        // const legacyActionManager = useService("legacy_action_manager");
        if (code !== 'megasoft') {
            return this._super(...arguments);
        }
        const payment = await ajax.jsonRpc('/get_config_payment', 'call', {values: processingValues}        
        ).then(function (data) {
            console.log(data)
            if (data[0] == "Error: 404"){
                console.log(data)
                const modalHtml = `
                    <div class="modal fade" id="exampleModal" tabindex="-1" aria-labelledby="exampleModalLabel" aria-hidden="true">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title" id="exampleModalLabel">Modal title</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                </div>
                                <div class="modal-body">
                                    <p>No se encuentra la URL de Megasoft</p>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                // Insertar el HTML del modal en el cuerpo del documento
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                $("#exampleModal").modal("show")
            }
            else {
                window.open(data[0],'') 
            }
        });

    },
    _insertBootstrapModal: function () {
        const modalHtml = `
            <div class="modal fade" id="exampleModal" tabindex="-1" aria-labelledby="exampleModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="exampleModalLabel">Modal title</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>aaaaaaa</p>>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary">Save changes</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Insertar el HTML del modal en el cuerpo del documento
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    },


    
};

checkoutForm.include(MegasoftMixin);
manageForm.include(MegasoftMixin);
