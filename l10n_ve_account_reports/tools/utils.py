def get_is_foreign_currency(env):
    """
    Utility function to determine if a report is in foreign currency or not.

    Returns
    -------
    bool
        Whether the report is in foreign currency or not.
    """
    foreign_currency_id = env.company.currency_foreign_id.id
    base_vef_id = env["ir.model.data"]._xmlid_to_res_id("base.VEF", raise_if_not_found=False)
    usd_report = env.context.get("usd_report", False)

    return (foreign_currency_id != base_vef_id and usd_report) or (
        foreign_currency_id == base_vef_id and not usd_report
    )
