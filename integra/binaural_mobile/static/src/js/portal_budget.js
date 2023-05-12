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
            const { status } = JSON.parse(directionClient);
            const is404 = status === 404;
            if (is404) return 
            const { data } = JSON.parse(directionClient);
            const streetinvoice = data[1]
            const streetdelivery = data[0]
            if (streetinvoice && streetdelivery) {
                $("#deliverys_address").empty();
                $("#billing_address").empty();
                $("#billing_address").append(`<option value="${streetinvoice.id}">${streetinvoice.street}</option>`);
                $("#deliverys_address").append(`<option value="${streetdelivery.id}">${streetdelivery.street}</option>`);
            }
        },
    })
});