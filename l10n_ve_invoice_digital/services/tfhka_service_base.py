from odoo import models, fields, _
from odoo.exceptions import UserError
from pytz import timezone

# Zona horaria por defecto cuando el usuario no tiene una configurada.
TFHKA_DEFAULT_TZ = "America/Caracas"

# Código de impuesto TFHKA por alícuota (SENIAT): E=exento, R=reducida,
# G=general, A=adicional. Única fuente de verdad: la consumen tfhka.document.service
# (subtotales y líneas de detalle) y tfhka.dispatch.guide.service.
TFHKA_TAX_CODE_BY_RATE = {
    0.0: "E",
    8.0: "R",
    16.0: "G",
    31.0: "A",
}

# Tolerancia al comparar una alícuota contra TFHKA_TAX_CODE_BY_RATE. Cubre el
# error de redondeo cuando la alícuota se deriva de montos ya redondeados a dos
# decimales; las alícuotas válidas están separadas por 8 puntos, así que no hay
# riesgo de colisión.
TFHKA_RATE_TOLERANCE = 0.05


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
    # Impuestos: grupos y códigos TFHKA
    # ------------------------------------------------------------------

    def _iter_tax_groups(self, tax_totals, key="groups_by_subtotal"):
        """Todos los grupos de impuesto de ``tax_totals``, sin asumir el título
        del subtotal.

        Odoo arma la clave de ``groups_by_subtotal`` con
        ``tax_group.preceding_subtotal or _("Untaxed Amount")``
        (``account/models/account_tax.py``), es decir un string **traducible**:
        "Subtotal" en es_419, "Untaxed Amount" en inglés, "Importe base" en
        es_ES. Indexar ese dict por un literal devuelve ``[]`` en silencio y el
        documento fiscal viaja sin impuestos. Por eso se recorren todos los
        subtotales, mismo criterio que
        ``tfhka.retention.service._get_exempt_amount``.

        :param tax_totals: dict ``tax_totals`` de una factura/nota.
        :param key: ``"groups_by_subtotal"`` (moneda base) o
            ``"groups_by_foreign_subtotal"`` (moneda alterna).
        :return: lista plana de dicts de grupo, en el orden en que Odoo los agrupó.
        """
        return [
            group
            for groups in (tax_totals or {}).get(key, {}).values()
            for group in groups
        ]

    def _get_tfhka_tax_code(self, rate, label=""):
        """Código TFHKA para una alícuota numérica.

        :param rate: alícuota en puntos porcentuales (16.0, no 0.16).
        :param label: texto para el mensaje de error (producto o grupo).
        :return: tupla ``(code, rate)`` con la alícuota ya normalizada.
        :raise UserError: si la alícuota no está soportada por TFHKA.
        """
        for mapped_rate, code in TFHKA_TAX_CODE_BY_RATE.items():
            if abs(rate - mapped_rate) <= TFHKA_RATE_TOLERANCE:
                return code, mapped_rate
        raise UserError(_(
            "The tax rate %(rate)s%% on '%(label)s' is not supported "
            "by TFHKA digitalization (allowed rates: 0, 8, 16, 31).",
            rate=round(rate, 2), label=label,
        ))

    def _get_tax_group_code_and_rate(self, record, group):
        """``(codigoTotalImp, alicuotaImp)`` de un grupo de ``tax_totals``.

        NO usa ``tax_group_name``: ese nombre es traducible (el template
        ``l10n_ve_binaural/data/template/account.tax.group-ve.csv`` trae
        "VAT 16%" como nombre base e "IVA 16%" solo como ``name@es``) y además
        el cliente puede renombrar el grupo. La alícuota se resuelve en dos pasos:

        1. Impuestos de las líneas cuyo ``tax_group_id`` coincide con el del
           grupo (mismo patrón que ``account.retention.line._onchange_move_id``).
           Si hay exactamente una alícuota distinta, esa es.
        2. Si no hay impuestos que casen (notas de crédito, impuestos borrados
           después de emitir, o registros duck-typed en tests) o si el grupo
           mezcla alícuotas, se deriva del propio grupo:
           ``100 * tax_group_amount / tax_group_base_amount``. Un grupo exento
           da 0.0 y resuelve a "E" correctamente.

        El resultado se valida contra ``TFHKA_TAX_CODE_BY_RATE``: un grupo con
        alícuotas mezcladas cae fuera del mapeo y produce un ``UserError``
        legible en vez de un documento fiscal mal armado.
        """
        rate = None
        group_id = group.get("tax_group_id")
        lines = getattr(record, "invoice_line_ids", None)
        if group_id and lines is not None:
            taxes = lines.tax_ids.filtered(lambda t: t.tax_group_id.id == group_id)
            rates = set(taxes.mapped("amount"))
            if len(rates) == 1:
                rate = rates.pop()

        if rate is None:
            base = group.get("tax_group_base_amount") or 0.0
            rate = 100.0 * (group.get("tax_group_amount") or 0.0) / base if base else 0.0

        return self._get_tfhka_tax_code(rate, group.get("tax_group_name") or "")

    def _is_exempt_group(self, record, group):
        """``True`` si el grupo es exento / alícuota 0 (código TFHKA "E").

        Reemplaza la comparación por nombre ``in ("Exento", "IVA 0%")``, que
        falla en base inglesa (el grupo del template se llama "VAT 0%") y con
        cualquier grupo renombrado por el cliente.
        """
        code, _rate = self._get_tax_group_code_and_rate(record, group)
        return code == "E"

    def _get_igtf_rate(self, record):
        """Alícuota del IGTF, en puntos porcentuales.

        Se lee de ``res.company.igtf_percentage`` (``l10n_ve_igtf``), que es la
        misma fuente con la que ``account.tax._prepare_tax_totals`` arma
        ``tax_totals['igtf']['name'] = f"{igtf_percentage} %"``. El IGTF **no**
        pasa por :meth:`_get_tfhka_tax_code`: su código es la constante "IGTF" y
        su alícuota no pertenece al juego {0, 8, 16, 31}.
        """
        company = getattr(record, "company_id", None)
        if company and company.igtf_percentage:
            return company.igtf_percentage
        name = ((getattr(record, "tax_totals", None) or {}).get("igtf", {}) or {}).get("name") or ""
        try:
            return float(name.replace("%", "").strip())
        except ValueError:
            return 3.0

    # ------------------------------------------------------------------
    # Identificación del sujeto (comprador / sujeto retenido)
    # ------------------------------------------------------------------

    def _get_party_source(self, record):
        """Contacto del que se toman los datos fiscales. Punto de extensión."""
        record.ensure_one()
        return record.partner_id

    def _get_party_address(self, partner):
        """Dirección a reportar para el sujeto. Punto de extensión."""
        return partner.contact_address_complete or "no definida"

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
