# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Import Lot/Serial Number in Picking-Receipt and Transfer from Excel File',
    'version': "17.0.1.0.0",
    'category': 'extra tools',
    'summary': 'Apps for import serial number import Lot number import lot number in picking import lot in picking import lot in receipt import serial number import serial number in picking import serial in picking import serial in receipt import lot serial in picking',
    'description': """
	BrowseInfo developed a new odoo/OpenERP module apps.
	This module is useful for odoo import  serial number Lot number with picking from Excel and CSV file .
        Its also useful for odoo import opening stock balance with serial number from XLS or CSV file.
	odoo Import serial number Import lot number inside picking.
	odoo Import product lot number import product serial number import Inventory import from CSV
    odoo import stock import from CSV Inventory adjustment import Opening stock import
    odoo Import warehouse stock Import product stock import Manage Inventory import inventory with lot number import
    odoo import inventory with serial number import inventory adjustment with serial number import inventory adjustment with lot number odoo
    odoo import inventory data import stock data import opening stock with lot number import lot number from excel
    odoo import serial number from excel Import serial number in incoming shipment import lot number in shipment.
    odoo Import lot number in delivery order Import product lot number in delivery import product serial number in delivery note
	odoo delivery serial import from CSV odoo lot import from CS Inventory serial number import serial number import 
    odoo Import lot number stock Import product serial on picking Manage Inventory import shipment with lot number import
    odoo import delivery order with serial number import lot number inside delivery order import serial number inside delivery order import
    odoo import lot number data import serial number data import stock lot number in picking import lot number from excel import serial number from excel.
    import odoo serial number/Lot number with picking from Excel and CSV file .
    import odoo opening stock balance with serial number excel Import serial number.
    odoo excel Import lot number inside picking excel Import product lot number excel import product serial number
    odoo excel Inventory import from CSV excel stock import from CSV excel Inventory adjustment import
    odoo import xls Opening stock import excel serial Import warehouse stock Import product stock excel Manage Inventory xls import inventory with lot number by excel
    odoo import inventory with serial number by excel, import inventory adjustment by xls with serial number import inventory adjustment with lot number by xls import inventory data 
    odoo excel import stock data import opening stock with lot number excel  import lot number from excel import serial number from excel.
    odoo Import serial number in incoming shipment import lot number in shipment.
    odoo Import lot number in delivery order Import product lot number in delivery import product serial number in delivery note
    odoo excel delivery serial import from CSV excel lot import from CSV excel Inventory serial number import serial number excel import odoo excel Import lot number stock excel
    odoo excel Import product serial on picking odoo Manage Inventory import excel shipment with lot number excel import delivery order with serial number xls import lot number inside delivery order 
    odoo xls import serial number inside delivery order xls import lot number data import serial number data excel import stock lot number in picking excel import lot number from xls import serial number from xls.
 """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.com',
    "price": 55,
    "currency": 'EUR',
    'depends': ['base', 'sale', 'purchase', 'stock', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'data/attachment_sample.xml',
        'views/import_lot_serial_no_view.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': False,
    "images": ["static/description/Banner.gif"],
    'live_test_url': 'https://youtu.be/XTJL3in-8rY',
}
