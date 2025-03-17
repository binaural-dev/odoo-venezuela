# -*- coding: utf-8 -*-
# Copyright (C) 2023-TODAY TechKhedut (<https://www.techkhedut.com>)
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo.tools import convert_file


def import_csv_data(cr):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""
    filenames = [
        'data/do.not.track.models.csv',
    ]
    for filename in filenames:
        convert_file(
            cr, 'tk_security_master',
            filename, None, mode='init', noupdate=True,
            kind='init', pathname=None,
        )


def post_init(cr):
    import_csv_data(cr)
