# from odoo.addons.sh_price_checker_kiosk.controllers.main import HomeCustom
from odoo import http
from odoo.http import request


# class LoginChecker(HomeCustom):
#     @http.route('/login/checker', auth='none', type='http', methods=['GET'], csrf=False)
#     def login_checker(self, **kwargs):
#         login = kwargs.get('login')
#         password = kwargs.get('password')
#         db = kwargs.get('db')
      
#         action_id = request.env.ref('sh_price_checker_kiosk.checker_action_kiosk_mode')
#         menu_id = request.env.ref('sh_price_checker_kiosk.price_checker_sub_menu')
#         redirect = '/web#action='+str(action_id.id)+'&menu_id='+str(menu_id.id)
#         uid = request.session.authenticate(db, login, password)
     
#         return request.redirect(self._login_redirect(uid, redirect=redirect))

class LoginChecker(http.Controller):
    @http.route('/login/checker', auth='none', type='http', methods=['GET'], csrf=False)
    def login_checker(self, **kwargs):
        login = kwargs.get('login')
        password = kwargs.get('password')
        db = kwargs.get('db')
        
        action_id = request.env.ref('sh_price_checker_kiosk.checker_action_kiosk_mode')
        menu_id = request.env.ref('sh_price_checker_kiosk.price_checker_sub_menu')
        redirect = '/web#action='+str(action_id.id)+'&menu_id='+str(menu_id.id)
        uid = request.session.authenticate(db, login, password)
        
        return request.redirect(self._login_redirect(uid, redirect=redirect))
    
    def _login_redirect(self, uid, redirect=None):

        res_users_obj = request.env['res.users']
        if uid:
            search_user = res_users_obj.search([('id','=',uid)],limit=1)
            if search_user and search_user.sh_direct_redirect:
                action_id = request.env.ref('sh_price_checker_kiosk.checker_action_kiosk_mode')
                menu_id = request.env.ref('sh_price_checker_kiosk.price_checker_sub_menu')
                return redirect if redirect else '/web#action='+str(action_id.id)+'&menu_id='+str(menu_id.id)
            else:
                return redirect if redirect else '/web'
            
        return redirect if redirect else '/web'