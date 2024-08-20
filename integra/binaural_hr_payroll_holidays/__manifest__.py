{
    "name": "Binaural Nómina con Ausencias",
    "summary": """Personalizaciones de nómina y ausencias para Venezuela""",
    "author": "Binauraldev",
    "license": "LGPL-3",
    "website": "https://www.binauraldev.com",
    "category": "Payroll Localization",
    "version": "16.0.1.0.2",
    # any module necessary for this one to work correctly
    "depends": [
        "binaural_hr_payroll",
        "hr_payroll_holidays",
        "hr_holidays",
        "hr_work_entry_holidays",
    ],
    # always loaded
    "data": [
        "data/ir_cron.xml",
        "data/hr_leave_type.xml",
        "data/hr_work_entry_type.xml",
        "views/hr_leave_type.xml",
    ],
    "binaural": True,
}
