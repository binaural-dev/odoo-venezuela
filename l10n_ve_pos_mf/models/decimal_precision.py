from odoo import api, fields, models

# Los documentos fiscales (máquina fiscal, Unidigital) solo admiten 2 decimales
# en el precio unitario.
PRICE_DIGITS = 2
FISCAL_PRICE_PRECISIONS = (
    "product.decimal_price",  # Product Price
    "l10n_ve_accountant.alternative_price_product",  # Foreign Product Price
)


class DecimalPrecision(models.Model):
    """Mismo código y mismos nombres de método que en
    ``binaural_unidigital_pos``: con los dos módulos instalados, uno reemplaza
    al otro y el formulario muestra una sola advertencia."""

    _name = "decimal.precision"
    _inherit = ["decimal.precision", "mail.thread"]

    # El chatter registra quién cambió los dígitos, cuándo y de cuánto a cuánto.
    digits = fields.Integer(tracking=True)

    @api.onchange("digits")
    def _onchange_digits_fiscal_price_warning(self):
        """Advierte, sin impedirlo, al sacar de 2 decimales una precisión de
        precio que usan los documentos fiscales."""
        if self.digits == PRICE_DIGITS or not (self._origin & self._fiscal_price_precisions()):
            return None
        return {
            "warning": {
                "title": self.env._("Fiscal price precision"),
                "message": self.env._(
                    "Fiscal documents only accept %(fiscal_digits)s decimals in the unit "
                    "price. With %(digits)s decimals in %(precision)s, the amounts in Odoo may "
                    "not match the fiscal document.\n\n"
                    "The change will be recorded in the history of this precision.",
                    fiscal_digits=PRICE_DIGITS,
                    digits=self.digits,
                    precision=self._origin.name,
                ),
            }
        }

    def _set_fiscal_price_digits(self):
        """Pone en 2 las precisiones de precio fiscal. Lo usa la migración para
        las bases donde el módulo ya estaba instalado; queda en el chatter de
        cada precisión."""
        self._fiscal_price_precisions().filtered(
            lambda precision: precision.digits != PRICE_DIGITS
        ).write({"digits": PRICE_DIGITS})

    def _fiscal_price_precisions(self):
        """Precisiones de precio ("Product Price" y "Foreign Product Price")
        que los documentos fiscales necesitan en 2 decimales."""
        precisions = self.browse()
        for xmlid in FISCAL_PRICE_PRECISIONS:
            precisions |= self.env.ref(xmlid, raise_if_not_found=False) or self.browse()
        return precisions
