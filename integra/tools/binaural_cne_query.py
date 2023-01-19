from odoo.exceptions import MissingError, UserError
from odoo import _
import requests
import logging
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


def get_default_name_by_vat(self, prefix_vat, vat):
    """This function return the name of the person by the vat number and the prefix of the vat number by the CNE website

    Args:
        prefix_vat (string): prefix of the vat number (V)
        vat (string): vat number of the person, this number is unique in Venezuela

    Raises:
        UserError: Error to connect with CNE, please check your internet connection or try again later

    Returns:
        string: name of the person
    """
    URL = (
        "http://www.cne.gov.ve/web/registro_electoral/ce.php?nacionalidad="
        + str(prefix_vat)
        + "&cedula="
        + str(vat)
    )
    try:
        response = requests.get(URL, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        info_table = soup.find_all("tr")
        for row in info_table:
            cne_info = row.find("td")
            for data in cne_info.find_all("b"):
                if not data.find("font"):
                    info = data.text.split(":")
                    if not info[0] == "DATOS DEL ELECTOR":
                        name = info.pop(0)
                        return (name, True)
    except Exception as e:
        _logger.warning(e)
        return ('', False)
