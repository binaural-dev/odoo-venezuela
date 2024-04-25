from odoo.tools.translate import _
from odoo.http import request
import functools


class ValidateRequest:
    @staticmethod
    def require(fields, kwargs, parent_field=False):
        errors = []
        error_msg = _("Is required")

        if parent_field:
            kwargs = kwargs.get(parent_field)

            if not kwargs:
                return [parent_field, error_msg]

        for field in fields:
            key = field[0]

            if len(field) == 2:
                error_msg = field[1]

            if key not in kwargs.keys():
                errors.append([key, error_msg])

        if len(errors) > 0 and parent_field:
            errors = [parent_field, errors]

        return errors

    @staticmethod
    def json(validation_errors):
        if any(validation_errors):
            return {"status": 400, "msg:": str(validation_errors)}

        return False


def has_logged(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        if request.env.user.id == request.env.ref("base.public_user").id:
            # Devolver una respuesta HTTP completa
            return request.render(
                "web.login", {"error": _("Please contact the administrator to send you an user.")}
            )
        return func(self, *args, **kwargs)

    return wrap
