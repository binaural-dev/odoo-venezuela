##############################################################################
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'MercadoLibre Multiple Accounts / Mercado Libre Publisher Extension',
    'version': "17.0.1.0.0",
    'author': 'Moldeo Interactive',
    'website': 'https://www.moldeointeractive.com',
    "category": "Sales",
    "depends": ['base', 'product','sale_management','website_sale','stock','odoo_connector_api','meli_oerp','meli_oerp_stock','meli_oerp_accounting'],
    'data': [
        'security/odoo_connector_api_security.xml',
        'security/ir.model.access.csv',
        'views/wizards_view.xml',
        'views/company_view.xml',
        'views/connection_account_view.xml',
    	#'views/posting_view.xml',
        #'views/product_post.xml',
        'views/connection_view.xml',
        'views/notification_view.xml',
        'views/product_view.xml',
        'views/sale_view.xml',
        'data/data.xml',
        'data/cron_jobs.xml',
    	#'views/category_view.xml',
    	#'views/banner_view.xml',
        'views/warning_view.xml',
        'views/questions_view.xml',
        #'data/cron_jobs.xml',
        #'data/error_template_data.xml',
        #'data/parameters_data.xml',
	    #'report/report_shipment_view.xml',
        #'report/report_invoice_shipment_view.xml',
	    #'views/shipment_view.xml',
	    #'views/notifications_view.xml'
    ],
    'price': '350.00',
    'currency': 'USD',
    "external_dependencies": {"python": ['pdf2image','meli']},
    'images': [ 'static/description/main_screenshot.png',
                'static/description/meli_oerp_screenshot.png',
                'static/description/meli_oerp_configuration_1.png',
                'static/description/meli_oerp_configuration_2.png',
                'static/description/meli_oerp_configuration_3.png',
                'static/description/meli_oerp_configuration_4.png',
                'static/description/moldeo_interactive_logo.png',
                'static/description/meli_oerp_multiple_configuration_1.png',
                'static/description/meli_oerp_multiple_configuration_2.png',
                'static/description/meli_oerp_multiple_configuration_3.png',
                'static/description/odoo_to_meli.png'],
    'assets': {
        'web.assets_backend': [
            '/meli_oerp_multiple/static/src/css/meli_oerp_multiple.css',
        ]
    },
    'demo_xml': [],
    'active': False,
    'installable': True,
    'application': True,
    'license': 'GPL-3'
}
