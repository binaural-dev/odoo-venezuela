from odoo import models, fields, _
from odoo.exceptions import UserError
from pytz import timezone

# Zona horaria por defecto cuando el usuario no tiene una configurada.
TFHKA_DEFAULT_TZ = "America/Caracas"


class TfhkaServiceBase(models.AbstractModel):
    """Base compartida de los servicios de TFHKA.

    Reúne la obtención de datos comunes a factura y retención (paralelo a los
    helpers de ``unidigital.*.service``): la fecha/hora de emisión y el nodo de
    identificación fiscal del sujeto (comprador / sujeto retenido). La heredan
    ``tfhka.document.service`` y ``tfhka.retention.service``.

    Puntos de extensión (para que ``l10n_ve_dispatch_guide_digital`` reutilice
    esta base en el futuro):

    * :meth:`_get_party_source` — de qué contacto se toman los datos fiscales.
    * :meth:`_get_party_address` — qué campo de dirección se reporta.
    """

    _name = "tfhka.service.base"
    _description = "TFHKA Service Base"

    # ------------------------------------------------------------------
    # Fecha/hora de emisión
    # ------------------------------------------------------------------

    def _get_emission_datetime(self, record):
        """``now`` en la zona horaria del usuario, con fallback a Caracas."""
        tz = timezone(record.env.user.tz or TFHKA_DEFAULT_TZ)
        return fields.Datetime.now().astimezone(tz)

    # ------------------------------------------------------------------
    # Identificación del sujeto (comprador / sujeto retenido)
    # ------------------------------------------------------------------

    def _get_party_source(self, record):
        """Contacto del que se toman los datos fiscales. Punto de extensión."""
        record.ensure_one()
        return record.partner_id

    def _get_party_address(self, partner):
        """Dirección a reportar para el sujeto. Punto de extensión."""
        return partner.street or "no definida"

    def _get_fiscal_party(self, record):
        """Construye el nodo de identificación (comprador / sujeto retenido).

        Parseo de RIF/cédula (tipo + número), limpieza y validaciones de
        NIF/país/teléfono/correo comunes a factura y retención. Devuelve
        ``None`` si el registro no tiene contacto.
        """
        record.ensure_one()
        partner = self._get_party_source(record)
        if not partner:
            return None

        if not partner.vat:
            raise UserError(_("The 'NIF' field of the Customer cannot be empty for digitalization."))

        vat = partner.vat.upper()
        if vat[0].isalpha():
            identification_type = vat[0]
            identification_number = vat[1:]
        else:
            identification_type = ""
            identification_number = vat

        if partner.prefix_vat:
            identification_type = partner.prefix_vat

        identification_number = identification_number.replace("-", "").replace(".", "")

        if not partner.country_code:
            raise UserError(_("The 'Country' field of the Customer cannot be empty for digitalization."))

        if not (partner.mobile or partner.phone):
            raise UserError(_("The 'Mobile' field of the Customer cannot be empty for digitalization."))

        if not partner.email:
            raise UserError(_("The 'Email' field of the Customer cannot be empty for digitalization."))

        return {
            "tipoIdentificacion": identification_type,
            "numeroIdentificacion": identification_number,
            "razonSocial": partner.name,
            "direccion": self._get_party_address(partner),
            "pais": partner.country_code,
            "telefono": [partner.mobile or partner.phone],
            "notificar": "Si",
            "correo": [partner.email],
        }
