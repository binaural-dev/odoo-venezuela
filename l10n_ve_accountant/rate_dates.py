from odoo import fields


def user_local_date(record, timestamp=None):
    """Dia local del usuario de ``timestamp`` (Datetime en UTC) o de hoy si no se pasa.

    ``context_today`` / ``context_timestamp`` leen la zona horaria de ``env.context['tz']``
    y sin ella caen en UTC: una orden creada por codigo (cron, integracion, API) a las 8 pm de
    Caracas buscaria la tasa del dia siguiente, que quiza aun no existe. Por eso, sin zona en el
    contexto se usa la del usuario del entorno; solo si tampoco la tiene queda UTC.
    """
    tz = record.env.context.get("tz") or record.env.user.tz
    local = record.with_context(tz=tz) if tz else record
    if timestamp:
        return fields.Datetime.context_timestamp(
            local, fields.Datetime.to_datetime(timestamp)
        ).date()
    return fields.Date.context_today(local)
