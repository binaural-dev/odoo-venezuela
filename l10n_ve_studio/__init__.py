from . import models


def post_init_hook(env):
    Module = env["ir.module.module"]
    studio_module = Module.search([("name", "=", "web_studio"), ("state", "=", "installed")])
    if studio_module:
        studio_module.button_uninstall()
