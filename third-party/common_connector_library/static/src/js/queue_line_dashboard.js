odoo.define('queue_line_ept.dashboard', function (require) {
    "use strict";

var core = require('web.core');
var ListController = require('web.ListController');
var ListRenderer = require('web.ListRenderer');
var ListModel = require('web.ListModel');
var ListRenderer = require('web.ListRenderer');
var ListView = require('web.ListView');
var SampleServer = require('web.SampleServer');
var view_registry = require('web.view_registry');
const session = require('web.session');

var QWeb = core.qweb;
// Add mock of method 'retrieve_dashboard' in SampleServer, so that we can have
// the sample data in empty purchase kanban and list view
let dashboardValues;
SampleServer.mockRegistry.add('queue.line.dashboard/retrieve_dashboard', () => {
    return Object.assign({}, dashboardValues);
});


//--------------------------------------------------------------------------
// List View
//--------------------------------------------------------------------------


var QueueLineListDashboardRenderer = ListRenderer.extend({
    events:_.extend({}, ListRenderer.prototype.events, {
        'click .o_dashboard_action': '_onDashboardActionClicked',
    }),
    /**
     * @override
     * @private
     * @returns {Promise}
     */
    _renderView: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            var purchase_dashboard = QWeb.render('queue_line_ept.Dashboard', {
                values: dashboardValues
            });
            self.$el.prepend(purchase_dashboard);
        });
    },

    /**
     * @private
     * @param {MouseEvent}
     */
    _onDashboardActionClicked: function (e) {
        e.preventDefault();
        var $action = $(e.currentTarget);
        debugger;
        var context = JSON.parse($action.attr('context'));
        this.do_action({
            name: $action.attr('title'),
            res_model: dashboardValues['model'],
            domain: [['id', 'in', dashboardValues[context['action']][1]]],
            context: context,
            views: [[false, 'list'], [false, 'form']],
            type: 'ir.actions.act_window',
            view_mode: "list"
        });
    },
});

var QueueLineListDashboardModel = ListModel.extend({
    /**
     * @override
     */
    init: function () {
        this.dashboardValues = {};
        if (arguments) {
            this.model = arguments[1]['modelName'];
        }
        this._super.apply(this, arguments);
    },

    __get: function (localID) {
        var result = this._super.apply(this, arguments);
        if (_.isObject(result)) {
            result.dashboardValues = this.dashboardValues[localID];
        }
        return result;
    },

    /**
     * @œverride
     * @returns {Promise}
     */
    __load: function () {
        return this._loadDashboard(this._super.apply(this, arguments));
    },
    /**
     * @œverride
     * @returns {Promise}
     */
    __reload: function () {
        return this._loadDashboard(this._super.apply(this, arguments));
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Promise} super_def a promise that resolves with a dataPoint id
     * @returns {Promise -> string} resolves to the dataPoint id
     */
    _loadDashboard: function (super_def, e) {
        var self = this;
        var action_domain = {};
        if (this.loadParams && this.loadParams.domain) {
            action_domain = this.loadParams.domain;
        }
        var dashboard_def = this._rpc({
            model: this.model,
            method: 'retrieve_dashboard',
            context: {
                'action_domain': action_domain
            }
        });
        return Promise.all([super_def, dashboard_def]).then(function(results) {
            var id = results[0];
            dashboardValues = results[1];
            return id;
        });
    },
});

var QueueLineListDashboardController = ListController.extend({
    custom_events: _.extend({}, ListController.prototype.custom_events, {
        dashboard_open_action: '_onDashboardOpenAction',
    }),

    /**
     * @private
     * @param {OdooEvent} e
     */
    _onDashboardOpenAction: function (e) {
        return this.do_action(e.data.action_name,
            {additional_context: JSON.parse(e.data.action_context)});
    },
});

var QueueLineListDashboardView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Model: QueueLineListDashboardModel,
        Renderer: QueueLineListDashboardRenderer,
        Controller: QueueLineListDashboardController,
    }),
});

view_registry.add('queue_line_ept_dashboard', QueueLineListDashboardView);

return {
    Model: QueueLineListDashboardModel,
    Renderer: QueueLineListDashboardRenderer,
    Controller: QueueLineListDashboardController,
};

});