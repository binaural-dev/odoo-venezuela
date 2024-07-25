odoo.define('tu_modulo.payment_post_processing_custom', function (require) {
    'use strict';

    var PaymentPostProcessing = require('payment.post_processing');

    PaymentPostProcessing.include({
        
        // Aquí puedes sobrescribir métodos existentes o agregar nuevos métodos según tus necesidades
        processPolledData: function (display_values_list) {
            console.log("THIS", this)
            console.log(arguments)
            this._super.apply(this, arguments);

        },
        

    });

    return PaymentPostProcessing;
});
