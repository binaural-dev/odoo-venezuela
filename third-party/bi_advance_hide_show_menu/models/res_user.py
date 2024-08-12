# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, tools
from odoo.tools.safe_eval import safe_eval
import operator
import logging
from odoo.http import request
from decorator import decorator
_logger = logging.getLogger(__name__)

def assert_log_admin_access(method):
    """Decorator checking that the calling user is an administrator, and logging the call.

    Raises an AccessDenied error if the user does not have administrator privileges, according
    to `user._is_admin()`.
    """
    def check_and_log(method, self, *args, **kwargs):
        user = self.env.user
        origin = request.httprequest.remote_addr if request else 'n/a'
        log_data = (method.__name__, self.sudo().mapped('name'), user.login, user.id, origin)
        if not self.env.is_admin():
            _logger.warning('DENY access to module.%s on %s to user %s ID #%s via %s', *log_data)
            raise AccessDenied()
        _logger.info('ALLOW access to module.%s on %s to user %s #%s via %s', *log_data)
        return method(self, *args, **kwargs)
    return decorator(check_and_log, method)


class Module(models.Model):
    _inherit = "ir.module.module"

    @assert_log_admin_access
    def button_immediate_install(self):
        """ Installs the selected module(s) immediately and fully,
        returns the next res.config action to execute

        :returns: next res.config item to execute
        :rtype: dict[str, object]
        """
        _logger.info('User #%d triggered module installation', self.env.uid)
        # We use here the request object (which is thread-local) as a kind of
        # "global" env because the env is not usable in the following use case.
        # When installing a Chart of Account, I would like to send the
        # allowed companies to configure it on the correct company.
        # Otherwise, the SUPERUSER won't be aware of that and will try to
        # configure the CoA on his own company, which makes no sense.
        menus_obj = self.env['ir.ui.menu'].search([],order="id desc",limit=1)
        menus_obj.write({'is_write':True})
        if request:
            request.allowed_company_ids = self.env.companies.ids
        return self._button_immediate_function(type(self).button_install)

class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Res Users'

    menu_access_ids= fields.Many2many('ir.ui.menu', string='Groups')
    report_access_ids = fields.Many2many('ir.actions.report', string='Groups')


    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        self.env['ir.ui.menu'].load_menus(debug=1)
        return res

class ResGroups(models.Model):
    _inherit = 'res.groups'
    _description = 'Res Groups'

    menu_ids= fields.Many2many('ir.ui.menu', string='Groups')
    report_ids = fields.Many2many('ir.actions.report', string='Groups')


