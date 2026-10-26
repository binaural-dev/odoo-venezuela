from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def check_duplicate_email(self, email, company_id=None, parent_id=False):
        """Omite la validación de correos duplicados de l10n_ve_contact, pero
        solo en compañías que digitalizan con TFHKA.

        La digitalización necesita poder repetir el correo entre contactos, pero
        acotarlo por compañía importa: el email del partner es el canal al que
        TFHKA notifica el documento (ver tfhka.service.base._get_fiscal_party,
        que envía "notificar": "Si" con "correo": [partner.email]), así que
        permitir duplicados en una compañía que no usa TFHKA solo abre la puerta
        a que un buzón reciba documentos fiscales de un tercero.

        La compañía que decide es la recibida en ``company_id``, no la
        compañía activa del usuario/contexto (``self.env.company``): en
        multi-compañía, un usuario con la compañía TFHKA activa no debe poder
        colar duplicados que en realidad pertenecen a otra compañía que no
        digitaliza. Si no se recibe ``company_id`` (caso de los call sites de
        l10n_ve_contact, que nunca lo pasan), se mantiene el fallback a
        ``self.env.company`` para no alterar ese comportamiento existente.
        """
        company = (
            self.env["res.company"].browse(company_id)
            if company_id
            else self.env.company
        )
        if company.invoice_digital_tfhka:
            return
        return super().check_duplicate_email(
            email, company_id=company_id, parent_id=parent_id
        )
