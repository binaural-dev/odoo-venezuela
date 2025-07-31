/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GuestForm = publicWidget.Widget.extend({
    selector: 'div.modal[id^="addGuestModal"]',
    events: {
        'change .guest-type-select': '_onGuestTypeChange',
    },
    start: function () {
        this._super.apply(this, arguments);
        this._toggleRelationField(
            this.$('.guest-type-select').val() === 'family'
        );
        return this;
    },

    _onGuestTypeChange: function (ev) {
        this._toggleRelationField(
            $(ev.currentTarget).val() === 'family'
        );
    },
    _toggleRelationField: function (show) {
        const $relationField = this.$('.family-relation-field');
        $relationField.toggle(show);
        $relationField.find('select').prop('required', show);
    }
    
});