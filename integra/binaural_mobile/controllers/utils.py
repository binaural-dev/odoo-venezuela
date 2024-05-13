import logging

from odoo import _
from odoo.models import IdType
from odoo.http import request
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT

_logger = logging.getLogger(__name__)

def filter_dict(original_dict, keys_to_include):
    """
    Filters the original dictionary to include only the specified keys.

    Args:
        original_dict (dict): The original dictionary.
        keys_to_include (list): List of keys to include in the filtered dictionary.

    Returns:
        dict: A new dictionary containing only the specified keys and their values.
    """
    filtered_dict = {}
    for key in keys_to_include:
        if key in original_dict:
            filtered_dict[key] = original_dict[key]
    return filtered_dict

def create_record(model_name: str, vals: list, is_sudo=True):
    """Creates a registry on the database using the ORM.

    Parameters
    ----------
    model_name
        The model you want to create the registry on.
    vals
        The vals fields for the recordset.
    is_sudo, optional
        If the model creation will be in sudo or not, by default True

    Returns
    -------
        The recordset of the created egistry
    """
    model = request.env[model_name]
    if is_sudo:
        model = request.env[model_name].sudo()

    records = model.create(vals)
    return records


def update_record(model_name: str, idx: int, vals: list, is_sudo=True):
    """Performs an update for a given registry.

    Parameters
    ----------
    model_name
        The model you want to update to.
    idx
        The id of the model registry you want to seach and update
    vals
        The vals fields you want to update in the registry
    is_sudo, optional
        If the model update will be in sudo or not, by default True
    """
    record = browse_model_data(model_name, idx)
    record.write(vals)
    return record


def browse_model_data(model_name: str, ids=None, is_sudo=True):
    """Performs a browse call based in a list of record ids

    Parameters
    ----------
    model_name
        The model records you want to search.
    ids
        The id list to look for.
    is_sudo, optional
        If the model search will be in sudo or not, by default True

    Returns
    -------
        A recordset with the model data.
    """
    if not ids:
        ids = ()
    elif ids.__class__ in IdType:
        ids = (ids,)
    else:
        ids = tuple(ids)
    model = request.env[model_name]
    if is_sudo:
        model = request.env[model_name].sudo()

    records = model.browse(ids)
    return records


def search_model_data(
    model_name: str, domain: list, limit=0, offset=0, order="name desc", **kwargs
):
    is_sudo = kwargs.get("is_sudo", True)
    model = request.env[model_name]
    if is_sudo:
        model = request.env[model_name].sudo()

    records = model.search(domain, limit=limit, offset=offset, order=order)
    return records


def search_name(model_name, name, domain, **kwargs):
    """Get the results of a search by it's name.

    Parameters
    ----------
    model_name
        The ORM model name.
    name
        The name you want to search to.
    domain
        The args as a domain definition to search.
    
    Returns
    -------
        A list of tuples containing the id and the registry
        name.
    """
    
    is_sudo = kwargs.get("is_sudo", True)
    model = request.env[model_name]
    if is_sudo:
        model = request.env[model_name].sudo()

    result_search = model.name_search(name, args=domain)
    return result_search

def get_model_data(
    model_name: str, domain: list, fields: list, limit=0, offset=0, order="name desc", **kwargs
) -> list:
    """Performs a search in the database to obtains records as a
    list of dictionaries.

    Parameters
    ----------
    model_name
        The ORM model name.
    domain
        The search domain.
    fields
        The fields you expect to show in the result
    limit, optional
        limit of registries you want to obtain, by default 1
    offset, optional
        How many jump in the search you want to perform, by default 0
    order, optional
        The order you want to expect the output, by default "name desc"

    Returns
    -------
        A list of dictionaries containing all the data provided by the
        domain.
    """

    is_sudo = kwargs.get("is_sudo", True)
    model = request.env[model_name]
    if is_sudo:
        model = request.env[model_name].sudo()

    records = model.search_read(
        domain=domain, fields=fields, limit=limit, offset=offset, order=order
    )
    return records


def get_model_count(model_name: str, domain: list) -> int:
    """Performs a search and count the quantity of registries obtained

    Parameters
    ----------
    model_name
        The ORM model name.
    domain
        The search domain.

    Returns
    -------
        The quantity of registries obtained by the given domain.
    """

    model_count = request.env[model_name].sudo().search_count(domain)

    return model_count


def check_access(uid: int) -> tuple:
    """Verifies if the user have access to the app.

    Parameters
    ----------
    uid
        The user-employee id.

    Returns
    -------
        A tuple containing True and an empty string if it
        the seller have access, False and a message otherwise.
    """

    if uid:
        domain = [("user_id", "=", uid)]
        employee = search_model_data("hr.employee", domain, limit=1)
        if employee and employee.cannot_access_app:
            return (False, _("You don't have access to this feature."))

    return (True, "")


