
from odoo import models, fields, api, _

class SaleLastPrice(models.TransientModel):
    _name = 'sale.last.price'
    _description = 'Sale Last Price'

    sale_line_id = fields.Many2one('sale.order.line')
    body_html = fields.Html('', compute='_compute_body_html')

    @api.depends('sale_line_id')
    def _compute_body_html(self):
        for record in self:
            body_html = "<p>{product}</p>".format(product=self.sale_line_id.product_id.display_name)
            if record.sale_line_id:
               
                order_line_ids = self.env['sale.order.line'].search([('id','!=',record.sale_line_id.id),
                                                                     ('order_id.partner_id','=',record.sale_line_id.order_id.partner_id.id),
                                                                     ('product_id','=',record.sale_line_id.product_id.id)
                                                                     ])
                if order_line_ids:
                    body_html += """
                    <table class="table table-sm table-striped"">
                        <thead>
                            <tr>
                                <th scope="col">#</th>
                                <th scope="col">Order</th>
                                <th scope="col">Date</th>
                                <th scope="col">Price</th>
                            </tr>
                        </thead>
                        <tbody>
                    """
                col = 1
                for order_line_id in order_line_ids:
                    body_html += """
                        <tr>
                            <th scope="row">{col}</th>
                            <td>{order_id}</td>
                            <td>{date}</td>
                            <td>{price}</td>
                        </tr>
                    """.format(col=col,
                               order_id=order_line_id.order_id.name,
                               date = order_line_id.order_id.date_order.date(),
                               price = order_line_id.price_unit
                               )
                    col += 1
                if order_line_ids:
                    body_html += """
                            </tbody>
                        </table>
                    """
            record.body_html = body_html
        

