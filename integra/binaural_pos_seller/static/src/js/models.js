odoo.define("binaural_pos_seller.models", function (require) {
    'use strict';

    const { PosGlobalState } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const BinauralPosSellerModels = (PosGlobalState) =>
        class extends PosGlobalState {
            async _processData(loadedData) {
                await super._processData(loadedData);
                const employeeIds = this.env.pos.config.employee_ids;
                let employees = !!loadedData['hr.employee'] ? loadedData['hr.employee'] : [];
                if(!!employeeIds){
                    this.employees = employees.filter((employee) => {
                        return (
                            employeeIds.includes(employee.id)
                        );
                    });
                }else{
                    this.employees = employees; 
                }
                this.sellers = employees.filter((employee) => employee.is_seller !== false);
            }
        };

    Registries.Model.extend(PosGlobalState, BinauralPosSellerModels);
});
