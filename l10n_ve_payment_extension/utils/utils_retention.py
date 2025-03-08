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
    months = (
        _("January"),
        _("February"),
        _("March"),
        _("April"),
        _("May"),
        _("June"),
        _("July"),
        _("August"),
        _("September"),
        _("October"),
        _("November"),
        _("December"),
    )
    month = months[date.month - 1]
    year = date.year
    message = "{} {}".format(month, year)
    return message
