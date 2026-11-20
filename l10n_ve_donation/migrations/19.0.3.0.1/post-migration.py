from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Two records of the module are `noupdate`, so the databases that already
    have it keep their old values:

    - The Donation Manager group has a privilege of its own (inside the
      Accounting privilege it was one more option of the same selector of the
      user form and saving the user with another level removed it; without
      privilege it is only drawn in developer mode). The group is moved to the
      new privilege and its record is released to be updated.
    - The paper format of the Donation Certificate is Letter size (it was A4):
      it is changed only if it still is A4, so that a format that somebody
      chose on purpose is left alone.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("l10n_ve_donation.group_donation_manager", raise_if_not_found=False)
    privilege = env.ref("l10n_ve_donation.res_groups_privilege_donation", raise_if_not_found=False)
    if group and privilege:
        group.privilege_id = privilege
    cr.execute(
        """
        UPDATE ir_model_data SET noupdate = FALSE
         WHERE module = 'l10n_ve_donation' AND name = 'group_donation_manager'
           AND model = 'res.groups'
        """
    )
    paperformat = env.ref(
        "l10n_ve_donation.paperformat_donation_certificate", raise_if_not_found=False
    )
    if paperformat and paperformat.format == "A4":
        paperformat.format = "Letter"
