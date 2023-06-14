/** @odoo-module **/

import { WebsiteSale } from "website_sale.website_sale";

WebsiteSale.include({
    events: Object.assign({}, WebsiteSale.prototype.events, {
        'change select[name="state_id"]': '_onChangeState',
        'change select[name="city_id"]': '_onChangeCity',
    }),
    /**
     * @override
     */
    start() {
        this._super(...arguments);
        this.$('select[name="state_id"]').change();
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onChangeState: function (ev) {
        const stateSelect = $(ev.currentTarget);
        const url = `/shop/city_infos/${stateSelect.val()}`
        const queryOptions = {
            url: url,
            type: "GET",
            timeout: 1000
        }

        if (!stateSelect.val()) {
            return;
        }
        $.ajax(queryOptions).then((cities) => {
            console.log(cities);
            const citySelect = $("select[name='city_id']");

            if (citySelect.data("init") === 2 || citySelect.find("option").length == 1){
                if (cities.length) {
                    citySelect.html("");

                    cities.map((city) => {
                        citySelect.append(`<option value="${city.id}" name-bin="${city.name}"> ${city.name} </option>`)
                    })
                    citySelect.parent("div").show();
                    citySelect.change();
                } else {
                    citySelect.val('').parent("div").hide();
                }
            }
            citySelect.data("init", 0);
        });
    },
    /**
     * @private
     * @param {Event} ev
     */
    _onChangeCity: function (ev) {
        // const city = $(ev.currentTarget).text().trim();
        const idx = ev.currentTarget.selectedIndex;
        const city = ev.currentTarget.options[idx].text;
        $('input[name="city"]').val(city);
    },
});

export default WebsiteSale;