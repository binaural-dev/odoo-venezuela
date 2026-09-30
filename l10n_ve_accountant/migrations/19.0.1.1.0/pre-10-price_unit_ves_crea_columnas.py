"""Crea `price_unit_ves` y `ves_currency_id` en `account_move_line` antes de que las cree el ORM.

Por qué: los dos son campos **nuevos** en 19.0 (`l10n_ve_accountant`), `compute=` con
    `store=True`. Cuando el ORM crea la columna de un campo así, marca **todas** las filas de la
    tabla para recomputar (`odoo/orm/models.py::_auto_init`: `if new and field.compute` →
    `add_to_compute`, con un `SELECT id FROM account_move_line` completo). En Proalca son
    **467.276 líneas** en un solo recordset, y `_compute_price_unit_ves` hace un `_convert()` con
    tasa histórica por línea. Ese `new` solo es cierto si la columna **no existía**: creándola
    acá, el ORM la encuentra hecha y no marca nada.
    Lo que se puede calcular exacto en SQL se llena acá; lo que necesita `_convert()` queda en
    NULL y lo recalcula por lotes el `post-` hermano.
Si no corre: no se pierde ningún dato —el ORM calcularía los dos campos igual—, pero lo hace de
    un tirón sobre las 467.276 líneas dentro de la transacción del upgrade: es el riesgo de
    MemoryError/timeout que documenta el doc 02 ("`explode_query_range` no es opcional en tablas
    grandes").
Revertir: `ALTER TABLE account_move_line DROP COLUMN price_unit_ves, DROP COLUMN ves_currency_id`.
    No hay dato de v17 que perder: las dos columnas nacen en 19.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

TABLE = "account_move_line"


def _ves_currency_id(cr):
    """El mismo VES que resuelve `_compute_ves_currency_id`, en el mismo orden.

    El compute hace `env.ref("base.VES", raise_if_not_found=False)` —que **no** filtra por
    `active`— y solo si eso falla cae a un `search([("name","=","VES")])`, que sí lo filtra.
    Importa: en Proalca `VES` existe con `active = false`, así que el xmlid lo encuentra y el
    search no. Invertir el orden daría otro resultado.
    """
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'VES' AND model = 'res.currency'"
    )
    row = cr.fetchone()
    if row:
        return row[0]
    cr.execute("SELECT id FROM res_currency WHERE name = 'VES' AND active ORDER BY id LIMIT 1")
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:  # instalación limpia: el ORM crea y calcula sobre una tabla vacía
        return

    creada_price = util.create_column(cr, TABLE, "price_unit_ves", "numeric")
    creada_ves = util.create_column(
        cr, TABLE, "ves_currency_id", "int4", fk_table="res_currency", on_delete_action="SET NULL"
    )
    if not (creada_price or creada_ves):
        _logger.info("price_unit_ves/ves_currency_id ya existían; no se recrean")

    # ---- ves_currency_id: calculable exacto en SQL, no necesita recompute ----
    # El compute es `ves_currency_id = currency_id if currency_id == VES else False`.
    ves_id = _ves_currency_id(cr)
    if ves_id is None:
        _logger.info("no hay moneda VES en esta BD: ves_currency_id queda NULL en todas las líneas")
        ves_rows = 0
    else:
        cr.execute(
            """
            UPDATE account_move_line
               SET ves_currency_id = %s
             WHERE currency_id = %s
               AND ves_currency_id IS DISTINCT FROM %s
            """,
            (ves_id, ves_id, ves_id),
        )
        ves_rows = cr.rowcount

    # ---- price_unit_ves: solo la rama trivial del compute ----
    # `if not line.currency_id or line.currency_id == company_currency: price_unit_ves = price_unit`
    # El resto pasa por `currency_id._convert(...)` con la tasa de `_get_foreign_rate_date()`: eso
    # no se traduce a SQL sin reimplementar la resolución de tasas históricas de Odoo, y escribir
    # una tasa inventada está explícitamente prohibido (doc 02 §8). Queda NULL para el `post-`.
    cr.execute(
        """
        UPDATE account_move_line aml
           SET price_unit_ves = aml.price_unit
          FROM res_company c
         WHERE c.id = aml.company_id
           AND (aml.currency_id IS NULL OR aml.currency_id = c.currency_id)
           AND aml.price_unit_ves IS NULL
        """
    )
    triviales = cr.rowcount

    # `price_unit = 0` se resuelve en SQL sin importar la moneda: las dos ramas del compute
    # terminan en 0. La trivial asigna `price_unit = 0`; la otra devuelve
    # `float_round(_convert(0, ...)) = 0` porque `_convert` escala el importe por la tasa y
    # cualquier tasa por 0 es 0. Mandarlas al recompute del ORM sería pagar una conversión con
    # búsqueda de tasa histórica por línea para llegar al mismo 0.
    #
    # No es un caso de borde: en el piloto las 302.947 líneas en moneda extranjera tienen
    # `price_unit = 0` (son apuntes que no son de factura), así que esto es lo que evita una
    # pasada del ORM sobre 302.947 registros para no cambiar nada.
    cr.execute(
        """
        UPDATE account_move_line
           SET price_unit_ves = 0
         WHERE price_unit_ves IS NULL
           AND (price_unit = 0 OR price_unit IS NULL)
        """
    )
    en_cero = cr.rowcount

    cr.execute(
        """
        SELECT count(*)
          FROM account_move_line aml
          JOIN res_company c ON c.id = aml.company_id
         WHERE aml.price_unit_ves IS NULL
           AND aml.currency_id IS NOT NULL
           AND aml.currency_id <> c.currency_id
        """
    )
    pendientes = cr.fetchone()[0]

    _logger.info(
        "price_unit_ves: %s líneas por moneda de la compañía + %s con price_unit 0, resueltas en "
        "SQL; %s pendientes de _convert() en el post-; ves_currency_id: %s líneas en VES",
        triviales,
        en_cero,
        pendientes,
        ves_rows,
    )

    util.add_to_migration_reports(
        "l10n_ve_accountant: `price_unit_ves` y `ves_currency_id` se crearon antes del ORM para "
        "evitar que marcara las %s líneas de account_move_line para recomputar de un tirón. "
        "Resueltas en SQL: %s por tener la moneda de la compañía y %s por tener `price_unit` en 0 "
        "(el compute da 0 por cualquiera de sus dos ramas). Quedan %s para recalcular por lotes en "
        "el post-, las únicas que necesitan tasa histórica. `ves_currency_id`: %s líneas en VES "
        "(el resto queda NULL, que es el valor que da el compute)."
        % (triviales + en_cero + pendientes, triviales, en_cero, pendientes, ves_rows),
        category="Binaural · Contabilidad",
    )
