from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def compute_rate(self, foreign_currency_id, rate_date, raise_if_not_found=True):
        """
        Compute the rate and inverse rate for the given currency and date.

        If the foreign currency is USD then the rate will be the inverse company rate and the
        inverse rate will be the company rate, Else both rates will be the company rate.

        This is done because the foreign rate will be the rate that is gonna be shown to the user
        and the inverse rate will be the rate that will be used as factor to multiply for the
        computation of the foreign amounts.

        The logic is that if the foreign currency is VEF then we will be always multiplying by the
        value the user uses and see as the rate, but if the foreign currency is USD then we will be
        always multiplying by the inverse rate because the user will see the rate as the inverse
        rate.

        Parameters
        ----------
        foreign_currency_id : int
            The id of the foreign currency.
        rate_date : date
            The date of the rate that is gonna be searched for the given currency
            (foreign_currency_id).
        raise_if_not_found : bool
            Whether the absence of a rate should raise UserError instead of
            returning {}. Defaults to True: every search that finds no rate for
            rate_date must stop with "no rate assigned". Pass False only from
            a call site that can deliberately work without a rate.

        La tasa se busca SOLO para la fecha exacta `rate_date`: no se usa la más
        cercana, ni la anterior, ni la posterior. Si la moneda no tiene un registro
        con esa fecha, se considera "no encontrada".

        Las tasas solo existen en la compañía principal (Odoo 19 no permite tasas en
        sucursales nativas). Se busca primero en la compañía activa y, si no hay
        resultado en ella, en su raíz (`root_id`): una sucursal resuelve así la tasa
        de la matriz.

        Raises
        ------
        UserError
            If raise_if_not_found is True (default) and the currency has no rate dated
            exactly rate_date in the company hierarchy.

        Returns
        -------
        dict
            A dictionary with the rate and inverse rate for the given currency and
            date, or {} if no rate was found and raise_if_not_found is False.
            The company currency without a recorded rate resolves to 1.0 / 1.0 (its rate
            against itself). {} is returned only when no foreign currency is given at
            all (there is no currency to look up).
        """

        if not foreign_currency_id:
            return {}

        company = self.env.company
        # las tasas solo viven en la compañía raíz (res.currency.rate._check_company_id);
        # la compañía activa va primero para que una tasa propia gane a la de la matriz
        company_ids = list(dict.fromkeys((company | company.root_id).ids))

        rate = self.env["res.currency.rate"]
        for company_id in company_ids:
            rate = rate.search(
                [
                    ("currency_id", "=", foreign_currency_id),
                    ("company_id", "=", company_id),
                    ("name", "=", rate_date),
                ],
                limit=1,
            )
            if rate:
                break

        if not rate:
            if foreign_currency_id == company.currency_id.id:
                # the company currency against itself is always 1
                return {"foreign_rate": 1.0, "foreign_inverse_rate": 1.0}
            if raise_if_not_found:
                currency = self.env["res.currency"].browse(foreign_currency_id)
                raise UserError(
                    _(
                        "There is no rate assigned for %(currency)s on %(date)s, please configure one.",
                        currency=currency.name,
                        date=rate_date,
                    )
                )
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

        Raises
        ------
        UserError
            If the rate is empty or zero: there is no rate to invert.

        Returns
        -------
        float
            The inverse rate for the given rate.
        """
        if not rate:
            raise UserError(_("There is no rate assigned, please configure one."))
        base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "base.USD", raise_if_not_found=False
        )
        foreign_currency_id = self.env.company.foreign_currency_id.id or False
        inverse_rate = (1 / rate) if rate and foreign_currency_id == base_usd_id else rate
        return inverse_rate
