from odoo.tools.float_utils import float_is_zero, float_round
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _get_tax_group_product_lines(self, product_lines, group):
        """Líneas de producto que llevan algún impuesto de `group` (un elemento
        de `tax_groups` del resumen de `tax_totals`).

        Un impuesto 'group' deja al PADRE en `l.tax_ids`, pero el núcleo expande
        `involved_tax_ids` a sus HIJOS: se comprueban ambos."""
        involved_tax_ids = set(group.get('involved_tax_ids', []))
        return product_lines.filtered(
            lambda l: (set(l.tax_ids.ids) & involved_tax_ids)
            or (set(l.tax_ids.children_tax_ids.ids) & involved_tax_ids)
        )

    @api.model
    def _fix_base_amount_for_multi_currency(self, res, record):
        """Corrige `base_amount` cuando la moneda del documento difiere de la
        de la compañía. El mecanismo de "real portion" corrige `line.balance`
        pero no `line.currency_rate`, así que el cómputo del core para
        `base_amount` difiere del balance real corregido por la unidad de
        redondeo de la moneda. Redistribuye la diferencia proporcionalmente
        entre subtotales y grupos de impuesto."""
        if record._name != 'account.move' or not record.is_invoice(include_receipts=True):
            return
        if not record.currency_id or not record.company_id.currency_id:
            return
        if record.currency_id == record.company_id.currency_id:
            return
        product_lines = record.line_ids.filtered(
            lambda l: l.display_type == 'product' and not l.tax_repartition_line_id
        )
        if not product_lines:
            return
        cc = record.company_id.currency_id
        sign = record.direction_sign
        correct_base = cc.round(sum(product_lines.mapped('balance')) * sign)
        diff = cc.round(correct_base - res.get('base_amount', 0.0))
        if cc.is_zero(diff):
            return
        res['base_amount'] = correct_base
        res['total_amount'] = cc.round(res.get('total_amount', 0.0) + diff)
        subtotals = res.get('subtotals', [])
        if not subtotals:
            return
        total_sub_base = sum(s.get('base_amount', 0.0) for s in subtotals)
        if cc.is_zero(total_sub_base):
            return
        remaining_diff = diff
        n_sub = len(subtotals)
        for i, subtotal in enumerate(subtotals):
            if i < n_sub - 1:
                ratio = subtotal.get('base_amount', 0.0) / total_sub_base
                share = cc.round(ratio * diff)
                subtotal['base_amount'] = subtotal.get('base_amount', 0.0) + share
                subtotal['total_amount'] = subtotal.get('total_amount', 0.0) + share
                remaining_diff -= share
            else:
                subtotal['base_amount'] = subtotal.get('base_amount', 0.0) + remaining_diff
                subtotal['total_amount'] = subtotal.get('total_amount', 0.0) + remaining_diff
            # Sync each tax group's base_amount with the REAL balance of ITS
            # OWN product lines, not a proportional split of the aggregate
            # diff -- that only guarantees the subtotal matches, not each
            # individual group (confirmed off-by-a-cent on a real invoice).
            tax_groups = subtotal.get('tax_groups', [])
            if not tax_groups:
                continue
            tg_total = sum(tg.get('base_amount', 0.0) for tg in tax_groups)
            if cc.is_zero(tg_total):
                continue
            # Every group (including the last) is priced from its OWN
            # `tg_lines`' real balance -- not a "last group takes the
            # remainder" special case. That remainder was only valid
            # under the assumption that `subtotal['base_amount']` equals
            # the sum of every OTHER group's own-lines base, which breaks
            # in two real scenarios (code review, PR tax-totals-base-per-
            # group): an untaxed product line still contributes to
            # `subtotal['base_amount']` (summed from ALL product lines)
            # but is never matched by any group's `tg_lines` -- with a
            # single tax group, that group IS "the last one" by
            # construction and the stray balance leaked into it; and a
            # line taxed by two distinct groups legitimately contributes
            # its full balance to BOTH groups' `tg_lines` (same base,
            # two different taxes), which the remainder math read as
            # double-counted, landing the last group at 0 or negative.
            for tg in tax_groups:
                tg_lines = self._get_tax_group_product_lines(product_lines, tg)
                if tg_lines:
                    tg_base = cc.round(sum(tg_lines.mapped('balance')) * sign)
                else:
                    # Fallback: couldn't identify this group's own lines
                    # (exotic tax setup) -- keep the old proportional split.
                    tg_ratio = tg.get('base_amount', 0.0) / tg_total
                    tg_base = cc.round(tg_ratio * subtotal['base_amount'])
                tg['base_amount'] = tg_base
                tg['display_base_amount'] = tg_base
                tg['total_amount'] = cc.round(tg.get('tax_amount', 0.0) + tg_base)

    @api.model
    def _fix_tax_amount_for_round_per_line(self, res, record, company):
        """Corrige `tax_amount` para `tax_calculation_rounding_method ==
        'round_per_line'`. `account.move._sync_tax_lines` (`account_move.py`,
        `_per_line_tax_sums`) ya redondea el impuesto de cada línea de
        producto individualmente y suma los montos redondeados -- el método
        de la máquina fiscal, que es lo que realmente se postea al libro
        (`account.move.line.balance`/`amount_currency` de las líneas `tax`).
        Pero este summary se calcula de forma independiente desde
        `base_lines` a través del motor del core (`super()` en el llamador),
        que sigue sumando las bases y redondeando una sola vez sin importar
        el modo configurado. Sin esta corrección, el widget de la factura y
        el PDF impreso mostrarían un IVA distinto al que realmente se
        posteó -- las líneas de impuesto reales son la única fuente de
        verdad, una vez que existen.

        Precisamente por eso se sale temprano si `record` es un registro
        virtual (`NewId`, típico de un onchange en vivo sobre un borrador
        todavía no guardado): en ese momento no existe ningún asiento real
        que igualar todavía, y `record.line_ids` puede traer líneas de
        impuesto desactualizadas de un paso de onchange anterior (ej. el
        usuario cambió la moneda y luego el precio en el mismo borrador,
        sin guardar entre medio) -- corregir contra esas líneas pisaría el
        `tax_amount` recién calculado por el core (ya correcto para el
        precio actual) con un valor obsoleto."""
        if record._name != 'account.move' or not record.is_invoice(include_receipts=True):
            return
        if isinstance(record.id, api.NewId):
            return
        real_tax_lines = record.line_ids.filtered(lambda l: l.display_type == 'tax')
        if not real_tax_lines:
            return
        if company.tax_calculation_rounding_method != 'round_per_line' and not any(
            t.price_include and not t.include_base_amount for t in real_tax_lines.tax_line_id
        ):
            return

        cc = company.currency_id
        doc_currency = record.currency_id
        sign = record.direction_sign
        by_group = {}
        for line in real_tax_lines:
            gid = line.tax_group_id.id
            entry = by_group.setdefault(gid, {'balance': 0.0, 'amount_currency': 0.0})
            entry['balance'] += line.balance
            entry['amount_currency'] += line.amount_currency

        total_tax_diff = 0.0
        total_tax_diff_currency = 0.0
        for subtotal in res.get('subtotals', []):
            for tg in subtotal.get('tax_groups', []):
                group_totals = by_group.get(tg.get('id'))
                if group_totals is None:
                    continue
                correct_tax = cc.round(group_totals['balance'] * sign)
                correct_tax_currency = doc_currency.round(group_totals['amount_currency'] * sign)
                diff = cc.round(correct_tax - tg.get('tax_amount', 0.0))
                diff_currency = doc_currency.round(correct_tax_currency - tg.get('tax_amount_currency', 0.0))
                if cc.is_zero(diff) and doc_currency.is_zero(diff_currency):
                    continue
                tg['tax_amount'] = correct_tax
                tg['tax_amount_currency'] = correct_tax_currency
                total_tax_diff += diff
                total_tax_diff_currency += diff_currency

        if cc.is_zero(total_tax_diff) and doc_currency.is_zero(total_tax_diff_currency):
            return

        # Re-aggregate subtotal/top-level totals from the corrected
        # tax_groups, mirroring the core's own aggregation
        # (account_tax.py:2889-2893 upstream).
        for subtotal in res.get('subtotals', []):
            subtotal['tax_amount'] = sum(tg.get('tax_amount', 0.0) for tg in subtotal.get('tax_groups', []))
            subtotal['tax_amount_currency'] = sum(
                tg.get('tax_amount_currency', 0.0) for tg in subtotal.get('tax_groups', [])
            )
        res['tax_amount'] = cc.round(res.get('tax_amount', 0.0) + total_tax_diff)
        res['tax_amount_currency'] = doc_currency.round(res.get('tax_amount_currency', 0.0) + total_tax_diff_currency)
        res['total_amount'] = cc.round(res.get('total_amount', 0.0) + total_tax_diff)
        res['total_amount_currency'] = doc_currency.round(
            res.get('total_amount_currency', 0.0) + total_tax_diff_currency
        )


    # ── Global: el centavo del redondeo cae en el grupo de impuesto al que pertenece ──
    # Con `round_globally`, el núcleo agrupa las líneas por moneda, nota de crédito
    # y `computation_key`, pero NO por grupo de impuesto: la diferencia entre el
    # total redondeado de las bases y la suma de las bases redondeadas de TODA la
    # factura se reparte entre todas las líneas (cae en la de mayor base). Si esa
    # diferencia nace en el grupo IVA, puede caer en una línea exenta e inflar la
    # base del grupo Exento (y la del IVA queda un centavo por debajo) en el
    # documento fiscal. Se reparte la diferencia dentro de cada grupo de impuesto
    # (las líneas con `computation_key` siguen redondeándose juntas, como en el núcleo).
    @api.model
    def _get_base_line_rounding_key(self, base_line):
        """Clave con la que se reparte la diferencia de redondeo de una línea base.

        Las líneas con `computation_key` (combos, anticipos...) se redondean juntas
        por diseño del núcleo y se respetan. Las demás comparten la diferencia con
        las líneas de sus mismos grupos de impuesto (tupla ordenada de ids; vacía
        si la línea no lleva impuestos)."""
        if base_line.get('computation_key'):
            return ('computation_key', base_line['computation_key'])
        taxes = base_line['tax_ids'].flatten_taxes_hierarchy()
        return ('tax_groups', tuple(sorted(set(taxes.tax_group_id.ids))))

    @api.model
    def _round_tax_details_base_lines(self, base_lines, company, mode='mixed'):
        if company.tax_calculation_rounding_method != 'round_globally' or len(base_lines) < 2:
            return super()._round_tax_details_base_lines(base_lines, company, mode=mode)
        lines_by_key = {}
        for base_line in base_lines:
            lines_by_key.setdefault(self._get_base_line_rounding_key(base_line), []).append(base_line)
        for lines in lines_by_key.values():
            super()._round_tax_details_base_lines(lines, company, mode=mode)

    # ── Global + impuestos incluidos en el precio ────────────────────────
    # Con `round_globally`, el núcleo compensa el centavo del redondeo global en
    # la línea de IVA. `_sync_tax_lines` reemplaza luego el IVA incluido por la
    # suma línea por línea, así que esa compensación se pierde y el total del
    # asiento queda 0,01 distinto de lo digitado. Se fija la base de cada línea
    # con IVA incluido a su valor individual, igual que
    # `account.move.line._price_included_split` ya hace con el saldo VEF, tanto en
    # la moneda del documento como en la alterna. Los saldos y el IVA en la moneda
    # de la compañía siguen saliendo de `_sync_tax_lines`, que calcula el impuesto
    # sobre los saldos VEF. Las demás líneas conservan lo que calcula el núcleo
    # (la diferencia de su grupo la reparte `_round_tax_details_base_lines`).
    @api.model
    def _prepare_tax_lines(self, base_lines, company, **kwargs):
        res = super()._prepare_tax_lines(base_lines, company, **kwargs)
        if company.tax_calculation_rounding_method == 'round_globally' and base_lines:
            self._apply_price_included_per_line(res, base_lines)
        return res

    @api.model
    def _apply_price_included_per_line(self, res, base_lines):
        """Deja cada línea con IVA incluido y el IVA incluido con su valor
        individual (ver el comentario de `_prepare_tax_lines`). Solo actúa en
        facturas con al menos una línea con impuestos porcentuales incluidos en
        el precio."""
        first_line = base_lines[0].get('record')
        if first_line is None or first_line._name != 'account.move.line':
            return
        move = first_line.move_id
        if not move.is_invoice(include_receipts=True):
            return
        product_lines = move.line_ids.filtered(lambda l: l.display_type == 'product')
        included_lines = product_lines.filtered(lambda l: l._price_included_split())
        if not included_lines:
            return
        sign = move.direction_sign
        tax_amount_by_tax = {}
        for base_line, to_update in res['base_lines_to_update']:
            line = base_line['record']
            if line.display_type != 'product':
                continue
            if line not in included_lines:
                # Las demás líneas conservan lo que calcula el núcleo: la diferencia de
                # redondeo de su grupo la reparte `_round_tax_details_base_lines`.
                continue
            currency = base_line['currency_id']
            raw = (
                base_line['price_unit'] * base_line['quantity']
                * (1 - (base_line.get('discount') or 0.0) / 100.0) * sign
            )
            taxes = line.tax_ids
            total_rate = sum(taxes.mapped('amount'))
            base = currency.round(raw / (1 + total_rate / 100.0))
            included = currency.round(raw)
            to_update['amount_currency'] = base
            if float_is_zero(total_rate, precision_digits=4):
                # Exento incluido en el precio (0 %): no hay impuesto que repartir.
                continue
            for tax in taxes:
                tax_amount_by_tax[tax.id] = tax_amount_by_tax.get(tax.id, 0.0) + currency.round(
                    (included - base) * tax.amount / total_rate
                )
        RepartitionLine = self.env['account.tax.repartition.line']

        def _set_tax_amount(repartition_value, target):
            repartition_line = (
                repartition_value if hasattr(repartition_value, 'tax_id')
                else RepartitionLine.browse(repartition_value)
            )
            if (
                repartition_line
                and repartition_line.repartition_type == 'tax'
                and repartition_line.tax_id.id in tax_amount_by_tax
            ):
                target['amount_currency'] = (
                    tax_amount_by_tax[repartition_line.tax_id.id] * repartition_line.factor_percent / 100.0
                )

        for vals in res['tax_lines_to_add']:
            _set_tax_amount(vals.get('tax_repartition_line_id'), vals)
        for vals, _key, to_update in res['tax_lines_to_update']:
            _set_tax_amount(vals.get('tax_repartition_line_id'), to_update)

    @api.model
    def _fix_base_amount_from_real_lines(self, res, record, company):
        """Con `round_globally` e impuestos incluidos en el precio, el IVA del
        widget sale de las líneas de impuesto reales (por línea) pero la base
        la calcula el núcleo con redondeo global: el total del widget queda
        0,01 distinto del asiento. Se recalculan las bases desde las líneas de
        producto reales (documento y moneda de la compañía)."""
        if record._name != 'account.move' or not record.is_invoice(include_receipts=True):
            return
        if isinstance(record.id, api.NewId):
            return
        real_tax_lines = record.line_ids.filtered(lambda l: l.display_type == 'tax')
        if not any(t.price_include and not t.include_base_amount for t in real_tax_lines.tax_line_id):
            return
        sign = record.direction_sign
        doc, cc = record.currency_id, company.currency_id
        products = record.line_ids.filtered(lambda l: l.display_type == 'product' and not l.tax_repartition_line_id)

        def sums(lines):
            return (
                doc.round(sum(lines.mapped('amount_currency')) * sign),
                cc.round(sum(lines.mapped('balance')) * sign),
            )

        all_doc, all_company = sums(products)
        if doc == cc:
            all_company = all_doc
        # Cada subtotal parte del total del anterior (grupos con `preceding_subtotal`).
        running_doc, running_company = all_doc, all_company
        for subtotal in res.get('subtotals', []):
            subtotal_tax_doc = subtotal_tax_company = 0.0
            for group in subtotal.get('tax_groups', []):
                group_lines = self._get_tax_group_product_lines(products, group)
                if group_lines:
                    base_doc, base_company = sums(group_lines)
                    if doc == cc:
                        base_company = base_doc
                    group['base_amount_currency'] = group['display_base_amount_currency'] = base_doc
                    group['base_amount'] = group['display_base_amount'] = base_company
                subtotal_tax_doc += group.get('tax_amount_currency', 0.0)
                subtotal_tax_company += group.get('tax_amount', 0.0)
                group['total_amount_currency'] = doc.round(
                    group['base_amount_currency'] + group.get('tax_amount_currency', 0.0)
                )
            subtotal['base_amount_currency'] = running_doc
            subtotal['base_amount'] = running_company
            running_doc = doc.round(running_doc + subtotal_tax_doc)
            running_company = cc.round(running_company + subtotal_tax_company)
            subtotal['total_amount_currency'] = running_doc
            subtotal['total_amount'] = running_company
        res['base_amount_currency'] = all_doc
        res['base_amount'] = all_company
        res['total_amount_currency'] = running_doc
        res['total_amount'] = running_company

    @api.model
    def _fix_price_included_summary_from_base_lines(self, res, base_lines, record):
        """Registro virtual (onchange) o factura sin líneas de impuesto todavía: el
        IVA incluido del resumen se calcula línea por línea, igual que lo hace
        `_sync_tax_lines` con las líneas reales.

        Con Global, el núcleo reparte el centavo del redondeo del IVA incluido entre
        las líneas (3,57 en vez de 1,79 + 1,79 = 3,58). El cliente reenvía ese JSON al
        guardar y `_inverse_tax_totals` lo interpreta como una edición manual del
        IVA: escribe 3,57 en la línea de impuesto y el saldo en bolívares sale de
        ahí (3,57 × tasa) en lugar de calcularse sobre la base en bolívares."""
        if record._name != 'account.move' or not record.is_invoice(include_receipts=True):
            return
        if not isinstance(record.id, api.NewId) and record.line_ids.filtered(lambda l: l.display_type == 'tax'):
            return
        currency = record.currency_id
        group_delta = {}
        total_base_delta = 0.0
        for base_line in base_lines:
            taxes = base_line['tax_ids']
            if not taxes or any(
                t.amount_type != 'percent' or not t.price_include or t.include_base_amount
                for t in taxes
            ):
                continue
            details = base_line['tax_details']
            total_rate = sum(taxes.mapped('amount'))
            if float_is_zero(total_rate, precision_digits=4):
                continue
            raw = base_line['price_unit'] * base_line['quantity'] * (1 - (base_line.get('discount') or 0.0) / 100.0)
            base = currency.round(raw / (1 + total_rate / 100.0))
            tax_total = currency.round(raw) - base
            total_base_delta += base - (
                details['total_excluded_currency'] + details.get('delta_total_excluded_currency', 0.0)
            )
            core_by_tax = {d['tax'].id: d for d in details['taxes_data']}
            for tax in taxes:
                core = core_by_tax.get(tax.id)
                if not core:
                    continue
                delta = group_delta.setdefault(tax.tax_group_id.id, [0.0, 0.0])
                delta[0] += currency.round(tax_total * tax.amount / total_rate) - core['tax_amount_currency']
                delta[1] += base - core['base_amount_currency']
        if not group_delta:
            return
        for subtotal in res.get('subtotals', []):
            for group in subtotal.get('tax_groups', []):
                delta = group_delta.get(group['id'])
                if delta:
                    group['tax_amount_currency'] = currency.round(group['tax_amount_currency'] + delta[0])
                    group['base_amount_currency'] = currency.round(group['base_amount_currency'] + delta[1])
                    group['display_base_amount_currency'] = currency.round(
                        group['display_base_amount_currency'] + delta[1]
                    )
        # Cada subtotal parte del total del anterior (grupos con `preceding_subtotal`).
        running = currency.round(res['base_amount_currency'] + total_base_delta)
        tax_amount = 0.0
        res['base_amount_currency'] = running
        for subtotal in res.get('subtotals', []):
            subtotal_tax = sum(g['tax_amount_currency'] for g in subtotal.get('tax_groups', []))
            subtotal['base_amount_currency'] = running
            subtotal['tax_amount_currency'] = currency.round(subtotal_tax)
            running = currency.round(running + subtotal_tax)
            subtotal['total_amount_currency'] = running
            tax_amount += subtotal_tax
        res['tax_amount_currency'] = currency.round(tax_amount)
        res['total_amount_currency'] = running

    @api.model
    def _fix_foreign_summary_from_lines(self, foreign_res, record):
        """El alterno del widget se calculaba por separado con el motor del
        núcleo sobre `foreign_price`, mientras que los apuntes toman el alterno
        de `foreign_balance` (y, en una tercera moneda, el total agregado). Los
        apuntes son lo que se publica al libro: el widget los refleja."""
        if record._name != 'account.move' or not record.is_invoice(include_receipts=True):
            return
        if isinstance(record.id, api.NewId) or not record.foreign_currency_id:
            return
        fc, ds = record.foreign_currency_id, record.direction_sign
        products = record.line_ids.filtered(lambda l: l.display_type == 'product' and not l.tax_repartition_line_id)
        tax_lines = record.line_ids.filtered(lambda l: l.display_type == 'tax')
        if not products:
            return

        def value(lines):
            return fc.round(sum(l.foreign_debit - l.foreign_credit for l in lines) * ds)

        base, tax = value(products), value(tax_lines)
        foreign_res['base_amount_currency'] = base
        foreign_res['tax_amount_currency'] = tax
        foreign_res['total_amount_currency'] = fc.round(base + tax)
        running = base
        for subtotal in foreign_res.get('subtotals', []):
            subtotal_tax = 0.0
            for group in subtotal.get('tax_groups', []):
                group_lines = self._get_tax_group_product_lines(products, group)
                if group_lines:
                    group['base_amount_currency'] = group['display_base_amount_currency'] = value(group_lines)
                group['tax_amount_currency'] = value(
                    tax_lines.filtered(lambda l: l.tax_group_id.id == group.get('id'))
                )
                subtotal_tax += group['tax_amount_currency']
            subtotal['base_amount_currency'] = running
            subtotal['tax_amount_currency'] = fc.round(subtotal_tax)
            running = fc.round(running + subtotal_tax)
            subtotal['total_amount_currency'] = running

    @api.model
    def _get_tax_totals_summary(
        self, base_lines, currency, company, cash_rounding=None
    ):
        res = super()._get_tax_totals_summary(
            base_lines, currency, company, cash_rounding
        )

        # `company` es un parámetro EXPLÍCITO de este método -- se usa
        # acá y en el resto del método en vez de `self.env.company`
        # (la compañía ACTIVA del entorno, que puede no coincidir: un
        # cron, un usuario multi-compañía, o cualquier llamador que
        # arme este summary explícitamente `with_company(otra_compañía)`,
        # como hace `l10n_ve_exchange_difference._create_exchange_difference_note`
        # al crear sus notas). El `or self.env.company` es solo un
        # fallback defensivo por si algún llamador legado pasara
        # `company=False`; en el camino normal `company` siempre viene
        # seteado por el núcleo (`account.tax._get_tax_totals_summary`
        # lo exige como posicional, no `Optional`).
        company = company or self.env.company
        ves_currency = company.currency_id

        # `base_lines` es el documento REAL para el que se está armando
        # este summary -- se intenta derivar `record` de ahí PRIMERO.
        # `active_model`/`active_id` del contexto son AMBIENTE de la UI
        # (el registro que el usuario tenía abierto cuando se disparó
        # este cómputo, no necesariamente el que se está calculando
        # ahora): un wizard de pago en lote, o un recompute encadenado
        # de otro documento distinto, pueden dejar un `active_id` ajeno
        # en el contexto mientras `base_lines` sigue apuntando al
        # documento correcto -- si el contexto ganara, TODAS las
        # facturas de ese lote heredarían la tasa/moneda de una sola.
        record = False
        if base_lines:
            try:
                first_line = base_lines[0].get('record')
                if first_line and isinstance(first_line, models.Model):
                    if hasattr(first_line, 'move_id'):
                        record = first_line.move_id
                    elif hasattr(first_line, 'order_id'):
                        record = first_line.order_id
                    else:
                        record = first_line
            except Exception as e:
                _logger.warning("Error deduciendo el record al generar summary tax base %s", e)

        if not record:
            active_model = self.env.context.get('active_model')
            active_id = self.env.context.get('active_id')
            if active_model and active_id:
                if isinstance(active_id, api.NewId):
                    active_id = active_id.origin
                if active_id:
                    record = self.env[active_model].browse(active_id)

        if not record:
            return res

        self._fix_base_amount_for_multi_currency(res, record)
        self._fix_tax_amount_for_round_per_line(res, record, company)
        self._fix_base_amount_from_real_lines(res, record, company)
        self._fix_price_included_summary_from_base_lines(res, base_lines, record)

        currency_id = company.currency_id or False
        foreign_currency_id = company.foreign_currency_id or False
        company_rate = 1.0
        has_discount= False
        if record._name == "account.move" and record.move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            company_rate = record.company_currency_rate
            currency_id = record.currency_id
            foreign_currency_id =record.foreign_currency_id
            has_discount = any(
                line.discount > 0
                for line in record.invoice_line_ids
            )
        else: 
            if hasattr(record, 'company_id'):
                currency_id = record.company_id.currency_id
            else:
                currency_id = company.currency_id
            foreign_currency_id = company.foreign_currency_id

        # FIXME: Evaluar escenarios en los que hay descuentos.
        res_without_discount = res.copy()
        #? QUESTION do i need to put the amount without discount? 
        #total amount discount 
        formatted_total_discount = 0.0
        formatted_total_discount_ves = 0.0
        if has_discount:
            exchange_rate = company_rate
            total_discount_amount = sum([
                (line.get("price_unit", 0.0) * line.get("quantity", 0.0) * line.get("discount", 0.0) / 100)
                for line in base_lines
            ])
            total_discount_amount_ves = total_discount_amount * exchange_rate
            formatted_total_discount = formatLang(
                env=self.env,
                value=total_discount_amount,
                currency_obj=currency_id
            )
            #discount only en VEF
            formatted_total_discount_ves = formatLang(
                env=self.env,
                value=total_discount_amount_ves,
                currency_obj=ves_currency
            )
        foreign_lines = []
        if record._name == 'account.move':
            foreign_lines, _foreign_tax_lines = record._get_rounded_foreign_base_and_tax_lines()
        elif record._name in ('sale.order','purchase.order'):
            company_id = (record.company_id or company)
            foreign_lines = [
                line._prepare_foreign_base_line_for_taxes_computation()
                for line in record.order_line
                if hasattr(line, '_prepare_foreign_base_line_for_taxes_computation')
            ]
            
            self._add_tax_details_in_base_lines(foreign_lines, company_id)
            self._round_base_lines_tax_details(foreign_lines, company_id)
        foreign_res = super()._get_tax_totals_summary(
            foreign_lines,
            foreign_currency_id,
            company,
            cash_rounding
        )
        self._fix_foreign_summary_from_lines(foreign_res, record)
        #amounts in foreign currency
        res['foreign_currency_id'] = foreign_res['currency_id']
        res['ves_currency_id'] = company.currency_id.id
        res['base_amount_foreign_currency'] = foreign_res['base_amount_currency']
        res['tax_amount_foreign_currency'] = foreign_res['tax_amount_currency']
        res['total_amount_foreign_currency'] = foreign_res['total_amount_currency']
        #discount amount 
        res['formatted_total_discount'] = formatted_total_discount
        res['formatted_total_discount_ves'] = formatted_total_discount_ves
        # Moneda Base
        res['formatted_base_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('base_amount_currency', 0.0),
            currency_obj=currency_id
        )
        res['formatted_tax_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('tax_amount_currency', 0.0),
            currency_obj=currency_id
        )
        res['formatted_total_amount_currency'] = formatLang(
            env=self.env,
            value=res.get('total_amount_currency', 0.0),
            currency_obj=currency_id
        )

        #only VES amounts
        res['formatted_base_amount_currency_ves'] = formatLang(
            env=self.env,
            value=res.get('base_amount', 0.0),
            currency_obj=ves_currency
        )
        res['formatted_tax_amount_currency_ves'] = formatLang(
            env=self.env,
            value=res.get('tax_amount', 0.0),
            currency_obj=ves_currency
        )
        # A draft invoice must not read `amount_total_signed` here: its compute
        # (`_compute_amount`) reads `tax_totals` -- the field being computed --
        # and gets False back, so the residual of the draft is stored as 0 and
        # the invoice shows up as "Paid". Its totals are the ones of this summary.
        total_ves = (
            abs(record.amount_total_signed)
            if record._name == 'account.move' and record.state != 'draft'
            else abs(res.get('total_amount', 0.0))
        )
        res['formatted_total_amount_currency_ves'] = formatLang(
            env=self.env,
            value=total_ves,
            currency_obj=ves_currency
        )
    
        # Foraneos
        res['formatted_base_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('base_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )
        res['formatted_tax_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('tax_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )
        res['formatted_total_amount_foreign_currency'] = formatLang(
            env=self.env,
            value=res.get('total_amount_foreign_currency', 0.0),
            currency_obj=foreign_currency_id
        )

        for res_subtotal, foreign_subtotal in zip(res.get("subtotals", []), foreign_res.get("subtotals", [])):
            res_subtotal["tax_amount_foreign_currency"] = foreign_subtotal.get("tax_amount_currency", 0.0)
            res_subtotal["base_amount_foreign_currency"] = foreign_subtotal.get("base_amount_currency", 0.0)
            res_subtotal["total_amount_foreign_currency"] = foreign_subtotal.get("total_amount_currency", 0.0)

            #Foraneo
            res_subtotal['formatted_base_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            res_subtotal['formatted_tax_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            res_subtotal['formatted_total_amount_foreign_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount_foreign_currency', 0.0),
                currency_obj=foreign_currency_id
            )
            #ONLY VES
            res_subtotal['formatted_base_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount', 0.0),
                currency_obj=ves_currency
            )
            res_subtotal['formatted_tax_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount', 0.0),
                currency_obj=ves_currency
            )
            res_subtotal['formatted_total_amount_currency_ves'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount', 0.0),
                currency_obj=ves_currency
            )
            #Base sistema
            res_subtotal['formatted_base_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('base_amount_currency', 0.0),
                currency_obj=currency_id
            )
            res_subtotal['formatted_tax_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('tax_amount_currency', 0.0),
                currency_obj=currency_id
            )
            res_subtotal['formatted_total_amount_currency'] = formatLang(
                env=self.env,
                value=res_subtotal.get('total_amount_currency', 0.0),
                currency_obj=currency_id
            )

            #Amount discount
            for res_tax_group, foreign_tax_group in zip(res_subtotal.get("tax_groups", []), foreign_subtotal.get("tax_groups", [])):
                res_tax_group["tax_amount_foreign_currency"] = foreign_tax_group.get("tax_amount_currency", 0.0)
                res_tax_group["base_amount_foreign_currency"] = foreign_tax_group.get("base_amount_currency", 0.0)
                res_tax_group["display_base_amount_foreign_currency"] = foreign_tax_group.get("display_base_amount_currency", 0.0)
                # Moneda base
                res_tax_group['formatted_base_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                res_tax_group['formatted_tax_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                # Display
                res_tax_group['formatted_display_base_amount_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('display_base_amount_currency', 0.0),
                    currency_obj=currency_id
                )
                #ONLY VES
                res_tax_group['formatted_base_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount', 0.0),
                    currency_obj=ves_currency
                )
                res_tax_group['formatted_tax_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount', 0.0),
                    currency_obj=ves_currency
                )
                res_tax_group['formatted_total_amount_currency_ves'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('total_amount', 0.0),
                    currency_obj=ves_currency
                )
                # Foranea
                res_tax_group['formatted_base_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('base_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
                res_tax_group['formatted_tax_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('tax_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
                res_tax_group['formatted_display_base_amount_foreign_currency'] = formatLang(
                    env=self.env,
                    value=res_tax_group.get('display_base_amount_foreign_currency', 0.0),
                    currency_obj=foreign_currency_id
                )
        return res
    
    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        """The discount of an invoice line is its effective discount, so a
        module that discounts through a field of its own only extends
        `_get_effective_discount_percent()`."""
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        if record and not isinstance(record, dict) and record._name == "account.move.line":
            res["discount"] = record._get_effective_discount_percent()
        return res

    @api.model
    def _prepare_foreign_base_line_for_taxes_computation(self, record, **kwargs):
        """ Convert any representation of a business object ('record') into a base line being a python
        dictionary that will be used to use the generic helpers for the taxes computation.

        The whole method is designed to ease the conversion from a business record.
        For example, when passing either account.move.line, either sale.order.line or purchase.order.line,
        providing explicitely a 'product_id' in kwargs is not necessary since all those records already have
        an `product_id` field.

        :param record:  A representation of a business object a.k.a a record or a dictionary.
        :param kwargs:  The extra values to override some values that will be taken from the record.
        :return:        A dictionary representing a base line.
        """
        def load(field, fallback, from_base_line=False):
            return self._get_base_line_field_value_from_record(record, field, kwargs, fallback, from_base_line=from_base_line)

        currency = (
            load('foreign_currency_id', None)
            or self.env.company.foreign_currency_id)
        base_line = {
            **kwargs,
            'record': record,
            'id': load('id', 0),

            # Basic fields:
            'product_id': load('product_id', self.env['product.product']),
            'product_uom_id': load('product_uom_id', self.env['uom.uom']),
            'tax_ids': load('tax_ids', self.env['account.tax']),
            'price_unit': load('price_unit', 0.0),
            'quantity': load('quantity', 0.0),
            'discount': load('discount', 0.0),
            'currency_id': currency,
            'deferred_start_date': self._get_base_line_field_value_from_record(record, 'deferred_start_date', kwargs, False),
            'deferred_end_date': self._get_base_line_field_value_from_record(record, 'deferred_end_date', kwargs, False),

            # The special_mode for the taxes computation:
            'special_mode': load('special_mode', False, from_base_line=True),

            # A special typing of base line for some custom behavior:
            'special_type': load('special_type', False, from_base_line=True),

            # All computation are managing the foreign currency and the local one.
            'rate': load('rate', 1.0),

            # For all computation that are inferring a base amount in order to reach a total you know in advance, you have to force some
            # base/tax amounts for the computation (E.g. down payment, combo products, global discounts etc).
            'manual_tax_amounts': load('manual_tax_amounts', None, from_base_line=True),
            'manual_total_excluded_currency': load('manual_total_excluded_currency', None, from_base_line=True),
            # Add a function allowing to filter out some taxes during the evaluation. Those taxes can't be removed from the base_line
            'filter_tax_function': load('filter_tax_function', None, from_base_line=True),
            'manual_total_excluded' : load('manual_total_excluded', None, from_base_line=True),
            # ===== Accounting stuff =====
            'sign': load('sign', 1.0),
            'is_refund': load('is_refund', False),
            'tax_tag_invert': load('tax_tag_invert', False),
            'partner_id': load('partner_id', self.env['res.partner']),
            'account_id': load('account_id', self.env['account.account']),
            'analytic_distribution': load('analytic_distribution', None),
        }

        # --- Lógica extra inspirada en la función base ---
        extra_tax_data = self._import_base_line_extra_tax_data(base_line, load('extra_tax_data', {}) or {})
        base_line.update({
            'computation_key': load('computation_key', extra_tax_data.get('computation_key'), from_base_line=True),
            'manual_tax_amounts': load('manual_tax_amounts', extra_tax_data.get('manual_tax_amounts'), from_base_line=True),
        })
        if 'price_unit' in extra_tax_data:
            base_line['price_unit'] = extra_tax_data['price_unit']

        # Propagar valores personalizados del record si es dict
        if record and isinstance(record, dict):
            for k, v in record.items():
                if k.startswith('_') and k not in base_line:
                    base_line[k] = v

        manual_fields = (
            'manual_total_excluded',
            'manual_total_excluded_currency',
            'manual_total_included',
            'manual_total_included_currency',
        )
        for field in manual_fields:
            base_line.setdefault(field, None)
        return base_line
