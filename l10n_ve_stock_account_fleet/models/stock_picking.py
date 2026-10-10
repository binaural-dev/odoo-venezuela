from odoo import api, fields, models


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
        texto que no vengan explícitos. setdefault respeta lo que el usuario
        ya corrigió en el formulario (el onchange los envía en vals)."""
        vehicle_id = vals.get("transport_vehicle_id")
        trailer_id = vals.get("transport_trailer_id")
        if not (vehicle_id or trailer_id):
            return vals
        Vehicle = self.env["fleet.vehicle"]
        fleet_vals = self._transport_values_from_fleet(
            vehicle=Vehicle.browse(vehicle_id) if vehicle_id else None,
            trailer=Vehicle.browse(trailer_id) if trailer_id else None,
        )
        for key, value in fleet_vals.items():
            vals.setdefault(key, value)
        return vals

    @api.constrains("transport_vehicle_id", "transport_trailer_id", "company_id")
    def _check_transport_fleet_company(self):
        # stock.picking no activa _check_company_auto: sin esto, por API o
        # importación se podría asignar un vehículo de otra compañía.
        self._check_company(["transport_vehicle_id", "transport_trailer_id"])

    @api.onchange("transport_vehicle_id")
    def _onchange_transport_vehicle_id(self):
        for picking in self.filtered("transport_vehicle_id"):
            picking.update(
                picking._transport_values_from_fleet(vehicle=picking.transport_vehicle_id)
            )

    @api.onchange("transport_trailer_id")
    def _onchange_transport_trailer_id(self):
        for picking in self.filtered("transport_trailer_id"):
            picking.update(
                picking._transport_values_from_fleet(trailer=picking.transport_trailer_id)
            )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._transport_complete_vals(dict(vals)) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if "transport_vehicle_id" in vals or "transport_trailer_id" in vals:
            vals = self._transport_complete_vals(dict(vals))
        return super().write(vals)
