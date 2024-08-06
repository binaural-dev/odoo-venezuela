from odoo import api, fields, models, tools, _
import logging

_logger = logging.getLogger(__name__)


class StockMoveReport(models.Model):
    _name = "stock.move.line.report"
    _auto = False
    _description = "Stock Move Report"
    _rec_name = "date"
    _order = "date, product_id"

    date = fields.Datetime()
    product_id = fields.Many2one("product.product")
    reference = fields.Char()
    origin = fields.Char()
    move_type = fields.Selection(
        [
            ("purchase", "PURCHASE"),
            ("sale", "SALE"),
            ("purchase_reverse", "PURCHASE REV"),
            ("sale_reverse", "SALE REV"),
            ("move", "MOVE"),
            ("product_integrator", "ARTÍCULO INTEGRADOR"),
            ("product_integrator_reverse", "DEV ARTÍCULO INTEGRADOR"),
            ("outgoing", "OUTGOING"),
            ("incoming", "INCOMING"),
            ("internal", "INTERNAL"),
            ("adjustment", "ADJUSTMENT"),
            ("scrap", "SCRAP"),
        ]
    )

    qty_in = fields.Float("Quantity in")
    qty_out = fields.Float("Quantity out")
    balance = fields.Float()
    company_id = fields.Many2one(
        "res.company",
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    {self._select()}
                    {self._from()}
                    {self._join()}
                    {self._where()}
                )
            """
        )

    def _select(self):
        # Init
        select = """
                SELECT
                    ml.company_id,
                    ml.id,
                    ml.date,
                    ml.product_id,
                    ml.reference,
                    COALESCE(sp.origin, sm.origin, ml.origin) AS origin,
            """

        select += f""" ({self.get_column_move_type()}) AS move_type,"""

        select += """
                (
                    CASE WHEN (ml.balance < 0) THEN
                        0.0
                    ELSE
                        ml.qty_done
                    END
                ) AS qty_in,
                (
                    CASE WHEN (ml.balance < 0) THEN
                        ml.qty_done
                    ELSE
                        0.0
                    END
                ) AS qty_out,
                (
                    SUM(ml.balance) OVER (PARTITION BY ml.company_id, ml.product_id ORDER BY ml.date) 
                ) AS balance
            """

        return select

    def get_column_move_type(self):
        # Validate exists columns in models
        is_exists_unbuild_id_in_stock_move = (
            "unbuild_id" in self.env["stock.move"]._fields
        )
        is_exists_production_id_in_stock_move_line = (
            "production_id" in self.env["stock.move.line"]._fields
        )
        is_exists_pos_order_id_in_stock_picking = (
            "pos_order_id" in self.env["stock.picking"]._fields
        )

        column_move_type = "CASE "
        if (
            is_exists_unbuild_id_in_stock_move
            or is_exists_production_id_in_stock_move_line
        ):
            column_move_type += """
                        WHEN (sm.unbuild_id IS NOT NULL) THEN
                            CASE WHEN (sl.id = sld.id) THEN
                                'sale_reverse'
                            ELSE
                                'product_integrator_reverse'
                            END
                        WHEN (ml.production_id IS NOT NULL) THEN
                            CASE WHEN (sl.usage = 'internal' AND sld.usage = 'production' AND ml.origin IS NULL) THEN
                                'product_integrator'
                            ELSE
                                'sale'
                            END
                    """
        if is_exists_pos_order_id_in_stock_picking:
            column_move_type += """
                        WHEN (sp.sale_id IS NOT NULL OR sp.pos_order_id IS NOT NULL OR sm.purchase_line_id IS NOT NULL) THEN
                            CASE WHEN (sl.usage = 'customer') THEN
                                    'sale_reverse'
                                WHEN (sld.usage = 'supplier') THEN
                                    'purchase_reverse'
                                WHEN (sl.usage = 'internal') THEN
                                    'sale'
                                WHEN (sl.usage = 'supplier') THEN
                                    'purchase'
                            END
                        """
        elif not is_exists_pos_order_id_in_stock_picking:
            column_move_type += """
                        WHEN (sp.sale_id IS NOT NULL OR sm.purchase_line_id IS NOT NULL) THEN
                            CASE WHEN (sl.usage = 'customer') THEN
                                    'sale_reverse'
                                WHEN (sld.usage = 'supplier') THEN
                                    'purchase_reverse'
                                WHEN (sl.usage = 'internal') THEN
                                    'sale'
                                WHEN (sl.usage = 'supplier') THEN
                                    'purchase'
                            END
                        """

        column_move_type += """
                WHEN (ml.origin IS NOT NULL) THEN
                    'sale'
                ELSE
                    CASE WHEN (sp.picking_type_id IS NOT NULL) THEN
                        (
                            CASE WHEN (spt.code = 'outgoing') THEN
                                    'outgoing'
                                WHEN (spt.code = 'incoming') THEN
                                    'incoming'
                                WHEN (spt.code = 'internal') THEN
                                   CASE WHEN (sld.scrap_location = TRUE ) THEN
                                            'scrap'
                                        ELSE 
                                            'internal'
                                        END
                            END
                        )
                        ELSE
                            'adjustment'
                    END
                END
            """

        return column_move_type

    def _from(self):
        return """
            FROM stock_move_line AS ml
        """

    def _join(self):
        return """
            LEFT JOIN stock_location AS sl ON ml.location_id = sl.id
            LEFT JOIN stock_location AS sld ON ml.location_dest_id = sld.id
            LEFT JOIN stock_move AS sm ON ml.move_id = sm.id
            LEFT JOIN stock_picking AS sp ON sm.picking_id = sp.id
            LEFT JOIN uom_uom AS uom ON ml.product_uom_id = uom.id
            LEFT JOIN stock_picking_type AS spt ON spt.id = sp.picking_type_id
        """

    def _where(self):
        return """
            WHERE ml.state = 'done'
        """

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        results = super().read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )
        for idx, result in enumerate(results):
            if result.get("balance"):
                operation = (
                    results[idx - 1]["balance"] + (result["qty_in"] - result["qty_out"])
                    if idx >= 1 and not result.get("__context")
                    else (result["qty_in"] - result["qty_out"])
                )
                result["balance"] = operation
        return results
