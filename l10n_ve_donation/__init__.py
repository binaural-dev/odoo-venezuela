from . import models


def _post_init_hook(env):
    """The administrator and the superuser are Donation Managers when the
    module is installed (not in every update: whoever removes them from the
    group keeps them out)."""
    group = env.ref("l10n_ve_donation.group_donation_manager")
    group.user_ids |= env.ref("base.user_root") | env.ref("base.user_admin")