def get_search_domain(field: str, full_name: str):
    """Create a domain search using similarities in the given client name.
    The name is split in multiple 'str' if there are whitespaces in it.

    Parameters
    ----------
    full_name
        Name to look for.

    Returns
    -------
        A domain that finds the similar names from the given input.
    """
    domain = []
    if full_name:
        domain = [[(field, "ilike", name)] for name in full_name.split(" ")]
    return expression.OR(domain)


def product_duplicate(sale_order: list):
    """Check if there are duplicates products sent
    to the order lines.

    Parameters
    ----------
    sale_order
        THe dictionary containing the sale order data.

    Returns
    -------
        True if the products are duplicated, False otherwise.
    """

    order_lines = sale_order.get("order_line", False)
    product_list = [line.get("product_id") for line in order_lines if line.get("product_id", False)]
    product_set = set(product_list)
    return len(product_list) > len(product_set)


def get_order_line(sale_order: list, fields: list):
    """Get the order lines from the sale_order data.

    Parameters
    ----------
    sale_order
        All the information from the sale order.
    fields
        The fields you expect to get from the order.

    Returns
    -------
        All the order_line data.
    """

    sale_orders = []
    for order in sale_order:
        order_line = order.get("order_line", [])
        if order_line:
            domain = [("id", "in", order_line),('display_type', '=', False)]
            order_cpy = order.copy()
            line = get_model_data("sale.order.line", domain, fields)
            order_cpy.update({"order_line": line})
            if request.env.company.mobile_show_tax_type == "include_tax":
                for line in order_cpy["order_line"]:
                    line["price_unit"] = line["price_unit_with_tax"]
                    line["price_subtotal"] = line["price_total"]
            sale_orders.append(order_cpy)

    return sale_orders or sale_order

def set_order_line(sale_order: list, tax_included: bool):
    order_lines = sale_order.get("order_line", [])
    lines = []
    company_id = request.env.user.company_id.id
    domain = [
        ("active", "=", True),
        ("company_id", "=", company_id),
        ("type_tax_use", "=", "sale"),
        ("amount", "=", 0.0000),
    ]

    tax_id = search_model_data("account.tax", domain, 1).id

    for line in order_lines:
        line_cpy = line.copy()
        product_id = False

        product_id = line_cpy.get("product_id")

        if type(product_id) is tuple:
            product_id = product_id[0]

        product_id = int(product_id) if type(product_id) is str else product_id

        if tax_included or request.env.company.mobile_tax_include:
            product_taxes_id = browse_model_data("product.product", product_id).taxes_id

            if any(product_taxes_id):
                tax_id = product_taxes_id[0].id

        if line_cpy.get("id", False):
            lines.append(
                (
                    1,
                    line_cpy.get("id"),
                    {
                        "product_id": product_id,
                        "product_uom_qty": line_cpy.get("product_uom_qty"),
                        "tax_id": [(6, 0, [tax_id])],
                    },
                )
            )

            continue

        lines.append(
            (
                0,
                0,
                {
                    "product_id": product_id,
                    "product_uom_qty": line_cpy.get("product_uom_qty"),
                    "tax_id": [(4, tax_id, 0)],
                },
            )
        )

    return lines


def convert_field_string(data: dict, fields: list):
    res = []
    for element in data:
        element_cpy = element.copy()
        element_cpy.update({key: str(element.get(key, False)) for key in fields})
        res.append(element_cpy)

    return res


def get_config(keyword: str, is_sudo=True):
    config = request.env["ir.config_parameter"]
    if is_sudo:
        config = request.env["ir.config_parameter"].sudo()

    res = config.get_param(keyword)
    return res


def get_foreign_currency_rate(foreign_currency_id: int, foreign_currency_date):

    rate = request.env["res.currency.rate"].search(
        [("currency_id", "=", foreign_currency_id), ("name", "<=", foreign_currency_date)],
        limit=1,
        order="name desc",
    )
    if rate:
        return rate.rate if rate.currency_id.name == "VEF" else rate.vef_rate

    rate = request.env["res.currency.rate"].search(
        [("currency_id", "=", foreign_currency_id), ("name", ">=", foreign_currency_date)],
        limit=1,
        order="name asc",
    )
    if rate:
        return rate.rate if rate.currency_id.name == "VEF" else rate.vef_rate

    return 0.00


class ValidateRequest:
    @staticmethod
    def require(fields, kwargs, parent_field=False):
        errors = []
        error_msg = _("Is required")

        if parent_field:
            kwargs = kwargs.get(parent_field)

            if not kwargs:
                return [parent_field, error_msg]

        for field in fields:
            key = field[0]

            if len(field) == 2:
                error_msg = field[1]

            if key not in kwargs.keys():
                errors.append([key, error_msg])

        if len(errors) > 0 and parent_field:
            errors = [parent_field, errors]

        return errors

    @staticmethod
    def json(validation_errors):
        if any(validation_errors):
            return {"status": 400, "msg:": str(validation_errors)}

        return False
