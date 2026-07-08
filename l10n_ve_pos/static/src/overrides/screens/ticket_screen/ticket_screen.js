/** @odoo-module **/

// Odoo 19: el core ya maneja el flujo completo de reembolso vía
// TicketScreen.onDoRefund (ver
// point_of_sale/static/src/app/screens/ticket_screen/ticket_screen.js:309).
//
// Los hooks _getToRefundDetail y _prepareRefundOrderlineOptions ya no
// existen en Odoo 19, y el componente FullRefundButton local dependía
// de ellos + de `order.orderlines` (renombrado a `order.lines`), así
// que ya no se importa aquí. Si en el futuro se quiere reactivar un
// botón "Reembolso total", debe reescribirse contra la API actual
// (`order.lines`, `toRefundLines`, `pos.linesToRefund`).