class IrUiMenu(models.Model):
    _inherit="ir.ui.menu"
    _description = 'Ir Ui Menu'

    is_write = fields.Boolean('Write',default=False)

    @api.model
    @api.returns('self')
    def get_user_roots_menu(self):
        menus_list = []
        res_group = self.env['res.groups'].search([('id','in',self.env.user.groups_id.ids)])
        for menu_group in res_group:
            if menu_group.menu_ids:
                for menu in menu_group.menu_ids:
                    if menu not in menus_list:
                        menus_list.append(menu.id)

        ir_ui_menu = self.search([('id', 'not in', self.env.user.menu_access_ids.ids),('parent_id', '=', False)])

        if len(menus_list)> 0:
            ir_menu = ir_ui_menu.search([('id','not in',menus_list),('parent_id', '=', False)])
            return ir_menu
        return ir_ui_menu

    def write(self, vals):
        res = super(IrUiMenu, self).write(vals)
        request.env['ir.ui.menu'].load_menus(request.session.debug)
        return res

    @api.model
    @tools.ormcache_context('self._uid', 'debug', keys=('lang',))
    def load_menus(self, debug):
        menus_obj = self.env['ir.ui.menu'].sudo().search([],order="id desc",limit=1)
        if menus_obj.is_write == False:
            repo_list = []
            res_user_hide=self.env['ir.ui.menu'].sudo()
            user_hide = res_user_hide.search([('id', 'in', self.env.user.menu_access_ids.ids),('parent_id','=',False)])
            
            group_res=self.env['res.groups'].sudo()
            res_group_menu = group_res.search([('users', 'in', self.env.user.id),('menu_ids', '!=', False)])
            reports_user = False
            reports_group = False
            
            res_user1 = self.env['res.users'].search([('id', '!=', self.env.user.id),('report_access_ids', '!=', False),('parent_id','=',False)])
            for user1 in res_user1:
                reports_user = user1.report_access_ids
                if res_user1:
                    if reports_user:
                        reports_user.create_action()

            res_user = self.env['res.users'].search([('id', '=', self.env.user.id),('report_access_ids', '!=', False),('parent_id','=',False)])
            for user in res_user:
                reports_user = user.report_access_ids
                if res_user:
                    if reports_user:
                        reports_user.unlink_action()

            res_group = self.env['res.groups'].sudo().search([('users', '=', self.env.user.id),('report_ids', '!=', False)])
            res_group1 = self.env['res.groups'].sudo().search([('users', '!=', self.env.user.id),('report_ids', '!=', False)])
            for group in res_group:
                reports_group = group.report_ids
                if res_group:
                    if reports_group:
                        reports_group.unlink_action()
                        
            for group1 in res_group1:
                reports_group1 = group1.report_ids
                if res_group1:
                    if reports_group1:
                        if res_user and res_group:
                            if reports_user:
                                repos = self.env['ir.actions.report'].search([('id', 'not in', reports_user.ids),('id', 'not in', reports_group.ids)])
                                repos.create_action()
                            else:
                                reports_group1.create_action()
                        else:
                            if reports_user:
                                repots = self.env['ir.actions.report'].search([('id', 'not in', reports_user.ids)])
                                repots.create_action()
                            else:
                                reports_group1.create_action()

            ir_act_report = self.env['ir.actions.report'].search([('users_ids', '=', self.env.user.id)])
            ir_act_report1 = self.env['ir.actions.report'].search([('users_ids', '!=', self.env.user.id)])
            if ir_act_report:
                ir_act_report.unlink_action()
            if ir_act_report1:
                if res_user and res_group and ir_act_report:
                    if reports_user or reports_group:
                        report_obj = self.env['ir.actions.report'].search([('id', 'not in', reports_user.ids),('id', 'not in', reports_group.ids),('id', 'not in', ir_act_report.ids)])
                        report_obj.create_action()
                    else:
                        ir_act_report1.create_action()
                elif res_user and res_group:
                    if reports_user or reports_group:
                        reports_group_obj = self.env['ir.actions.report'].search([('id', 'not in', reports_user.ids),('id', 'not in', reports_group.ids)])
                        reports_group_obj.create_action()
                    else:
                        ir_act_report1.create_action()
                else:
                    if reports_user or reports_group or ir_act_report:
                        if reports_group:
                            hide_report = self.env['ir.actions.report'].search([('id', 'not in', reports_group.ids)])
                            hide_report.create_action()
                        if reports_user:
                            hide_report = self.env['ir.actions.report'].search([('id', 'not in', reports_user.ids)])
                            hide_report.create_action()
                        if ir_act_report:
                            hide_report = self.env['ir.actions.report'].search([('id', 'not in', ir_act_report.ids)])
                            hide_report.create_action()

                    else:
                        ir_act_report1.create_action()

            if user_hide: 
                fields = ['name', 'sequence', 'parent_id', 'action', 'web_icon', 'web_icon_data']
                menu_roots = self.get_user_roots_menu()
                menu_roots_data = menu_roots.read(fields) if menu_roots else []
                menu_root = {
                            'id': False,
                            'name': 'root',
                            'parent_id': [-1, ''],
                            'children': [menu['id'] for menu in menu_roots_data],
                        }
                all_menus = {'root': menu_root}

            elif res_group_menu: 
                fields = ['name', 'sequence', 'parent_id', 'action', 'web_icon', 'web_icon_data']
                menu_roots = self.get_user_roots_menu()
                menu_roots_data = menu_roots.read(fields) if menu_roots else []
                menu_root = {
                            'id': False,
                            'name': 'root',
                            'parent_id': [-1, ''],
                            'children': [menu['id'] for menu in menu_roots_data],
                        }
                all_menus = {'root': menu_root}
              
            else:
                fields = ['name', 'sequence', 'parent_id', 'action', 'web_icon', 'web_icon_data']
                menu_roots = self.sudo().get_user_roots()
                menu_roots_data = menu_roots.read(fields) if menu_roots else []
                menu_root = {
                    'id': False,
                    'name': 'root',
                    'parent_id': [-1, ''],
                    'children': [menu['id'] for menu in menu_roots_data],
                }
                all_menus = {'root': menu_root}
                
            if not menu_roots_data:
                return all_menus

            # menus are loaded fully unlike a regular tree view, cause there are a
            # limited number of items (752 when all 6.1 addons are installed)
            child_menus = self.sudo().search([('id', 'child_of', menu_roots.ids)])
            menus=child_menus.search([('id', 'not in', self.env.user.menu_access_ids.ids)])
            if res_group_menu: 
                menu_list = []
                for group_id in res_group_menu:
                    menu_list += group_id.menu_ids.ids
                    menus = child_menus.search([('id','not in', list(set(menu_list))),('id', 'not in', self.env.user.menu_access_ids.ids)])

            menu_items = menus.read(fields)
            xmlids = (menu_roots + menus)._get_menuitems_xmlids()

            # add roots at the end of the sequence, so that they will overwrite
            # equivalent menu items from full menu read when put into id:item
            # mapping, resulting in children being correctly set on the roots.
            menu_items.extend(menu_roots_data)

            # set children ids and xmlids
            menu_items_map = {menu_item["id"]: menu_item for menu_item in menu_items}
            for menu_item in menu_items:
                menu_item.setdefault('children', [])
                parent = menu_item['parent_id'] and menu_item['parent_id'][0]
                menu_item['xmlid'] = xmlids.get(menu_item['id'], "")
                if parent in menu_items_map:
                    menu_items_map[parent].setdefault(
                        'children', []).append(menu_item['id'])
            all_menus.update(menu_items_map)

            # sort by sequence
            for menu_id in all_menus:
                all_menus[menu_id]['children'].sort(key=lambda id: all_menus[id]['sequence'])

                # recursively set app ids to related children
                def _set_app_id(app_id, menu):
                    menu['app_id'] = app_id
                    for child_id in menu['children']:
                        _set_app_id(app_id, all_menus[child_id])

                for app in menu_roots_data:
                    app_id = app['id']
                    _set_app_id(app_id, all_menus[app_id])

                # filter out menus not related to an app (+ keep root menu)
                all_menus = {menu['id']: menu for menu in all_menus.values() if menu.get('app_id')}
                all_menus['root'] = menu_root

                return all_menus
            
        else:
            menus_obj.write({'is_write':False})
            return super(IrUiMenu, self).load_menus(request.session.debug)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

    





    


        

