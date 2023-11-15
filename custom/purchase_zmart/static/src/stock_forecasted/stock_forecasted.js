/** @odoo-module **/

// import { useService } from "@web/core/utils/hooks";
// import { patch } from '@web/core/utils/patch';
// import { registry } from "@web/core/registry";
// import { View } from "@web/views/view";
// import { useSetupAction } from "@web/webclient/actions/action_hook";
// import { ControlPanel } from "@web/search/control_panel/control_panel";

// import { ForecastedButtons } from "./forecasted_buttons";
// import { ForecastedDetails } from "./forecasted_details";
// import { ForecastedHeader } from "./forecasted_header";
// import { ForecastedWarehouseFilter } from "./forecasted_warehouse_filter";

// import { ForecastedDetails } from "@stock/stock_forecasted/forecasted_details";

// patch(ForecastedDetails.prototype, 'purchase_zmart.ForecastedDetails', {
//     // _formatMonetary(num, currencyId){
//     //     return formatMonetary(num,{ currencyId: currencyId});
//     // },
//     _getReportValues(){
//         // this.resModel = this.context.active_model || (this.context.params && this.context.params.active_model);
//         // if (!this.resModel) {
//         //     if (this.props.action.res_model) {
//         //         const actionModel = await this.orm.read('ir.model', [Number(this.props.action.res_model)], ['model']);
//         //         if (actionModel.length && actionModel[0].model) {
//         //             this.resModel = actionModel[0].model
//         //         }
//         //     } else if (this.props.action._originalAction) {
//         //         const originalContextAction = JSON.parse(this.props.action._originalAction).context;
//         //         if (originalContextAction) {
//         //             this.resModel = originalContextAction.active_model
//         //         }
//         //     }
//         // }
//         // const isTemplate = !this.resModel || this.resModel === 'product.template';
//         // this.reportModelName = `report.stock.report_product_${isTemplate ? 'template' : 'product'}_replenishment`;
//         // this.warehouses.splice(0, this.warehouses.length);
//         // this.warehouses.push(...await this.orm.call('report.stock.report_product_product_replenishment', 'get_warehouses', []));
//         // if (!this.context.warehouse) {
//         //     this.updateWarehouse(this.warehouses[0].id);
//         // }
//         // const reportValues = await this.orm.call(
//         //     this.reportModelName, 'get_report_values',
//         //     [],
//         //     {
//         //         context : this.context,
//         //         docids : [this.productId],
//         //         serialize : true,
//         //     }
//         //     );
//         // this.docs = {...reportValues.docs, ...reportValues.precision};

//         console.log('_getReportValues _getReportValues _getReportValues')

//         console.log(this.hola);

//         return () => {}
//     }
// });


// ------------------------------------------

/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { View } from "@web/views/view";
import { useSetupAction } from "@web/webclient/actions/action_hook";

import { ForecastedButtons } from "@stock/stock_forecasted/forecasted_buttons";
import { ForecastedDetails } from "@stock/stock_forecasted/forecasted_details";
import { ForecastedHeader } from "@stock/stock_forecasted/forecasted_header";
import { ForecastedWarehouseFilter } from "@stock/stock_forecasted/forecasted_warehouse_filter";

const { Component, onWillStart, useState, useSubEnv} = owl;

class StockForecasted extends Component{
    setup(){
        useSetupAction();
        useSubEnv({
            //ControlPanel trick : Allow the use of ControlPanel's bottom-right while disabling search to avoid errors
            searchModel:{
                searchMenuTypes : [],
            },
        });
        this.env.config.viewSwitcherEntries = [];

        this.orm = useService("orm");
        this.action = useService("action");

        this.context = useState(this.props.action.context);
        this.productId = this.context.active_id;
        this.title = this.props.action.name || _t("Forecasted Report");
        if(!this.context.active_id){
            this.context.active_id = this.props.action.params.active_id;
            this.reloadReport();
        }

        this.docs = useState({});
        this.warehouses = useState([]);

        onWillStart(this._getReportValues);
    }

