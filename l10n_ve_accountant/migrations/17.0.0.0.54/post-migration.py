import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("17.0.0.0.54: Replaced by 17.0.0.0.56 (ORM-based rounding)")
