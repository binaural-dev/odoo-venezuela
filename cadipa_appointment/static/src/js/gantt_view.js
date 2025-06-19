odoo.define('cadipa_gantt.GanttView', function (require) {
    'use strict';

    const viewRegistry = require('web.view_registry');
    const CadipaGanttRenderer = require('cadipa_gantt.GanttRenderer');
    const CadipaGanttModel = require('cadipa_gantt.GanttModel');
    const GanttView = require('web_gantt.GanttView');

    const CadipaGanttView = GanttView.extend({
        config: Object.assign({}, GanttView.prototype.config, {
            Model: CadipaGanttModel,
            Renderer: CadipaGanttRenderer,
        }),
        init(viewInfo, params) {
            this._super(...arguments);
        },
    });

    viewRegistry.add('cadipa_gantt', CadipaGanttView);
    return CadipaGanttView;
});
