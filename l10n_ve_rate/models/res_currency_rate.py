from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def compute_rate(self, foreign_currency_id, rate_date, raise_if_not_found=False):
        # .parent_ids o .ids contiene la compañía actual y todas sus compañías padre
        company_ids = self.env.company.parent_ids.ids if hasattr(self.env.company, 'parent_ids') else [self.env.company.id]

        rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", foreign_currency_id),
                ("company_id", "in", company_ids), # Busca en la sucursal o en cualquiera de sus padres
                ("name", "<=", rate_date),
            ],
            order="name DESC", limit=1
        )

        if not rate:
            if raise_if_not_found:
                raise UserError(_("There is no rate for that date, please configure one."))
            return {}

        vef_id = self.env.company.currency_id.id
        if vef_id == foreign_currency_id:
            return {
                "foreign_rate": rate.company_rate,
                "foreign_inverse_rate": rate.company_rate,
            }
        else:
            return {
                "foreign_rate": rate.inverse_company_rate,
                "foreign_inverse_rate": rate.company_rate,
            }

    @api.model
    def compute_inverse_rate(self, rate):
        """
        Compute the inverse rate for the given rate.
        The inverse rate will be the inverse of the given rate if the foreign currency is USD, else
        the inverse rate will be the same as the given rate.

        Parameters
        ----------
        rate : float
            The rate that is gonna be used to compute the inverse rate.

        Returns
        -------
        float
            The inverse rate for the given rate.
        """
        base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.USD", raise_if_not_found=False
        )
        
        # Obtener la moneda extranjera buscando en la compañía actual o en sus matrices
        company_ids = self.env.company.parent_ids.ids if hasattr(self.env.company, 'parent_ids') else [self.env.company.id]
        companies = self.env["res.company"].browse(company_ids)
        
        # Toma la primera moneda extranjera definida en la jerarquía (de abajo hacia arriba)
        foreign_currency_id = next(
            (comp.foreign_currency_id.id for comp in companies if comp.foreign_currency_id), 
            False
        )

        inverse_rate = (1 / rate) if rate and foreign_currency_id == base_usd_id else rate
        return inverse_rate