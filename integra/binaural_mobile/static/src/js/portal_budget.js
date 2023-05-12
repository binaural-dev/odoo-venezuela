odoo.define('binaural_mobile.portal_budget_form', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    
    publicWidget.registry.portalBudgetForm = publicWidget.Widget.extend({
        selector: '.o_portal_budget_form',
        events: {
            // "keyup #client": "_onKeyupClient",
            // "click #client": "_onClickClient"
            "change #client": "_onChangeClient",
        },
        start: function() {

            $('#client').select2({
                maximumInputLength: 35,
                minimumInputLength: 0,
                maximumSelectionSize: 1,
                ajax: {
                    url: '/budget/client',
                    dataType: 'json',
                    data:  term => ({query: term}),
                    results: data => {
                        const ret = [];
                        _.each(data, function (client) {
                            const { id: clientId } = client
                            const isExistclient = ret.find(client => client.id === clientId);

                            if (isExistclient) return;

                            ret.push({
                                id: client.id,
                                text: client.name,
                                isNew: false,
                            });
                        });
                        return {results: ret};
                    }
                },
            });
            
        },
        
        _onChangeClient: async function(ev) {
            const idClient = ev.target.value;
            const directionClient = await ajax.jsonRpc('/budget/direction_client', 'call', {
                "client": idClient
            });
            const { delivery } =  JSON.parse(directionClient);
            const { invoice } =  JSON.parse(directionClient);
            const { contact } =  JSON.parse(directionClient);
            const streetinvoice = invoice[0]
            const streetdelivery = delivery[0]
            const streetcontact = contact[0]
            $("#deliverys_address").empty();
            $("#billing_address").empty();
            if (streetinvoice && streetdelivery) {
                $("#billing_address").append(`<option value="${streetinvoice.id}">${streetinvoice.street}</option>`);
                $("#deliverys_address").append(`<option value="${streetdelivery.id}">${streetdelivery.street}</option>`);
            }else{
                $("#billing_address").append(`<option value="${streetcontact.id}">${streetcontact.street}</option>`);
                $("#delivery_address").append(`<option value="${streetcontact.id}">${streetcontact.street}</option>`);
                console.log("entro2")
            }
        },
    });
});