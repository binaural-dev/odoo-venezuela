from odoo import SUPERUSER_ID, http
from odoo.api import Environment
from odoo.exceptions import AccessError

XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class AccountingReportsController(http.Controller):
    def _get_wizard(self, wizard_id):
        """Return the wizard requested by the current user.

        The book is generated with a superuser environment, so the wizard must
        belong to the user and its company must be one they can access.
        """
        request_env = http.request.env
        wizard = Environment(request_env.cr, SUPERUSER_ID, request_env.context)[
            "wizard.accounting.reports"
        ].browse(int(wizard_id)).exists()
        if (
            not wizard
            or wizard.create_uid != request_env.user
            or wizard.company_id not in request_env.user.company_ids
        ):
            raise AccessError(request_env._("You cannot access this report."))
        return wizard

    def _xlsx_response(self, file, filename):
        return http.request.make_response(
            file,
            headers=[
                ("Content-Type", XLSX_MIMETYPE),
                ("Content-Disposition", f"attachment;filename={filename}"),
            ],
        )

    @http.route("/web/download_sales_book", type="http", auth="user")
    def download_sales_book(self, wizard_id, **kw):
        wizard = self._get_wizard(wizard_id)
        return self._xlsx_response(wizard.generate_sales_book(wizard.company_id.id), "Libro_de_venta.xlsx")

    @http.route("/web/download_purchase_book", type="http", auth="user")
    def download_purchase_book(self, wizard_id, **kw):
        wizard = self._get_wizard(wizard_id)
        return self._xlsx_response(wizard.generate_purchases_book(wizard.company_id.id), "Libro_de_compra.xlsx")
