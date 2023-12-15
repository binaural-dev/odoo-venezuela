import logging
_logger = logging.getLogger(__name__)
def migrate(cr, version):
    _logger.warning("PRE MIGRATION AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    cr.execute("ALTER TABLE product_template ADD COLUMN temp_ciu_id int")
    cr.execute("UPDATE product_template SET temp_ciu_id=ciu_id")
