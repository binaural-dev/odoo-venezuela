from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Campos que copia _transport_values_from_fleet(vehicle=...). Se usan tanto
# para completarlos como para vaciarlos cuando se quita el vehículo.
TRANSPORT_VEHICLE_FIELDS = (
    "transport_vehicle_plate",
    "transport_vehicle_brand",
    "transport_vehicle_model",
    "transport_driver_name",
    "transport_driver_vat",
    "transport_driver_license_type",
    "transport_driver_contact",
    "transport_vehicle_type",
)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    transport_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehicle",
        copy=False,
        tracking=True,
        check_company=True,
        domain="[('is_trailer', '=', False)]",
    )
    transport_trailer_id = fields.Many2one(
        "fleet.vehicle",
        string="Trailer",
        copy=False,
        tracking=True,
        check_company=True,
        domain="[('is_trailer', '=', True)]",
    )

    @api.depends("transport_data_source", "transport_vehicle_id", "transport_trailer_id")
    def _compute_transport_data_locked(self):
        # Solo bloquea los campos de VEHÍCULO de la guía que ya tiene un
        # vehículo/batea de Flota elegido; un transportista externo sin
        # ficha en Flota sigue pudiendo cargar los datos a mano aunque la
        # compañía use 'fleet'. El conductor del día nunca se bloquea por
        # este campo (las vistas ya no lo usan en los campos de conductor):
        # debe poder corregirse aunque el vehículo esté elegido.
        for picking in self:
            picking.transport_data_locked = picking.transport_data_source == "fleet" and bool(
                picking.transport_vehicle_id or picking.transport_trailer_id
            )

    # ------------------------------------------------------------------
    # Copia de datos desde Flota. Nunca related/compute almacenado: la guía
    # guarda una foto de los datos al elegir el vehículo y el usuario puede
    # corregirla (p. ej. otro conductor ese día). Un cambio posterior en
    # Flota no altera las guías existentes.
    # ------------------------------------------------------------------

    @api.model
    def _transport_format_vat(self, partner):
        """Cédula del conductor con su prefijo (V, E...). l10n_ve_contact
        guarda el prefijo aparte, en prefix_vat."""
        if not partner.vat:
            return False
        vat = partner.vat
        prefix = partner.prefix_vat if "prefix_vat" in partner._fields else False
        if prefix and not vat[:1].isalpha():
            vat = f"{prefix}{vat}"
        return vat

    @api.model
    def _transport_driver_contact(self, partner):
        """Móvil del conductor; si no tiene, su teléfono. El móvil lo agrega
        l10n_ve_contact."""
        mobile = partner.mobile if "mobile" in partner._fields else False
        return mobile or partner.phone or False

    @api.model
    def _transport_values_from_fleet(self, vehicle=None, trailer=None):
        vals = {}
        if vehicle:
            driver = vehicle.driver_id
            vals.update({
                "transport_vehicle_plate": vehicle.license_plate or False,
                "transport_vehicle_brand": vehicle.model_id.brand_id.name or False,
                "transport_vehicle_model": vehicle.model_id.name or False,
                "transport_driver_name": driver.name or False,
                "transport_driver_vat": self._transport_format_vat(driver),
                "transport_driver_license_type": driver.driver_license_type or False,
                "transport_driver_contact": self._transport_driver_contact(driver),
                "transport_vehicle_type": vehicle.category_id.name or False,
            })
        if trailer:
            vals["transport_trailer_plate"] = trailer.license_plate or False
        return vals

    @api.model
    def _transport_complete_vals(self, vals):
        """Para create/write por API o importación: completa los datos de
        texto que no vengan explícitos, o los vacía si el vehículo/batea se
        quitan explícitamente (vals trae la clave en False/None). setdefault
        respeta lo que el usuario ya corrigió en el formulario (el onchange
        los envía en vals)."""
        Vehicle = self.env["fleet.vehicle"]
        if "transport_vehicle_id" in vals:
            vehicle_id = vals["transport_vehicle_id"]
            if vehicle_id:
                fleet_vals = self._transport_values_from_fleet(vehicle=Vehicle.browse(vehicle_id))
            else:
                fleet_vals = dict.fromkeys(TRANSPORT_VEHICLE_FIELDS, False)
            for key, value in fleet_vals.items():
                vals.setdefault(key, value)
        if "transport_trailer_id" in vals:
            trailer_id = vals["transport_trailer_id"]
            if trailer_id:
                fleet_vals = self._transport_values_from_fleet(trailer=Vehicle.browse(trailer_id))
            else:
                fleet_vals = {"transport_trailer_plate": False}
            for key, value in fleet_vals.items():
                vals.setdefault(key, value)
        return vals

    @api.constrains("transport_vehicle_id", "transport_trailer_id", "company_id")
    def _check_transport_fleet_company(self):
        # stock.picking no activa _check_company_auto: sin esto, por API o
        # importación se podría asignar un vehículo de otra compañía.
        self._check_company(["transport_vehicle_id", "transport_trailer_id"])

    @api.constrains("transport_vehicle_id", "transport_trailer_id")
    def _check_transport_vehicle_trailer_type(self):
        # El domain is_trailer en los campos es solo de UI/name_search; sin
        # este constrain, por API o importación se podría cargar una batea
        # en "Vehículo" (o viceversa), mal-etiquetando el documento fiscal
        # enviado a The Factory HKA.
        for picking in self:
            if picking.transport_vehicle_id and picking.transport_vehicle_id.is_trailer:
                raise ValidationError(
                    _(
                        "'%(vehicle)s' is marked as a trailer in Fleet and cannot "
                        "be used as the main vehicle."
                    )
                    % {"vehicle": picking.transport_vehicle_id.display_name}
                )
            if picking.transport_trailer_id and not picking.transport_trailer_id.is_trailer:
                raise ValidationError(
                    _(
                        "'%(vehicle)s' is not marked as a trailer in Fleet and "
                        "cannot be used as the trailer."
                    )
                    % {"vehicle": picking.transport_trailer_id.display_name}
                )

    @api.constrains("transport_vehicle_id", "transport_trailer_id")
    def _check_transport_vehicle_driver_is_not_company(self):
        # Chequea driver_id.is_company directamente: un vehiculo guardado
        # antes de que fleet_vehicle.py validara esto (o con la cedula del
        # conductor mal cargada, sin reflejar que es_company) igual no debe
        # poder usarse en una guia.
        for picking in self:
            for fname in ("transport_vehicle_id", "transport_trailer_id"):
                vehicle = picking[fname]
                if vehicle and vehicle.driver_id and vehicle.driver_id.is_company:
                    raise ValidationError(
                        _(
                            "The vehicle '%(vehicle)s' has a company as its "
                            "driver in Fleet ('%(driver)s'). Fix the driver in "
                            "Fleet before using this vehicle in a dispatch guide."
                        )
                        % {
                            "vehicle": vehicle.display_name,
                            "driver": vehicle.driver_id.name,
                        }
                    )

    @api.onchange("transport_vehicle_id")
    def _onchange_transport_vehicle_id(self):
        for picking in self:
            if picking.transport_vehicle_id:
                picking.update(
                    picking._transport_values_from_fleet(vehicle=picking.transport_vehicle_id)
                )
            else:
                picking.update(dict.fromkeys(TRANSPORT_VEHICLE_FIELDS, False))

    @api.onchange("transport_trailer_id")
    def _onchange_transport_trailer_id(self):
        for picking in self:
            if picking.transport_trailer_id:
                picking.update(
                    picking._transport_values_from_fleet(trailer=picking.transport_trailer_id)
                )
            else:
                picking.transport_trailer_plate = False

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._transport_complete_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if "transport_vehicle_id" in vals or "transport_trailer_id" in vals:
            vals = self._transport_complete_vals(dict(vals))
        return super().write(vals)
