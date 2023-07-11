# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

import re
from collections import namedtuple


DroggolSearchTerm = namedtuple('DrSearchTuple', ['ds_name', 'category_id', 'formulate'])


class DroggolSearchTerm:

    _name = 'product.public.category'

    def __init__(self, ds_name, category_id, formulate, *args, **kwargs):
        self.ds_name = ds_name
        self.id = category_id
        self.formulate = formulate
        args = args
        kwargs = kwargs

    def __repr__(self):
        return f'{self.ds_name}({self.id}:{self.formulate})'


class CategorySearchDB:
    def __init__(self, db):
        self.db = db

    def search(self, term, options=False):
        result = []
        categ_ids = []

        for category in self.db:
            if category.formulate:
                continue

            if re.search(re.escape(term), category.ds_name, re.IGNORECASE):
                result.append(category)
                categ_ids.append(category.id)
        return result
