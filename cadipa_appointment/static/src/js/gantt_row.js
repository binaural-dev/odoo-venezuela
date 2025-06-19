odoo.define('cadipa_gantt.GanttRow', function (require) {
    'use strict';

    const GanttRow = require('web_gantt.GanttRow');

    const CadipaGanttRow = GanttRow.extend({
        template: 'CadipaGanttView.Row',

        init(parent, pillsInfo, viewInfo, options) {
            this._super(...arguments);
        },

    });

    return CadipaGanttRow;
});
