odoo.define("binaural_pos_seller.models", function (require) {
    'use strict';

    const { PosGlobalState } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const BinauralPosSellerModels = (PosGlobalState) =>
        class extends PosGlobalState {
            async _processData(loadedData) {
                await super._processData(loadedData);
                const employeeIds = this.env.pos.config.employee_ids;
                if(employeeIds){
                    this.employees = loadedData['hr.employee'].filter((employee) => {
                        return (
                            employeeIds.includes(employee.id)
                        );
                    });
                }else{
                    this.employees = loadedData['hr.employee']
                }
                this.sellers = loadedData['hr.employee'].filter((employee) => employee.is_seller !== false);
            }
        };

    Registries.Model.extend(PosGlobalState, BinauralPosSellerModels);
});