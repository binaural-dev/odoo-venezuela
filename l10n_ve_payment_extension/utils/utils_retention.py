from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError


def search_invoices_with_taxes(AccountMove, domain):
    """
    Search for invoices with taxes for the given domain.

    Params
    ------
    AccountMove: account.move recordset
        AccountMove model.
    domain: list
        Domain to search for invoices.

    Returns
    -------
    account.move
        Invoices with taxes different than 0.
    """
    invoices = AccountMove.search(domain)
    return invoices.filtered(
        lambda i: any(line.tax_ids[0].amount > 0 for line in i.line_ids if line.tax_ids)
    )


def load_retention_lines(invoices, Retention):
    """
    Load retention lines for the given invoices.

    Params
    ------
    invoices: account.move recordset
        Invoices to load retention lines.
    Retention: account.retention recordset
        Retention model.

    Returns
    -------
    account.retention
        Retention lines.
    """
    retention_lines_data = [Retention.compute_retention_lines_data(i) for i in invoices]
    return [Command.create(line) for lines in retention_lines_data for line in lines]


def get_current_date_format(date):
    """
    Computes a date format consisting of the name of the month plus the year.

    Returns
    -------
    string
        The month and the year on the desired format.
    """
    # 1. Definimos los meses de forma limpia (sin el _() aquí para evitar problemas de contexto)
    months = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    )
    
    # 2. Obtenemos el mes en inglés
    month_name = months[date.month - 1]
    
    # 3. Traducimos el mes individualmente usando el contexto de Odoo
    translated_month = _(month_name)
    year = date.year
    
    # 4. RECOMENDADO: Traducir la estructura completa para permitir variaciones de idioma
    # Esto permite que en español se traduzca como "%s de %s" (Enero de 2026) si fuera necesario.
    return _("%(month)s %(year)s", month=translated_month, year=year)
