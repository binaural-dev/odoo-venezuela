import logging
import json
import requests
from requests import HTTPError

_logger = logging.getLogger(__name__)


def test_logger():
    """
    Request to logger Iot
    """
    _data = {"value": "data"}
    return _send_post(
        iot_ip="10.18.1.130", port="8069", url="hw_proxy/default_fiscal_action", data=_data
    )

def mf_print_report_z(_ip="", _port="8069",data=None):
    return _send_post(iot_ip=_ip, port=_port, url="hw_proxy/report_z", timeout=(5,20), data=data)

def _rpc(data):
    return {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"data": json.dumps(data)},
    }


def _send_post(iot_ip="", port="8069", url="",timeout=(5,10), **kw):
    try:
        response = requests.post(
            f"http://{iot_ip}:{port}/{url}",
            timeout=timeout,
            json=_rpc(kw["data"]),
        )
        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        _logger.warning(f"HTTP error occurred: {http_err}")  # Python 3.6
    except Exception as err:
        _logger.warning(f"Other error occurred: {err}")  # Python 3.6
    else:
        return response.json()["result"]
