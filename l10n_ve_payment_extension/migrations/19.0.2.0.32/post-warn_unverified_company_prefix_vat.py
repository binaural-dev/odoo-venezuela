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
    B1 regression this exists to prevent). Instead it fills
    `prefix_vat_confirmed` (l10n_ve_contact) the only way that doesn't
    require guessing:

    - Companies whose prefix_vat is anything other than 'V' (E/J/G/P/C)
      could only have gotten there through someone deliberately picking it
      -- 'V' is the field's default, nothing else is. Those are marked
      confirmed=True; no letter was guessed, the letter that's already
      there is taken at face value.
    - Companies still at 'V' stay confirmed=False (ambiguous: could be a
      real V RIF, could be nobody having touched it) and get a chatter
      message asking an admin to review and, if correct, tick "Prefix VAT
      confirmed" in the company form (Accounting > Configuration >
      Companies). Since B6, the retention/ARCV/SENIAT reports refuse to
      generate for a company while this stays False (see
      ResCompany._check_prefix_vat_confirmed_for_fiscal_documents).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([("vat", "!=", False)])

    deliberately_set = companies.filtered(lambda c: c.partner_id.prefix_vat != "V")
    deliberately_set.partner_id.write({"prefix_vat_confirmed": True})

    unverified = companies - deliberately_set
    if not unverified:
        return

    _logger.warning(
        "l10n_ve_payment_extension 19.0.2.0.32: %d company(-ies) have "
        "prefix_vat='V' (the field's untouched default) despite having a "
        "vat set -- this literal was never confirmed and may be wrong. "
        "Fiscal documents (retention voucher, ARCV, SENIAT/ISLR/municipal "
        "filings) will refuse to generate for them until reviewed. "
        "Company ids: %s",
        len(unverified), unverified.ids,
    )
    for company in unverified:
        company.message_post(
            body=(
                "El literal del RIF de esta compañía (%s) quedó en 'V' por "
                "ser el valor por defecto del campo, no porque se haya "
                "confirmado -- revíselo en Contabilidad > Configuración > "
                "Compañías. Los reportes de retención, ARCV y los archivos "
                "del SENIAT no se generarán para esta compañía hasta que "
                "confirme el literal correcto y marque 'Prefix VAT "
                "confirmed'."
            )
            % (company.vat or "")
        )
