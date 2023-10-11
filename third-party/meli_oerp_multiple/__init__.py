# -*- coding: utf-8 -*-
##############################################################################
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from . import models
from . import controllers
#import wizard
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

from odoo import api, SUPERUSER_ID

def _post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    #env["mercadolibre.orders"]._meli_brand_fix()
