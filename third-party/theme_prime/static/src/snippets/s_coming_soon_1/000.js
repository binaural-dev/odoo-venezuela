/** @odoo-module **/

import "@theme_prime/snippets/s_tp_countdown/000";
import publicWidget from "web.public.widget";

publicWidget.registry.s_coming_soon = publicWidget.Widget.extend({
    selector: '.s_coming_soon',
    disabledInEditableMode: false,
    start: function () {
        if (!this.editableMode || !this.$('.s_coming_soon_countdown_over').length) {
            $('#wrapwrap').css('overflow', 'hidden');
        }
        if (this.editableMode) {
            this.$target.removeClass('d-none');
            $('#wrapwrap').css('overflow', 'auto');
        }
        return this._super.apply(this, arguments);
    },
    destroy: function () {
        $('#wrapwrap').css('overflow', 'auto');
        this._super.apply(this, arguments);
    },
});

publicWidget.registry.TpCountdown.include({
    _endCountdown: function () {
        if (this.$target.parents('.s_coming_soon').length) {
            if (!this.editableMode) {
                this.$target.parents('.s_coming_soon').addClass('d-none');
                this.$target.addClass('s_coming_soon_countdown_over');
            }
            $('#wrapwrap').css('overflow', 'auto');
        }
        this._super.apply(this, arguments);
    }
});
