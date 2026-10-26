import logging

from odoo import api, SUPERUSER_ID


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """`res.company.prefix_vat` (l10n_ve_contact) is a Selection field with
    default='V', and the company partner was never created with an explicit
    prefix_vat (see ResCompany.create() in l10n_ve_contact/models/res_company.py):
    every existing company has 'V' stored regardless of its real RIF literal
    (J/E/G/P/C). There is no way to derive the letter from `vat` alone --
    l10n_ve_contact's own _check_vat constrains only allows digits in that
    field, so the letter was never encoded there either.

    This migration does NOT guess the literal (a wrong guess is exactly the
    B1 regression this exists to prevent). It only surfaces, via a chatter
    message on each company record, which ones still carry the untouched
    default so an admin reviews and corrects `prefix_vat` in the company
    form (Accounting > Configuration > Companies) before the retention/ARCV/
    SENIAT reports that now print it start relying on that value.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([("vat", "!=", False)])
    unverified = companies.filtered(lambda c: c.partner_id.prefix_vat == "V")
    if not unverified:
        return

    _logger.warning(
        "l10n_ve_payment_extension 19.0.2.0.31: %d company(-ies) have "
        "prefix_vat='V' (the field's untouched default) despite having a "
        "vat set -- this literal was never confirmed and may be wrong. "
        "Review it in the company form before relying on the RIF printed "
        "in retention/ARCV/SENIAT reports. Company ids: %s",
        len(unverified), unverified.ids,
    )
    for company in unverified:
        company.message_post(
            body=(
                "El literal del RIF de esta compañía (%s) quedó en 'V' por "
                "ser el valor por defecto del campo, no porque se haya "
                "confirmado -- revíselo en Contabilidad > Configuración > "
                "Compañías antes de confiar en el RIF impreso en el "
                "comprobante de retención, ARCV, o los archivos del SENIAT."
            )
            % (company.vat or "")
        )
