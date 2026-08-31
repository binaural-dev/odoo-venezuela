from . import models

# `tests` solo debe importarse en modo test (Odoo lo hace automáticamente
# al descubrir el paquete durante `--test-enable`); no se importa aquí para
# no cargar TransactionCase/tests en producción.
