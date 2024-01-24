{
    "name": "Binaural Nómina",
    "summary": """Personalizaciones de nómina para Venezuela""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Payroll Localization",
    "version": "16.0.1.0.2",
    # any module necessary for this one to work correctly
    "depends": ["hr", "hr_payroll", "binaural_rate"],
    # always loaded
    "data": [
        "data/hr_work_entry_type.xml",
        "data/resource_calendar.xml",
        "data/hr_payroll_structure_type.xml",
        "views/hr_contract.xml",
        "views/res_config_settings.xml",
        "views/hr_payslip.xml",
        "views/hr_payslip_run.xml",
        "views/hr_salary_rule.xml",
    ],
}
