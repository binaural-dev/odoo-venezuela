# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import json
import werkzeug
from lxml import etree
from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.base.models.ir_ui_view import NameManager
from odoo.addons.base.models import ir_ui_view

class IrActionReport(models.Model):
    _inherit="ir.actions.report"
    _description = 'Ir Action Report'

    group_ids = fields.Many2many('res.groups', string='Groups')
    users_ids = fields.Many2many('res.users', string='Users')

class FieldConfiguration(models.Model):
    _name = 'field.config'
    _description = 'Field Configuration'

    config_fields_id = fields.Many2one('ir.model', string='Fields')
    fields_id = fields.Many2one('ir.model.fields', string='Field')
    name = fields.Char(string='Technical Name', related='fields_id.name')
    group_ids = fields.Many2many('res.groups', string='Groups')
    readonly = fields.Boolean(string='Readonly')
    invisible = fields.Boolean(string='Invisible')


    def write(self, vals):
        if self.ids:
            self.env['ir.model.access'].call_cache_clearing_methods()
        return super(FieldConfiguration, self).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(FieldConfiguration, self).create(vals_list)
        if res.ids:
            self.env['ir.model.access'].call_cache_clearing_methods()
        return res

    def unlink(self):
        if self.ids:
            self.env['ir.model.access'].call_cache_clearing_methods()
        return super(FieldConfiguration, self).unlink()

class IrModel(models.Model):
    _inherit= "ir.model"
    _description = 'Ir Model'

    field_config_id = fields.One2many('field.config','config_fields_id', string='Field Config')

    
class View(models.Model):
    _inherit = 'ir.ui.view'
    _description = 'View'

    def _postprocess_view(self, node, model_name, editable=True, parent_name_manager=None, **options):
        """ Process the given architecture, modifying it in-place to add and
        remove stuff.

        :param self: the optional view to postprocess
        :param node: the combined architecture as an etree
        :param model_name: the view's reference model name
        :param editable: whether the view is considered editable
        :return: the processed architecture's NameManager
        """
        root = node

        if model_name not in self.env:
            self._raise_view_error(_('Model not found: %(model)s', model=model_name), root)
        model = self.env[model_name]

        if self._onchange_able_view(root):
            self._postprocess_on_change(root, model)

        name_manager = NameManager(model, parent=parent_name_manager)

        root_info = {
            'view_type': root.tag,
            'view_editable': editable and self._editable_node(root, name_manager),
            'view_modifiers_from_model': self._modifiers_from_model(root),
            'mobile': options.get('mobile'),
        }

        # use a stack to recursively traverse the tree
        stack = [(root, editable)]
        while stack:
            node, editable = stack.pop()

            # compute default
            tag = node.tag
            had_parent = node.getparent() is not None
            node_info = dict(root_info, modifiers={}, editable=editable and self._editable_node(node, name_manager))

            # tag-specific postprocessing
            postprocessor = getattr(self, f"_postprocess_tag_{tag}", None)
            if postprocessor is not None:
                postprocessor(node, name_manager, node_info)
                if had_parent and node.getparent() is None:
                    # the node has been removed, stop processing here
                    continue
            models = []

            Models = self.env['ir.model'].search([('field_config_id', '!=',False)])
            for required_model in Models:
                if len(required_model.field_config_id.ids) > 0 :
                    models.append(required_model)
                    

            for Model in models:
                        
                field_name = None
                if node.tag == "field":
                    field_name = node.get("name")
                elif node.tag == "label":
                    field_name = node.get("for")
                if field_name and field_name in Model._fields:
                    field = Model._fields[field_name]
                    if field.groups and not self.user_has_groups(groups=field.groups):
                        node.getparent().remove(node)
                        fields.pop(field_name, None)
                        # no point processing view-level ``groups`` anymore, return
                        return False
                
                  
                # ir_model_obj = self.env['ir.model'].search([('model','=',Model.model)])
                # for i in ir_model_obj:
                if Model.field_config_id:
                    for field_line in Model.field_config_id:
                        if not field_line.group_ids:
                            if field_name == field_line.fields_id.name and model_name == field_line.fields_id.model:
                                if field_line.invisible == True:
                                    node.set('invisible', '1')
                                if field_line.readonly == True:
                                    node.set('readonly', '1')
                        if field_line.group_ids:
                            for group in field_line.group_ids:
                                if group.users:
                                    for user in group.users:
                                        if user.id == self.env.uid:
                                            if field_name == field_line.fields_id.name and model_name == field_line.fields_id.model:
                                                if field_line.invisible == True:
                                                    node.set('invisible', '1') 
                                                if field_line.readonly == True:
                                                    node.set('readonly', '1')   
        
            ir_ui_view.transfer_node_to_modifiers(node, node_info['modifiers'])
            ir_ui_view.transfer_modifiers_to_node(node_info['modifiers'], node)

            # if present, iterate on node_info['children'] instead of node
            for child in reversed(node_info.get('children', node)):
                stack.append((child, node_info['editable']))

        name_manager.update_available_fields()
        root.set('model_access_rights', model._name)

        return name_manager

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
