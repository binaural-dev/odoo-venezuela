import ast

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_no_upload")
class TestNoUploadCreditDebitNoteActions(TransactionCase):
    """Las notas de crédito/débito siempre deben originarse desde su
    factura de origen (vía el botón nativo Credit Note/Debit Note), nunca
    creándose ni subiéndose (OCR) directo desde sus propias vistas List/
    Kanban. El `create="false"` en esas vistas ya bloquea el botón
    "Nuevo", pero el botón "Subir"/"Upload" es propio del controlador
    (`AccountMoveListController`/`AccountMoveKanbanController`) y no
    depende de `create` -- se apaga vía el contexto `no_upload`, leído por
    los parches en `static/src/views/account_move_list` y
    `account_move_kanban`. Este test confirma que esas 3 acciones siguen
    llevando `no_upload: True` en su contexto (si alguien las vuelve a
    heredar y pisa el `context` completo, el botón reaparecería sin que
    ningún test lo detecte)."""

    def _assert_no_upload(self, xml_id):
        action = self.env.ref(xml_id)
        context = ast.literal_eval(action.context or "{}")
        self.assertTrue(
            context.get("no_upload"),
            "La acción %s debe llevar 'no_upload': True en su contexto "
            "para que el botón Subir/Upload quede oculto en su vista "
            "List/Kanban." % xml_id,
        )

    def test_action_move_in_refund_type_has_no_upload(self):
        self._assert_no_upload("account.action_move_in_refund_type")

    def test_action_move_out_refund_type_has_no_upload(self):
        self._assert_no_upload("account.action_move_out_refund_type")

    def test_action_move_out_refund_type_non_legacy_has_no_upload(self):
        self._assert_no_upload("account.action_move_out_refund_type_non_legacy")
