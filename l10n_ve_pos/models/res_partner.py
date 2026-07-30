from odoo import models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Odoo 19 loader contract: extend the read with the Venezuelan
        ``prefix_vat`` (Selection) and ``city_id`` fields used by the POS UI.
        """
        res = super()._load_pos_data_fields(config_id)
        extra = [name for name in ('prefix_vat', 'city_id') if name not in res]
        return res + extra

    # Campos de localización que el formulario reducido del PdV precarga con la
    # dirección de la compañía para que el cajero no los teclee en cada venta.
    # No se incluye "city" (Char) porque es related="city_id.name", store=True
    # y escribible: escribirla renombraría el registro res.country.city. Se
    # rellena sola en cuanto se fija city_id.
    _POS_COMPANY_DEFAULT_FIELDS = (
        "country_id",
        "state_id",
        "city_id",
        "municipality",
        "parish_id",
        "zip",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not self.env.context.get("l10n_ve_pos_partner_defaults"):
            return values
        # Un contacto hijo hereda la dirección de su padre (contexto default_*
        # del o2m child_ids), no la de la compañía.
        if values.get("parent_id") or self.env.context.get("default_parent_id"):
            return values
        company_partner = self.env.company.partner_id
        if not company_partner:
            return values
        for fname in self._POS_COMPANY_DEFAULT_FIELDS:
            # Respeta cualquier valor ya resuelto por super() (claves default_*
            # del contexto o defaults de campo, p.ej. el país de l10n_ve_contact).
            if fname not in fields_list or values.get(fname):
                continue
            value = company_partner[fname]
            if not value:
                continue
            values[fname] = value.id if self._fields[fname].type == "many2one" else value
        return values
