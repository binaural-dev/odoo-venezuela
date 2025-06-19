odoo.define('cadipa_gantt.GanttRenderer', function (require) {
    'use strict';

    const CadipaGanttRow = require('cadipa_gantt.GanttRow');
    const GanttRenderer = require('web_gantt.GanttRenderer');
    const session = require('web.session');
    const {device} = require('web.config');
    const core = require('web.core');

    const QWeb = core.qweb;

    const CadipaGanttRenderer = GanttRenderer.extend({
        config: Object.assign({}, GanttRenderer.prototype.config, {
            GanttRow: CadipaGanttRow
        }),
        init(parent, state, params) {
            this._super.apply(this, arguments);
            this.template_to_use = "CadipaGanttView";
            this.company_id = session.company_id
            this.config_company = {}
        },
        async __load_company_settings() {
            const domain = [
                [
                    'id', '=', this.company_id
                ]
            ]

            const data = await this._rpc({
                model: 'res.company',
                method: 'search_read',
                fields: [
                    "appointment_open_hour",
                    "appointment_close_hour"
                ],
                domain: domain,
            });

            if (data.length > 0) {
                this.config_company = data[0]
            };
        },
        _getSlotsDates() {
            const token = this.SCALES[this.state.scale].interval;
            const stopDate = this.state.stopDate;
            let day = this.state.startDate;
            const dates = [];

            const appointment_open_hour = Number(this.config_company.appointment_open_hour);
            const appointment_close_hour = Number(this.config_company.appointment_close_hour);

            if (this.state.scale == "day") {
                day.set({hour: appointment_open_hour})
                stopDate.set({hour: appointment_close_hour})
            };

            while (day <= stopDate) {
                dates.push(day);
                day = day.clone().add(1, token);
            }

            return dates;
        },
        async _renderView() {
            await this.__load_company_settings();

            const oldRowWidgets = Object.keys(this.rowWidgets).map((rowId) => {
                return this.rowWidgets[rowId];
            });
            this.rowWidgets = {};
            this.viewInfo = this._prepareViewInfo();
    
            this.proms = [];
            const rows = this._renderRows(this.state.rows, this.state.groupedBy);
            let totalRow;
            if (this.totalRow) {
                totalRow = this._renderTotalRow();
            }

            // this.proms.push(this._renderView.apply(this, arguments));
            const proms = this.proms;

            delete this.proms;
            return Promise.all(proms).then(() => {
                _.invoke(oldRowWidgets, 'destroy');
                if (this.firstRendering) {
                    this._replaceElement(QWeb.render(this.template_to_use, {widget: this, isMobile: device.isMobile}));
                    this.firstRendering = false;
                } else {
                    const newContent = $(QWeb.render(this.template_to_use, {widget: this, isMobile: device.isMobile}));
                    this.$el.html(newContent[0].innerHTML);
                }
                const $containment = $('<div id="o_gantt_containment"/>');
                const $rowContainer = this.$('.o_gantt_row_container');
                $rowContainer.append($containment);
                if (!this.state.groupedBy.length) {
                    $containment.css(this.isRTL ? {right: 0} : {left: 0});
                }

                rows.forEach((row) => {
                    row.$el.appendTo($rowContainer);
                });

                if (totalRow) {
                    totalRow.$el.appendTo(this.$('.o_gantt_total_row_container'));
                }

                if (this._isInDom && !this.disableDragdrop) {
                    this._setRowsDroppable();
                }
    
                if (this.state.isSample) {
                    this._renderNoContentHelper();
                }
            });
        },
    });

    return CadipaGanttRenderer;
});