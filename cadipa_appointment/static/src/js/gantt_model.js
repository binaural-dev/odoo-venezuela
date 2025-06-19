odoo.define('cadipa_gantt.GanttModel', function (require) {
    'use strict';

    const core = require('web.core');
    const GanttModel = require('web_gantt.GanttModel');
    const session = require('web.session');

    const _t = core._t;

    const CadipaGanttModel = GanttModel.extend({
        init(parent, params = {}) {
            this._super.apply(this, arguments);
        },
    });

    return CadipaGanttModel;
});
