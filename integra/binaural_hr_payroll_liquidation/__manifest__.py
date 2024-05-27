{
    "name": "Binaural Nómina Liquidaciones",
    "summary": """
        Modificaciones de nómina para liquidaciones y pagos de prestaciones en Venezuela.
    """,
    "author": "Binauraldev",
    "website": "https://www.binauraldev.com",
    "category": "Human Resources",
    "version": "16.0.1.0.1",
    # any module necessary for this one to work correctly
    "depends": ["binaural_hr_payroll"],
    # always loaded
    "data": [
        "data/ir_cron.xml",
        "security/ir.model.access.csv",
        "views/hr_payroll_benefits_accumulated.xml",
        "views/hr_payroll_benefits_accumulated_detail.xml",
        "views/hr_payslip.xml",
        "views/menuitems.xml",
    ],
}
