"""A las 8 pm de Caracas el servidor (UTC) ya esta en el dia siguiente.

`pos.config._compute_rate` busca la tasa con `fields.Date.today()` (fecha UTC) y
`raise_if_not_found=False`: a las 8 pm no encuentra la tasa de "manana", no lanza
error y deja la caja con tasa 0 en silencio. Esta prueba FALLA mientras se use la
fecha del servidor.
"""

from odoo.addons.l10n_ve_accountant.tests.common_tz_boundary import (
    CARACAS_DAY,
    FROZEN_UTC_NOW,
    USD_PER_VEF_INVERSE,
    TzBoundaryMixin,
    freeze_time,
)
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_tz_boundary")
class TestPosConfigServerDateVsUserTz(TzBoundaryMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self._setup_tz_boundary()

    def test_pos_config_rate_at_8pm_uses_user_day_rate(self):
        with freeze_time(FROZEN_UTC_NOW):
            config = self.env["pos.config"].create({"name": "TZ POS"})
            config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
            config._compute_rate()
            self.assertAlmostEqual(
                config.foreign_rate,
                USD_PER_VEF_INVERSE,
                places=4,
                msg=(
                    "A las 8 pm de Caracas la caja debe tomar la tasa del dia del "
                    f"usuario ({CARACAS_DAY}); quedo en 0 por buscar la fecha UTC."
                ),
            )
