/** @odoo-module **/
import publicWidget from 'web.public.widget';

publicWidget.registry.profile = publicWidget.Widget.extend({

    selector: '.o_portal_details',

    events: {
        'change #city_id': '_onCityChange',
    },

    _onCityChange(e) {
        const city_id = $(e.currentTarget).val();
        const city_odoo = $('#city');
        city_odoo.val(city_id);
    }
});