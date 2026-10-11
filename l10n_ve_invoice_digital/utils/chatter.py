import html

from markupsafe import Markup

STATUS_COLORS = {
    "success": "#28a745",
    "error": "#dc3545",
}


def status_message(body, status):
    """Wrap an already-translated chatter body with a colored underline bar.

    ``body`` must be plain text (e.g. the result of ``_(...)``); it gets
    escaped here before being embedded in the HTML wrapper, so callers never
    need to escape it themselves.
    """
    color = STATUS_COLORS[status]
    return (
        Markup(
            '<div style="border-bottom: 3px solid %s; '
            'display: inline-block; padding-bottom: 2px;">' % color
        )
        + Markup(html.escape(body))
        + Markup("</div>")
    )
