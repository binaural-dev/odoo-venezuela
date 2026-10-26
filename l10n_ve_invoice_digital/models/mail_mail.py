from odoo import fields, models, modules


class MailMail(models.Model):
    _inherit = "mail.mail"

    # Marca los mail.mail creados por el flujo de digitalización TFHKA (ver
    # tfhka.document.service._send_digitalization_email). No se muestra en
    # ninguna vista: es un campo interno de control, no una configuración de
    # usuario.
    #
    # Por qué existe: process_email_queue() nativo (odoo/addons/mail/models/
    # mail_mail.py) reporta a ir.cron cuántos correos quedan pendientes en
    # TODO el dominio 'outgoing' cuando batch_size ya se alcanzó. Como el
    # runner de ir.cron (odoo/addons/base/models/ir_cron.py, _run_job) vuelve
    # a ejecutar el mismo código mientras queden pendientes -- hasta
    # MIN_RUNS_PER_JOB=10 iteraciones o MIN_TIME_PER_JOB=10s --, terminaba
    # vaciando toda la cola en una sola ejecución del cron sin importar el
    # batch_size configurado. Los correos marcados aquí se procesan aparte,
    # respetando batch_size como tope real por ejecución.
    tfhka_digitalization_email = fields.Boolean(default=False)

    def process_email_queue(self, email_ids=(), batch_size=1000):
        if not email_ids:
            digital_domain = [
                ("tfhka_digitalization_email", "=", True),
                ("state", "=", "outgoing"),
                "|",
                ("scheduled_date", "=", False),
                ("scheduled_date", "<=", fields.Datetime.now()),
            ]
            digital_mails = self.search(digital_domain, limit=batch_size)
            if digital_mails:
                # No se llama _commit_progress (a través de post_send_callback):
                # así ir.cron ve el ciclo como completado y no reintenta -- lo
                # que quede pendiente se procesa en la próxima ejecución,
                # respetando batch_size al pie de la letra en vez de vaciar
                # toda la cola de una vez.
                digital_mails.send(auto_commit=not modules.module.current_test)
                return digital_mails
        return super().process_email_queue(email_ids=email_ids, batch_size=batch_size)
