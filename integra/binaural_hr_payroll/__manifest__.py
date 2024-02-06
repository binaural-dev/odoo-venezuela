{
    "name": "Binaural Nómina",
    "summary": """Personalizaciones de nómina para Venezuela""",
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Payroll Localization",
    "version": "16.0.1.3.0",
    # any module necessary for this one to work correctly
    "depends": ["hr", "hr_payroll", "binaural_rate"],
    # always loaded
    "data": [
        "data/hr_work_entry_type.xml",
        "data/resource_calendar.xml",
        "data/hr_payroll_structure_type.xml",
        "security/ir.model.access.csv",
        "views/hr_contract.xml",
        "views/hr_employee.xml",
        "views/hr_payroll_move.xml",
        "views/hr_payroll_structure.xml",
        "views/hr_payslip.xml",
        "views/hr_payslip_run.xml",
        "views/hr_salary_rule.xml",
        "views/res_config_settings.xml",
        "views/menuitems.xml",
    ],
}
