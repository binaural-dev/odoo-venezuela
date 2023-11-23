from odoo import _, api, exceptions, fields, models
from odoo.tools import float_is_zero
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError

class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing.abstract"
    _name = "account.fiscalyear.closing"
    _description = "Fiscal year closing"

    def _default_year(self):
        company = self._default_company_id()
        """lock_date = company.fiscalyear_lock_date or fields.Date.today()
        fiscalyear = lock_date.year
        if lock_date.month < company.fiscalyear_last_month and \
                lock_date.day < company.fiscalyear_last_day:
            fiscalyear = fiscalyear - 1"""
        fiscalyear = datetime.now().year
        month = datetime.now().month
        day = datetime.now().day
        _logger.info("month %s",month)
        _logger.info("company.fiscalyear_last_month %s",company.fiscalyear_last_month)
        if int(month) < int(company.fiscalyear_last_month) and \
                int(day) < int(company.fiscalyear_last_day):
            fiscalyear = fiscalyear - 1
        return fiscalyear

    def _default_company_id(self):
        return self.env['res.company']._company_default_get(
            'account.fiscalyear.closing'
        )
    
    name = fields.Char(
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    check_draft_moves = fields.Boolean(
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    year = fields.Integer(
        help="Introduce here the year to close. If the fiscal year is between "
             "several natural years, you have to put here the last one.",
        default=lambda self: self._default_year(),
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    company_id = fields.Many2one(
        default=lambda self: self._default_company_id(),
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    chart_template_id = fields.Many2one(
        # "account.chart.template", 
        related="company_id.chart_template_id",
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('calculated', 'Calculed'),
            ('posted', 'Posted'),
            ('cancelled', 'Cancelled'),
        ],
        string="State",
        readonly=True,
        default='draft',
    )
    calculation_date = fields.Datetime(
        readonly=True,
    )
    date_start = fields.Date(
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    date_end = fields.Date(
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    date_opening = fields.Date(
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    #domain="[('chart_template_ids', '=', chart_template_id)]",
    closing_template_id = fields.Many2one(
        "account.fiscalyear.closing.template",
        
        readonly=True,
        states={'draft': [('readonly', False)]},
        oldname='template_id',
    )
    stored_template_id = fields.Many2one(
        "account.fiscalyear.closing.template",
        readonly=True,
    )
    is_new_template = fields.Boolean(
        compute="_compute_is_new_template",
    )
    move_config_ids = fields.One2many(
        'account.fiscalyear.closing.config',
        'fyc_id',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    move_ids = fields.One2many(
        'account.move','fyc_id', readonly=True,
    )

    # jounals_type_bin
    journals_filter = fields.Selection([
        ('fiscal', 'Dairy Fiscal'),
        ('nofiscal', 'Dairy No Fiscal'),
        ('all', 'All dairys'),
    ], default='all')

    _sql_constraints = [
        ('year_company_uniq', 'unique(year, company_id,jounals_type_bin)',
         _('There should be only one fiscal year closing for that year and '
           'company!')),
    ]

    #@api.multi
    # @api.depends('closing_template_id', 'stored_template_id')
    # def _compute_is_new_template(self):
    #     for record in self:
    #         # It should be with .id suffix for avoiding problems with NewId
    #         record.is_new_template = (
    #             record.closing_template_id.id != record.stored_template_id.id
    #         )

    # #@api.multi
    # def _prepare_mapping(self, tmpl_mapping):
    #     self.ensure_one()
    #     dest_account = False
    #     # Find the destination account
    #     name = tmpl_mapping.name
    #     if tmpl_mapping.dest_account:
    #         dest_account = self.env['account.account'].search([
    #             ('company_id', '=', self.company_id.id),
    #             ('code', '=ilike', tmpl_mapping.dest_account),
    #         ], limit=1)
    #         # Use an error name if no destination account found
    #         if not dest_account:
    #             name = _("Sin cuenta de destino '%s' encontrada.") % (
    #                 tmpl_mapping.dest_account,
    #             )
    #     return {
    #         'name': name,
    #         'src_accounts': tmpl_mapping.src_accounts,
    #         'dest_account_id': dest_account,
    #     }

    # @api.model
    # def _prepare_type(self, tmpl_type):
    #     return {
    #         'account_type_id': tmpl_type.account_type_id,
    #         'closing_type': tmpl_type.closing_type,
    #     }

    # def _get_default_journal(self, company):
    #     """To be inherited if we want to change the default journal."""
    #     journal_obj = self.env['account.journal']
    #     domain = [('company_id', '=', company.id)]
    #     journal = journal_obj.search(
    #         domain + [('code', '=', 'MISC')], limit=1,
    #     )
    #     if not journal:
    #         journal = journal_obj.search(
    #             domain + [('type', '=', 'general')], limit=1,
    #         )
    #     return journal

    # #@api.multi
    # def _prepare_config(self, tmpl_config):
    #     self.ensure_one()
    #     mappings = self.env['account.fiscalyear.closing.mapping']
    #     for m in tmpl_config.mapping_ids:
    #         mappings += mappings.new(self._prepare_mapping(m))
    #     types = self.env['account.fiscalyear.closing.type']
    #     for t in tmpl_config.closing_type_ids:
    #         types += types.new(self._prepare_type(t))
    #     if tmpl_config.move_date == 'last_ending':
    #         date = self.date_end
    #     else:
    #         date = self.date_opening
    #     return {
    #         'enabled': True,
    #         'name': tmpl_config.name,
    #         'sequence': tmpl_config.sequence,
    #         'code': tmpl_config.code,
    #         'inverse': tmpl_config.inverse,
    #         'move_type': tmpl_config.move_type,
    #         'date': date,
    #         'journal_id': (
    #             tmpl_config.journal_id or self._get_default_journal(
    #                 self.company_id
    #             ).id
    #         ),
    #         'mapping_ids': mappings,
    #         'closing_type_ids': types,
    #         'closing_type_default': tmpl_config.closing_type_default,
    #     }

    # # @api.onchange('closing_template_id')
    # # Not working due to https://github.com/odoo/odoo/issues/20163
    # # Using instead `action_load_template`
    # def onchange_template_id(self):
    #     self.move_config_ids = False
    #     if not self.closing_template_id:
    #         return
    #     config_obj = self.env['account.fiscalyear.closing.config']
    #     tmpl = self.closing_template_id.with_context(
    #         force_company=self.company_id.id
    #     )
    #     self.check_draft_moves = tmpl.check_draft_moves
    #     for tmpl_config in tmpl.move_config_ids:
    #         self.move_config_ids += config_obj.new(
    #             self._prepare_config(tmpl_config)
    #         )

    # @api.onchange('year')
    # def _onchange_year(self):
    #     self.date_end = '%s-%s-%s' % (
    #         self.year,
    #         str(self.company_id.fiscalyear_last_month).zfill(2) or '12',
    #         str(self.company_id.fiscalyear_last_day).zfill(2) or '31',
    #     )
    #     date_end = fields.Date.from_string(self.date_end)
    #     self.date_start = fields.Date.to_string(
    #         date_end - relativedelta(years=1) + relativedelta(days=1)
    #     )
    #     self.date_opening = fields.Date.to_string(
    #         date_end + relativedelta(days=1)
    #     )
    #     if self.date_start != self.date_end:
    #         self.name = "%s-%s" % (self.date_start, self.date_end)
    #     else:
    #         self.name = str(self.date_end)

    # #@api.multi
    # def action_load_template(self):
    #     self.ensure_one()
    #     config_obj = self.env['account.fiscalyear.closing.config']
    #     move_configs = config_obj
    #     tmpl = self.closing_template_id.with_context(
    #         force_company=self.company_id.id
    #     )
    #     if tmpl:
    #         for tmpl_config in tmpl.move_config_ids:
    #             move_configs += config_obj.new(
    #                 self._prepare_config(tmpl_config)
    #             )
    #     self.write({
    #         'check_draft_moves': tmpl.check_draft_moves,
    #         'stored_template_id': tmpl.id,
    #         'move_config_ids': [(5, )] + [
    #             (0, 0, x._convert_to_write(x._cache)) for x in move_configs
    #         ],
    #     })

    # #@api.multi
    # def draft_moves_check(self):
    #     for closing in self:
    #         _logger.info("CHECK DRAFT %s",closing.jounals_type_bin)
    #         if closing.jounals_type_bin == 'fiscal':
    #             draft_moves = self.env['account.move'].search([
    #                 ('company_id', '=', closing.company_id.id),
    #                 ('state', '=', 'draft'),
    #                 ('date', '>=', closing.date_start),
    #                 ('date', '<=', closing.date_end),
    #                 ('journal_id.fiscal', '=', True),
    #             ])
    #         elif closing.jounals_type_bin == 'nofiscal':
    #             draft_moves = self.env['account.move'].search([
    #                 ('company_id', '=', closing.company_id.id),
    #                 ('state', '=', 'draft'),
    #                 ('date', '>=', closing.date_start),
    #                 ('date', '<=', closing.date_end),
    #                 ('journal_id.fiscal', '=', False),
    #             ])
    #         else:
    #             draft_moves = self.env['account.move'].search([
    #                 ('company_id', '=', closing.company_id.id),
    #                 ('state', '=', 'draft'),
    #                 ('date', '>=', closing.date_start),
    #                 ('date', '<=', closing.date_end),
    #             ])
    #         if draft_moves:
    #             msg = _('Se encontraron uno o más movimientos sin asentar: \n')
    #             for move in draft_moves:
    #                 msg += ('ID: %s, Date: %s, Number: %s, Ref: %s\n' %
    #                         (move.id, move.date, move.name, move.ref))
    #             raise ValidationError(msg)
    #     return True

    # def _show_unbalanced_move_wizard(self, data):
    #     """When a move is not balanced, a wizard is presented for checking the
    #     possible problem. This method fills the records and return the
    #     corresponding action for showing that wizard.

    #     :param data: Dictionary with the values of the unbalanced move.
    #     :return: Dictionary with the action for showing the wizard.
    #     """
    #     del data['closing_type']
    #     del data['fyc_id']
    #     wizard = self.env['account.fiscalyear.closing.unbalanced.move'].create(
    #         data
    #     )
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('Unbalanced journal entry found'),
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'account.fiscalyear.closing.unbalanced.move',
    #         'res_id': wizard.id,
    #         'target': 'new',
    #     }

    # #@api.multi
    # def calculate(self):
    #     for closing in self:
    #         # Perform checks, raise exception if check fails
    #         if closing.check_draft_moves:
    #             closing.draft_moves_check()
    #         for config in closing.move_config_ids.filtered('enabled'):
    #             move, data = config.moves_create()
    #             if not move and data:
    #                 # The move can't be created
    #                 return self._show_unbalanced_move_wizard(data)
    #     return True

    # #@api.multi
    # def _moves_remove(self):
    #     for closing in self:
    #         closing.mapped('move_ids.line_ids').filtered('reconciled').\
    #             remove_move_reconcile()
    #         closing.move_ids.button_cancel()
    #         closing.move_ids.unlink()
    #     return True

    # #@api.multi
    # def button_calculate(self):
    #     res = self.calculate()
    #     if res is True:
    #         # Change state only on successful creation
    #         self.write({
    #             'state': 'calculated',
    #             'calculation_date': fields.Datetime.now(),
    #         })
    #     else:
    #         # Remove intermediate moves already created
    #         self._moves_remove()
    #     return res

    # #@api.multi
    # def button_recalculate(self):
    #     self._moves_remove()
    #     return self.button_calculate()

    # #@api.multi
    # def button_post(self):
    #     # Post moves
    #     #for closing in self:
    #         #for move_config in closing.move_config_ids.sorted('sequence'):
    #         #    move_config.move_id.post()
    #     moves = self.env['account.move'].sudo().search([('fyc_id', 'in', self.ids),('state','=','draft')])
    #     for m in moves:
    #         m.post()
    #     self.write({'state': 'posted'})
    #     return True

    # #@api.multi
    # def button_open_moves(self):
    #     # Return an action for showing moves
    #     return {
    #         'name': _('Fiscal closing moves'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'tree,form',
    #         'res_model': 'account.move',
    #         'domain': [('fyc_id', 'in', self.ids)],
    #     }

    # #@api.multi
    # def button_open_move_lines(self):
    #     return {
    #         'name': _('Fiscal closing move lines'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'tree,form',
    #         'res_model': 'account.move.line',
    #         'domain': [('move_id.fyc_id', 'in', self.ids)],
    #     }

    # #@api.multi
    # def button_cancel(self):
    #     self._moves_remove()
    #     self.write({'state': 'cancelled'})
    #     return True

    # #@api.multi
    # def button_recover(self):
    #     self.write({
    #         'state': 'draft',
    #         'calculation_date': False,
    #     })
    #     return True

    # #@api.multi
    # def unlink(self):
    #     if any(x.state not in ('draft', 'cancelled') for x in self):
    #         raise exceptions.UserError(
    #             _("No puede eliminar ningún cierre que no esté en borrador o "
    #               "cancelado.")
    #         )
    #     return super(AccountFiscalyearClosing, self).unlink()


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config.abstract"
    _name = "account.fiscalyear.closing.config"
    _order = "sequence asc, id asc"



    @api.onchange('l_map')
    def inchange_l_map(self):
        #if not self.journal_id:
        #    raise UserError("Seleccione un diario")
        print("buscar las cuentas y ponerlas en fiscal closing==================================================================")
        ingreso = self.env.ref('account.data_account_type_revenue').id
        gasto = self.env.ref('account.data_account_type_expenses').id
        #costo = self.env.ref('accounting_pdf_reports.data_account_type_direct_costs_cost').id

        #('company_id','=',self.journal_id.company_id.id),
        #('company_id','=',self.journal_id.company_id.id),

        ganancia = self.env.ref('account.data_unaffected_earnings').id
        accounts = self.env['account.account'].sudo().search([('user_type_id','in',[gasto,ingreso])])

        config_a = self.env['account.account'].sudo().search([('user_type_id','=',ganancia)],limit=1)#esta es la de destino siempre es la misma preguntar cual es
        maps = []
        cont = 1
        account_len = int(self.env['ir.config_parameter'].sudo().get_param('account_longitude_report'))
        if not account_len:
            raise exceptions.UserError("Por favor configure la longitud de las cuentas contables.")
        if self.l_map:
            #sync
            _logger.info("accounts %s",accounts)
            for a in accounts:
                if len(a.code) == account_len:
                    vals = {'name':a.name,'src_accounts':a.code,'dest_account_id':config_a.id,'fyc_config_id':self.id}
                    cont +=1
                    print("vals**************",vals)
                    maps.append((0, 0, vals))
            if len(maps) > 0:
                #self.update({'mapping_ids':maps})
                return {'value':{'mapping_ids':maps}}
        else:
            return {'value':{'mapping_ids':[(5, 0, 0)]}}

    fyc_id = fields.Many2one(
        comodel_name='account.fiscalyear.closing', index=True, readonly=True,
        string="Cierre del año fiscal", required=True, ondelete='cascade',
    )

    l_map = fields.Boolean(string='Cargar Cuentas')

    mapping_ids = fields.One2many(
        comodel_name='account.fiscalyear.closing.mapping',
        inverse_name='fyc_config_id', string="Asignaciones de cuentas",
    )
    closing_type_ids = fields.One2many(
        comodel_name='account.fiscalyear.closing.type',
        inverse_name='fyc_config_id', string="Tipos de cierre",
    )
    date = fields.Date(string="Fecha de asiento")
    enabled = fields.Boolean(string="Activado", default=True)
    journal_id = fields.Many2one(required=True)
    move_id = fields.Many2one(comodel_name="account.move", string="Asiento")

    _sql_constraints = [
        ('code_uniq', 'unique(code, fyc_id)',
         _('El código debe ser único por cierre de año fiscal!')),
    ]

    #@api.multi
    def config_inverse_get(self):
        configs = self.env['account.fiscalyear.closing.config']
        for config in self:
            code = config.inverse and config.inverse.strip()
            if code:
                configs |= self.search([
                    ('fyc_id', '=', config.fyc_id.id),
                    ('code', '=', code),
                ])
        return configs

    #@api.multi
    def closing_type_get(self, account):
        self.ensure_one()
        closing_type = self.closing_type_default
        closing_types = self.closing_type_ids.filtered(
            lambda r: r.account_type_id == account.user_type_id)
        if closing_types:
            closing_type = closing_types[0].closing_type
        return closing_type

    #@api.multi
    def move_prepare(self, move_lines,rate=0):
        self.ensure_one()
        description = self.name
        journal_id = self.journal_id.id
        return {
            'ref': description,
            'date': self.date,
            'fyc_id': self.fyc_id.id,
            'closing_type': self.move_type,
            'journal_id': journal_id,
            'line_ids': [(0, 0, m) for m in move_lines],
            'foreign_currency_rate':rate,
        }

    def _mapping_move_lines_get(self,src,account_map):
        move_lines = []
        dest_totals = {}
        # Add balance/unreconciled move lines
        #for account_map in self.mapping_ids:
        rate = 1
        
        dest = account_map.dest_account_id
        dest_totals.setdefault(dest, 0)
        #aqui filtrar si viene src usar solo esa
        if not src:
            src_accounts = self.env['account.account'].search([
                ('company_id', '=', self.fyc_id.company_id.id),
                ('code', '=ilike', account_map.src_accounts),
            ], order="code ASC")
        else:
            src_accounts = self.env['account.account'].sudo().search([('code','=ilike',src)])
        #_logger.info("CANTIDAD DE src_accounts %s",len(src_accounts))
        for account in src_accounts:
            closing_type = self.closing_type_get(account)
            balance = False
            if closing_type == 'balance':
                # Get all lines
                lines = account_map.account_lines_get(account,self.fyc_id.jounals_type_bin)
               
                balance, move_line,rate = account_map.move_line_prepare(
                    account, lines
                )
                if move_line:
                    move_lines.append(move_line)
            elif closing_type == 'unreconciled':
                # Get credit and debit grouping by partner
                """partners = account_map.account_partners_get(account)
                for partner in partners:
                    balance, move_line = account_map.\
                        move_line_partner_prepare(account, partner)
                    if move_line:
                        move_lines.append(move_line)"""
                continue
            else:
                # Account type has unsupported closing method
                continue
            if dest and balance:
                dest_totals[dest] -= balance
        # Add destination move lines, if any
        for account_map in self.mapping_ids.filtered('dest_account_id'):
            dest = account_map.dest_account_id
            balance = dest_totals.get(dest, 0)
            if not balance:
                continue
            dest_totals[dest] = 0
            move_line = account_map.dest_move_line_prepare(dest, balance)
            if move_line:
                move_lines.append(move_line)
        return move_lines,rate

    #@api.multi
    def inverse_move_prepare(self):
        self.ensure_one()
        move_ids = False
        date = self.fyc_id.date_end
        if self.move_type == 'opening':
            date = self.fyc_id.date_opening
        config = self.config_inverse_get()
        if config.move_id:
            move_ids = config.move_id.reverse_moves(
                date=date, journal_id=self.journal_id,
            )
        return move_ids

    #@api.multi
    def moves_create(self):
        self.ensure_one()
        moves = self.env['account.move']
        # Prepare one move per configuration
        data = False

        rate = 1
        _logger.info("funcion moves_create self.mapping_ids.filtered('dest_account_id') %s",self.mapping_ids)
        #raise UserError("T")
        for ac in self.mapping_ids:
            #_logger.info("src_accountssrc_accounts------------------------------------------------------ %s",ac.src_accounts)
            #for c in ac.src_accounts:
            data = False
            if self.mapping_ids:
                move_lines,rate = self._mapping_move_lines_get(ac.src_accounts,ac)
                if len(move_lines)>0:
                    data = self.move_prepare(move_lines,rate)
            elif self.inverse:
                #alerta: el move_id es un many2one
                move_ids = self.inverse_move_prepare()
                move = moves.browse(move_ids[0])
                move.write({'ref': self.name, 'closing_type': self.move_type})
                self.move_id = move.id
                return move, data
            # Create move
            if not data:
                continue
                #return False, data
            total_debit = sum([x[2]['debit'] for x in data['line_ids']])
            total_credit = sum([x[2]['credit'] for x in data['line_ids']])

            dif = total_credit - total_debit

            if dif != 0:
                other_dest = False
                for line in data['line_ids']:
                    if len(line)>=2:
                        if line[2]['name'] in ['Resultado','Result']:
                            other_dest = {
                                'account_id':line[2]['account_id'],
                                'name':'Ajuste por precisión decimal',
                                'date':line[2]['date'],
                                'debit': abs(dif) if dif > 0 else False,
                                'credit': abs(dif) if dif < 0 else False,
                            }
                if other_dest:
                    data['line_ids'].append((0,0,other_dest))
            #el modulo valida pero con 2 decimales mientras que odoo manda las lineas con muchos decimales
            total_debit = sum([x[2]['debit'] for x in data['line_ids']])
            total_credit = sum([x[2]['credit'] for x in data['line_ids']])

            if abs(round(total_credit - total_debit, 2)) >= 0.01:
                # the move is not balanced
                return False, data
            move = moves.with_context(journal_id=self.journal_id.id).create(data)
            #self.move_id = move.id
            #este move_id debe ser para el inversal, duda
            if move:
                move._onchange_rate()
        return move, data


class AccountFiscalyearClosingMapping(models.Model):
    _inherit = "account.fiscalyear.closing.mapping.abstract"
    _name = "account.fiscalyear.closing.mapping"
    #aqui
    fyc_config_id = fields.Many2one(
        comodel_name='account.fiscalyear.closing.config', index=True,
        string="Configuración de cierre del año fiscal", readonly=False, required=True,
        ondelete='cascade',
    )
    src_accounts = fields.Char(
        string="Cuenta de origen", required=True,
    )
    dest_account_id = fields.Many2one(
        comodel_name='account.account', string="Cuenta de destino",
    )

    #@api.multi
    def dest_move_line_prepare(self, dest, balance, partner_id=False):
        self.ensure_one()
        move_line = {}
        precision = self.env['decimal.precision'].precision_get('Account')
        #_logger.info("precisionprecisionprecisionprecisionprecision =========> %s",precision)
        precision = 12
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == 'opening':
            date = self.fyc_config_id.fyc_id.date_opening
        if not float_is_zero(balance, precision_digits=precision):
            move_line = {
                'account_id': dest.id,
                'debit': balance < 0 and -balance,
                'credit': balance > 0 and balance,
                'name': _('Result'),
                'date': date,
                'partner_id': partner_id,
            }
        return move_line

    #@api.multi
    def move_line_prepare(self, account, account_lines, partner_id=False):
        self.ensure_one()
        move_line = {}
        balance = 0
        precision = self.env['decimal.precision'].precision_get('Account')
        precision = 12
        description = self.name or account.name
        date = self.fyc_config_id.fyc_id.date_end
        rate = 1
        if self.fyc_config_id.move_type == 'opening':
            date = self.fyc_config_id.fyc_id.date_opening
        if account_lines:
            _logger.info("CODIGO --------------- %s",account.code)
            _logger.info("CUENTA ------------- %s",account.name)
            d = sum(account_lines.mapped('debit'))
            c = sum(account_lines.mapped('credit'))
            _logger.info("Debit SUM %s",d)
            _logger.info("CREDIT SUM %s",c)
            balance = (
                sum(account_lines.mapped('debit')) -
                sum(account_lines.mapped('credit')))
            all_deb = all_cred = balance_bs = 0 
          
            for al in account_lines:
                all_deb += al.debit * al.foreign_currency_rate
                all_cred += al.credit * al.foreign_currency_rate
            _logger.info("ALL DEB %s",all_deb)
            _logger.info("ALL CRED %s",all_cred)
            balance_bs = all_deb - all_cred

            
            if not float_is_zero(balance, precision_digits=precision):
                rate = round(balance_bs/balance,2)
                move_line = {
                    'account_id': account.id,
                    'debit': balance < 0 and -balance,
                    'credit': balance > 0 and balance,
                    'name': description,
                    'date': date,
                    'partner_id': partner_id,
                }
            else:
                balance = 0
        _logger.info("RATE %s",rate)
        return balance, move_line,abs(rate)

    #@api.multi
    def account_lines_get(self, account,j_type):
        _logger.info("buscar account move line por diario tipo: %s",j_type)
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        if j_type == 'fiscal':
            return self.env['account.move.line'].search([
                ('company_id', '=', company_id),
                ('account_id', '=', account.id),
                ('date', '>=', start),
                ('date', '<=', end),
                ('move_id.journal_id.fiscal','=',True),
            ])
        elif j_type == 'nofiscal':
            return self.env['account.move.line'].search([
                ('company_id', '=', company_id),
                ('account_id', '=', account.id),
                ('date', '>=', start),
                ('date', '<=', end),
                ('move_id.journal_id.fiscal','=',False),
            ])
        else:
            return self.env['account.move.line'].search([
                ('company_id', '=', company_id),
                ('account_id', '=', account.id),
                ('date', '>=', start),
                ('date', '<=', end),
            ])

    #@api.multi
    def move_line_partner_prepare(self, account, partner):
        self.ensure_one()
        move_line = {}
        balance = partner.get('debit', 0.) - partner.get('credit', 0.)
        precision = self.env['decimal.precision'].precision_get('Account')
        precision = 12
        description = self.name or account.name
        partner_id = partner.get('partner_id')
        if partner_id:
            partner_id = partner_id[0]
        date = self.fyc_config_id.fyc_id.date_end
        if self.fyc_config_id.move_type == 'opening':
            date = self.fyc_config_id.fyc_id.date_opening
        if not float_is_zero(balance, precision_digits=precision):
            move_line = {
                'account_id': account.id,
                'debit': balance < 0 and -balance,
                'credit': balance > 0 and balance,
                'name': description,
                'date': date,
                'partner_id': partner_id,
            }
        else:
            balance = 0
        return balance, move_line

    #@api.multi
    def account_partners_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        return self.env['account.move.line'].read_group([
            ('company_id', '=', company_id),
            ('account_id', '=', account.id),
            ('date', '>=', start),
            ('date', '<=', end),
        ], ['partner_id', 'credit', 'debit'], ['partner_id'])


class AccountFiscalyearClosingType(models.Model):
    _inherit = "account.fiscalyear.closing.type.abstract"
    _name = "account.fiscalyear.closing.type"

    fyc_config_id = fields.Many2one(
        comodel_name='account.fiscalyear.closing.config', index=True,
        string="Configuración de cierre del año fiscal", readonly=True, required=True,
        ondelete='cascade',
    )
