{
    "name": "Binaural Club Socios",
    "summary": """
        Modulo destinado a Socios de un Club
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "16.0.1.0.8",
    "depends": [
        "base",
        "base_automation",
        "binaural_rate",
        "binaural_contact",
        "account",
        "account_accountant",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/action_partner.xml",
        "views/res_partner.xml",
        "views/partner_profession.xml",
        "views/associate_list.xml",
        "views/partner_config.xml",
        "views/account_payment.xml",
        "views/account_move.xml",
        "views/family_members.xml",
        "views/pending_debt_list.xml",
        "views/insolvent_partner.xml",
        "views/member_in_debt_report.xml",
        "wizard/status_action_batch.xml",
        "wizard/establish_extension.xml",
        "wizard/suspend_partner.xml",
        "wizard/remove_suspend_partner.xml",
        "data/cron.xml"

    ],
    "binaural":True,
}
