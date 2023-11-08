{
    "name": "Binaural Club Socios",
    "summary": """
        Modulo destinado a Socios de un Club
    """,
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Stock",
    "version": "1.1",
    "depends": [
        "base",
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
        "wizard/status_action_batch.xml"

    ],
}
