/** @odoo-module **/

import publicWidget from "web.public.widget";
import time from "web.time";
import { qweb } from "web.core";

publicWidget.registry.TpCountdown = publicWidget.Widget.extend({
    selector: ".tp-countdown",
    start: function () {
        const dueDate = this.el.dataset.dueDate;
        const eventTime = dueDate.includes("-") ? moment(time.str_to_datetime(dueDate)) : moment.unix(this.el.dataset.dueDate);
        const currentTime = moment();
        const diffTime = eventTime - currentTime;
        const interval = 1000;
        let duration = moment.duration(diffTime);
        if (this.el.dataset.countdownStyle) {
            this.$(".tp-countdown-container").remove();
            this.$target.prepend($(qweb.render(this.el.dataset.countdownStyle)));
        }
        this.$(".tp-end-msg-container").addClass("css_non_editable_mode_hidden");
        if (diffTime > 0) {
            this.countDownTimer = setInterval(() => {
                duration = moment.duration(duration.asMilliseconds() - interval, "milliseconds");
                if (duration.asMilliseconds() < 0) {
                    this._endCountdown();
                }
                let d = parseInt(moment.duration(duration).asDays());
                let h = moment.duration(duration).hours();
                let m = moment.duration(duration).minutes();
                let s = moment.duration(duration).seconds();

                d = $.trim(d).length === 1 ? "0" + d : d;
                h = $.trim(h).length === 1 ? "0" + h : h;
                m = $.trim(m).length === 1 ? "0" + m : m;
                s = $.trim(s).length === 1 ? "0" + s : s;

                this.$(".countdown_days").text(d);
                this.$(".countdown_hours").text(h);
                this.$(".countdown_minutes").text(m);
                this.$(".countdown_seconds").text(s);
            }, interval);
        } else {
            this._endCountdown();
        }
        return this._super.apply(this, arguments);
    },
    _endCountdown: function () {
        this.$(".countdown_days").text("00");
        this.$(".countdown_hours").text("00");
        this.$(".countdown_minutes").text("00");
        this.$(".countdown_seconds").text("00");
        this.$(".tp-end-msg-container").removeClass("css_non_editable_mode_hidden");
        if (this.countDownTimer) {
            clearInterval(this.countDownTimer);
        }
    },
    destroy: function () {
        if (this.countDownTimer) {
            clearInterval(this.countDownTimer);
        }
        this._super.apply(this, arguments);
    },
});
