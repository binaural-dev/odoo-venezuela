##############################################################################
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'MercadoLibre Stock Management Extension / Mercado Libre Publisher Extension',
    'summary': 'MercadoLibre Stock Management Extension / Mercado Libre Publisher Extension',
    'version': "17.0.1.0.0",
    'author': 'Moldeo Interactive',
    'website': 'https://www.moldeointeractive.com',
    "category": "Sales",
    "depends": ['base', 'product','sale_management','meli_oerp', 'stock','delivery'],
    'data': [
        'views/company_view.xml',
        'views/stock_view.xml',
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
    ],
    'demo': [
    ],
    'price': '50.00',
    'currency': 'USD',
    "external_dependencies": {"python": ['pdf2image','meli']},
    'images': [ 'static/description/main_screenshot.png',
                'static/description/meli_oerp_stock_configuration.png',
                'static/description/meli_oerp_stock_installation.png',
                'static/description/moldeo_interactive_logo.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'GPL-3',
}
