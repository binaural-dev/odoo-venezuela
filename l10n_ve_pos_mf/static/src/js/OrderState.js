// /** @odoo-module **/

// import { patch } from "@web/core/utils/patch";
// import { PosOrder } from "@point_of_sale/app/models/pos_order";

// patch(PosOrder.prototype, {
//   init_from_JSON(json) {
//     // primero deja que el core reconstruya el pedido
//     super.init_from_JSON(json);
//     // luego tus campos adicionales
//     this.fiscal_machine = json.fiscal_machine   || false;
//     this.mf_invoice_number = json.mf_invoice_number || false;
//     this.mf_reportz = json.mf_reportz       || false; // <-- bug fix: leer del json
//   },

//   export_as_JSON() {
//     const res = super.export_as_JSON();
//     res.fiscal_machine = this.fiscal_machine;
//     res.mf_invoice_number = this.mf_invoice_number;
//     res.mf_reportz = this.mf_reportz;
//     return res;
//   },

//   // En algunos flujos quieres que nunca lance error por "no editable"
//   assert_editable() {
//     // no-op
//   },
//   // Alias por si algún código llama la versión camelCase
//   assertEditable() {
//     // no-op
//   },
// });