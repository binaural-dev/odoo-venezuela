# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Import Mass products Lot/Serial Number in Picking-Receipt from Excel File',
    'version': "17.0.1.0.0",
    'category': 'Warehouse',
    'summary': 'import product serial number import product Lot import mass lot number in picking import lot in picking import mass lot in receipt import serial number import serial number in picking import mass serial in picking import multiple product serial in receipt',
    'description': """
                import lot number,
                import serial number,
                import bulk lot number,
                import bulk serial number,
                import lot number for multiple product,
                import serial number for multiple product,
                import lot number for incoming shipment,
                import serial number for incoming shipment,
                import lot number for incoming shipment,
                import serial number for incoming shipment,
 """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.com',
    "price": 34,
    'license': 'OPL-1',
    "currency": 'EUR',
    'depends': ['base','sale','purchase','stock','sale_management','import_lot_serial_no'],
    'data': [
                'security/ir.model.access.csv',
                'data/attachment_sample.xml',
                'views/import_multi_lot_serial_no_view.xml',
            ],
    'demo': [],
    'test': [],
    'installable':True,
    'auto_install':False,
    'application':False,
    "images":["static/description/Banner.gif"],
    'live_test_url':'https://youtu.be/fhwsZ9XM3Zw',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
