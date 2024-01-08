{
    "name": "Binaural Nómina",
    "summary": """Personalizaciones de nómina para Venezuela""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Payroll Localization",
    "version": "16.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["hr_payroll", "binaural_rate"],
    # always loaded
    "data": [
        "views/hr_contract.xml",
        "views/res_config_settings.xml",
        "views/hr_payslip.xml",
    ],
}
