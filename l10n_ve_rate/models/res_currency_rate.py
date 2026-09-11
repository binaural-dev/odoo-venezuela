from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def compute_rate(self, foreign_currency_id, rate_date, raise_if_not_found=False):
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
            Whether the absence of a usable rate should raise UserError, instead of
            returning {}. Defaults to False: this method is reached from many
            "automatic" paths that are not a deliberate user request for a rate -
            record defaults on create(), a create()-time chatter comparison against
            the current rate, and even the plain @api.depends compute for
            foreign_rate/foreign_inverse_rate, which the ORM can re-trigger from
            unrelated code simply reading that field (e.g. sale.order._prepare_invoice()
            reading self.foreign_rate). None of those call sites can meaningfully
            react to a hard error, so raising there would block unrelated operations
            (creating an order, preparing an invoice) entirely, for every user,
            whenever nobody has loaded today's rate yet.

            raise_if_not_found=True only makes sense from a call site built
            specifically to let the user act on the error in place (e.g. a
            dedicated "recalculate rate" button or onchange) - no such call site
            exists yet in this codebase; the parameter is kept available for one to
            opt into deliberately, rather than baked into the shared compute chain.

        The search only ever looks backwards in time: it filters rates with
        name <= rate_date and takes the closest one (name DESC, limit 1). If there
        is no rate for rate_date itself but there are rates both before and after it,
        the closest one *before* it is used - rates dated after rate_date are excluded
        by the domain itself and never considered, regardless of how close they are.

        Raises
        ------
        UserError
            If raise_if_not_found is True and there is no rate at or before rate_date
            for this currency/company - i.e. rate_date is older than every recorded
            rate (or none exist at all). This does not happen just because there is
            no rate for that exact date; it only happens when there is no earlier
            rate to fall back to either.

        Returns
        -------
        dict
            A dictionary with the rate and inverse rate for the given currency and
            date, or {} if no rate was found and raise_if_not_found is False.
        """
        rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", foreign_currency_id),
                ("company_id", "=", self.env.company.id),
                ("name", "<=", rate_date),
            ],
            order="name DESC", limit=1,
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
        foreign_currency_id = self.env.company.foreign_currency_id.id or False
        inverse_rate = (1 / rate) if rate and foreign_currency_id == base_usd_id else rate
        return inverse_rate
