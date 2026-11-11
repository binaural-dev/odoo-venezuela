from collections.abc import Iterable

from odoo import api, fields, models

MIGRATED_KEY = "binaural_migrated"


class IrModule(models.Model):
    _inherit = "ir.module.module"

    binaural = fields.Boolean(default=False)
    migration_state = fields.Selection(
        [("migrated", "Migrated"), ("pending", "Pending migration")],
        compute="_compute_migration_state",
        search="_search_migration_state",
        help="Migrated: the manifest of the module says it is migrated to this version of Odoo "
        "(key binaural_migrated). Pending migration: a module that is not from Odoo and cannot be "
        "installed in this version yet.",
    )

    @api.depends("name", "state", "author")
    def _compute_migration_state(self):
        """
        The manifest is read when the screen asks for it, not when the list of modules is updated:
        marking a module as migrated shows on the screen without updating anything.
        """
        for module in self:
            if self.get_module_info(module.name).get(MIGRATED_KEY):
                module.migration_state = "migrated"
            elif module.state == "uninstallable" and not (module.author or "").startswith("Odoo S"):
                module.migration_state = "pending"
            else:
                module.migration_state = False

    def _search_migration_state(self, operator, value):
        if operator not in ("in", "not in", "=", "!="):
            return NotImplemented
        values = set(value) if isinstance(value, Iterable) and not isinstance(value, str) else {value}
        modules = self.with_context(active_test=False).search([])
        matching = modules.filtered(lambda module: module.migration_state in values)
        return [("id", "in" if operator in ("in", "=") else "not in", matching.ids)]
