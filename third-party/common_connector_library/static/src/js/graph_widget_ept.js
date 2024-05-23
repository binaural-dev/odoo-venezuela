odoo.define('graph_widget_ept.graph', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var core = require('web.core');
    var QWeb = core.qweb;

    var EmiproDashboardGraph = AbstractField.extend({
        className: "dashboard_graph_ept",
        events: {
            'click #perform_operation button':'_performOpration',
            'change #sort_order_data': '_sortOrders',
            'click #instance_product': '_getProducts',
            'click #instance_customer': '_getCustomers',
            'click #instance_order': '_getOrders',
            'click #instance_order_shipped': '_getShippedOrders',
            'click #instance_refund': '_getRefundOrders',
            'click #instance_report': '_getReport',
            'click #instance_log': '_getLog',
        },
        jsLibs: [
            '/web/static/lib/Chart/Chart.js',
        ],
        init: function () {
            this._super.apply(this, arguments);
            this.graph_type = this.attrs.graph_type;
            // this.data = JSON.parse(this.value);
            this.data = this.recordData
            this.match_key = _.find(_.keys(this.data), function(key){ return key.includes('_order_data') })
            this.graph_data = this.match_key.length ? JSON.parse(this.data[this.match_key]) : {}

            this.context = this.record.context
        },
        /**
         * The widget view uses the ChartJS lib to render the graph. This lib
         * requires that the rendering is done directly into the DOM (so that it can
         * correctly compute positions). However, the views are always rendered in
         * fragments, and appended to the DOM once ready (to prevent them from
         * flickering). We here use the on_attach_callback hook, called when the
         * widget is attached to the DOM, to perform the rendering. This ensures
         * that the rendering is always done in the DOM.
         */
        on_attach_callback: function () {
            this._isInDOM = true;
            this._renderInDOM();
        },
        /**
         * Called when the field is detached from the DOM.
         */
        on_detach_callback: function () {
            this._isInDOM = false;
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Render the widget only when it is in the DOM.
         *
         * @override
         * @private
         */
        _render: function () {
            if (this._isInDOM) {
                return this._renderInDOM();
            }
            return Promise.resolve();
        },
        /**
         * Render the widget. This function assumes that it is attached to the DOM.
         *
         * @private
         */
        _renderInDOM: function () {
            this.$el.empty();
            this.$canvas = $('<canvas/>');
            this.$el.addClass(cssClass);
            this.$el.empty();
            if(this.graph_data){
                var dashboard = $(QWeb.render('graph_dashboard_ept',{widget: this}))
                this.$el.append(dashboard);
                this.$el.find('.graph_ept').append(this.$canvas);
            } else {
                this.$el.append(this.$canvas);
            }
            var config, cssClass;
            var context = this.$canvas[0].getContext('2d');
            if (this.graph_type === 'line') {
                config = this._getLineChartConfig(context);
                cssClass = 'o_graph_linechart';
            }
            this.chart = new Chart(context, config);
        },

        _getLineChartConfig: function (context) {
            if(!_.isEmpty(this.graph_data) && this.graph_data.hasOwnProperty('values')){
                var labels = this.graph_data.values.map(function (pt) {
                    return pt.x;
                });
                var borderColor = '#0068ff';

                var gradientColor = context.createLinearGradient(0, 0, 0, 450);
                gradientColor.addColorStop(0.10, 'rgba(0, 155, 255, 0.25)');
                gradientColor.addColorStop(0.25, 'rgba(255, 255, 255, 0.25)');
                var backgroundColor;
                if(gradientColor){
                    backgroundColor = gradientColor
                }
                else{
                    backgroundColor = this.graph_data.is_sample_data ? '#ebebeb' : '#dcd0d9';
                }
                return {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: this.graph_data.values,
                            fill: 'start',
                            label: this.graph_data.key,
                            backgroundColor: backgroundColor,
                            borderColor: borderColor,
                            borderWidth: 2,
                            pointStyle: 'line',
                        }]
                    },
                    options: {
                        legend: {display: false},
                        scales: {
                            xAxes: [{
                                position: 'bottom'
                            }],
                            yAxes: [{
                                position: 'left',
                                ticks: {
                                    beginAtZero: true
                                },
                            }]
                        },
                        maintainAspectRatio: false,
                        elements: {
                            line: {
                                tension: 0.5,
                            }
                        },
                        tooltips: {
                            intersect: false,
                            position: 'nearest',
                            caretSize: 0,
                        },
                    },
                };
            }
        },

        /*Render action for  Sale Orders */
        _sortOrders: function (e) {
          var self = this;
          this.context.sort = e.currentTarget.value
            return this._rpc({model: self.model,method: 'read',args:[this.res_id],'context':this.context}).then(function (result) {
                if(result.length) {
                    self.graph_data = JSON.parse(result[0][self.match_key])
                    self.on_attach_callback()
                }
            })
        },

        /*Render action for  Products */
        _getProducts: function () {
            return this.do_action(this.graph_data.product_date.product_action)
        },

        /*Render action for  Customers */
        _getCustomers: function () {
            return this.do_action(this.graph_data.customer_data.customer_action)
        },

        /*Render action for  Sales Order */
        _getOrders: function () {
            return this.do_action(this.graph_data.order_data.order_action)
        },

        /*Render action for  shipped Order */
        _getShippedOrders: function () {
            return this.do_action(this.graph_data.order_shipped.order_action)
        },

        _getRefundOrders: function () {
            return this.do_action(this.graph_data.refund_data.refund_action)
        },

        /*Render(Open)  Operations wizard*/
        _performOpration: function () {
            return this._rpc({model: this.model,method: 'perform_operation',args: [this.res_id]}).then( (result) => {
                this.do_action(result)
            });
        },

        /*Render action for  Sales Analysis */
        _getReport: function () {
            return this._rpc({model: this.model,method: 'open_report',args: [this.res_id]}).then( (result) => {
                this.do_action(result)
            });
        },

        /*Render action for  Common Log Book */
        _getLog: function () {
         return this._rpc({model: this.model,method: 'open_logs',args: [this.res_id]}).then( (result) => {
                this.do_action(result)
            });
        },

    });

    fieldRegistry.add('dashboard_graph_ept', EmiproDashboardGraph);
    return {
        EmiproDashboardGraph: EmiproDashboardGraph
    };
});