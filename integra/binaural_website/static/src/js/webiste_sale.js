odoo.define('binaural_sitio_web.website_sale_bin', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const VariantMixin = require('sale.VariantMixin');
    require("web.zoomodoo");

    publicWidget.registry.WebsiteSaleBinauralSitioWeb = publicWidget.Widget.extend(VariantMixin, {
        selector: '.oe_website_sale',
        events: _.extend({}, VariantMixin.events || {}, {

            'change select[name="state_id"]': '_onChangeState',
            'change select[name="city_id"]': '_onChangeCity',
        }),
        /**
         * @constructor
         */
        init: function () {
            this._super.apply(this, arguments);
            this._changestate = _.debounce(this._changestate.bind(this), 500);
            this.isWebsite = true;
        },
        /**
         * @override
         */
        start() {
            const def = this._super(...arguments);
            this.$('select[name="state_id"]').change();
            return def;
        },

        /**
         * @private
         */
        _changestate: function () {
            
            if (!$("#state_id").val()) {
                return;
            }
            this._rpc({
                route: "/shop/city_infos/" + $("#state_id").val(),
                params: {
                    mode: $("#state_id").attr('mode'),
                },
            }).then(function (data) {
                const selectStates = $("select[name='city_id']");
                if (selectStates.data('init') === 0 || selectStates.find('option').length === 1) {
                    if (data.states.length) {
                        selectStates.html('');
                        _.each(data.states, function (x) {
                            var opt = $('<option>').text(x[1])
                                .attr('value', x[0]).attr('name-bin', x[1])
                                
                            selectStates.append(opt);
                        });
                        selectStates.parent('div').show();
                    } else {
                        selectStates.val('').parent('div').hide();
                    }
                    selectStates.data('init', 0);
                } else {
                    selectStates.data('init', 0);
                }
            });
        },
        
        /**
         * @private
         * @param {Event} ev
         */
        _onChangeState: function (ev) {
            this._changestate();
        },
        /**
         * @private
         * @param {Event} ev
         */
        _onChangeCity: function (ev) {
            $("#city_odoo").val($("#city_id_bin option:selected").attr("name-bin"))
        }, 
    });
});
