# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import api, models


class DrCacheMixin(models.AbstractModel):
    _name = 'dr.cache.mixin'
    _description = 'Cache Mixin'

    _fields_to_watch = []

    @api.model_create_multi
    def create(self, vals_list):
        self.clear_caches()
        return super().create(vals_list)

    def write(self, vals):
        self.clear_caches()
        return super().write(vals)

    def unlink(self):
        self.clear_caches()
        return super().unlink()