    async _add_inlay_port_field () {
        let is_there_document_in = false
        const document_in_ids = []

        this.docs.lines.forEach(line => {
            if (line.document_in) {
                is_there_document_in = true;

                document_in_ids.push(line.document_in.id)
            }
        });

        if (!is_there_document_in) return;

        try {
            const recordset_document_in = await this.orm.searchRead(
                'purchase.order',
                [
                    ['id', 'in', document_in_ids],
                ],
                ['inlay_port']
            );

            const lines = this.docs.lines.map( (line) => {

                const record_document_in = recordset_document_in.find((rc) => {
                    return rc.id === line.document_in.id
                })

                let inlay_port = ''

                if (record_document_in) {
                    inlay_port = record_document_in.inlay_port
                }

                return {
                    ...line,
                    document_in: {
                        ...line.document_in,
                        inlay_port
                    }
                }
            })

            this.docs = {
                ...this.docs,
                is_there_document_in,
                lines,
            }

        } catch (error) {
            console.error(error);
        }
    }

    async _getReportValues(){
        this.resModel = this.context.active_model || (this.context.params && this.context.params.active_model);
        if (!this.resModel) {
            if (this.props.action.res_model) {
                const actionModel = await this.orm.read('ir.model', [Number(this.props.action.res_model)], ['model']);
                if (actionModel.length && actionModel[0].model) {
                    this.resModel = actionModel[0].model
                }
            } else if (this.props.action._originalAction) {
                const originalContextAction = JSON.parse(this.props.action._originalAction).context;
                if (originalContextAction) {
                    this.resModel = originalContextAction.active_model
                }
            }
        }
        const isTemplate = !this.resModel || this.resModel === 'product.template';
        this.reportModelName = `report.stock.report_product_${isTemplate ? 'template' : 'product'}_replenishment`;
        this.warehouses.splice(0, this.warehouses.length);
        this.warehouses.push(...await this.orm.call('report.stock.report_product_product_replenishment', 'get_warehouses', []));
        if (!this.context.warehouse) {
            this.updateWarehouse(this.warehouses[0].id);
        }
        const reportValues = await this.orm.call(
            this.reportModelName, 'get_report_values',
            [],
            {
                context : this.context,
                docids : [this.productId],
                serialize : true,
            }
        );

        this.docs = {
            ...reportValues.docs, 
            ...reportValues.precision, 
            is_there_document_in: false
        };

        await this._add_inlay_port_field()

    }

    async updateWarehouse(id){
        const hasPreviousValue = this.context.warehouse !== undefined;
        this.context.warehouse = id;
        if(hasPreviousValue)
            await this.reloadReport();
    }

    async reloadReport(){
        return this.action.doAction({
            type: "ir.actions.client",
            tag: "replenish_report",
            context: this.context,
            name : this.title,
        },
        {
            stackPosition: 'replaceCurrentAction'
        });
        //await this._getReportValues();
    }

    get graphDomain() {
        const domain = [
            ['state', '=', 'forecast'],
            ['warehouse_id', '=', this.context.warehouse],
        ];
        if (this.resModel === undefined || this.resModel === 'product.template') {
            domain.push(['product_tmpl_id', '=', this.productId]);
        } else if (this.resModel === 'product.product') {
            domain.push(['product_id', '=', this.productId]);
        }
        return domain;
    }

    get graphInfo() {
        return {noContentHelp: this.env._t('Try to add some incoming or outgoing transfers.')};
    }

    async openView(resModel, view, resId) {
        const action = {
            type: 'ir.actions.act_window',
            res_model: resModel,
            views: [[false, view]],
            view_mode: view,
            res_id: resId,
        }
        return this.action.doAction(action);
    }
}

StockForecasted.template = 'stock.Forecasted';
StockForecasted.components = {ControlPanel, ForecastedButtons, ForecastedWarehouseFilter, ForecastedHeader, View, ForecastedDetails};
registry.category("actions").add("replenish_report", StockForecasted);
