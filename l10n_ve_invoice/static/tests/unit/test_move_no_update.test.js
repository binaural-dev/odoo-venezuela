import { expect, test } from "@odoo/hoot";
import { openKanbanView, openListView, start, startServer } from "@mail/../tests/mail_test_helpers";
import { defineAccountModels } from "@account/../tests/account_test_helpers";

defineAccountModels();

// El botón "Subir"/"Upload" (`.o_button_upload_bill`) es propio del
// controlador (`showUploadButton`, ver account_move_list_controller.js/
// account_move_kanban_controller.js core), no depende del `create` de la
// vista -- por eso las Notas de Crédito/Débito lo apagan por contexto
// (`l10n_ve_no_upload: True`, ver views/account_move.xml) y nuestro parche
// (static/src/js/account_move_list, account_move_kanban) es lo único
// que lo hace efectivo.

test("l10n_ve_no_upload=True oculta el botón Subir en la vista lista de account.move", async () => {
    await startServer();
    await start();
    await openListView("account.move", {
        context: { default_move_type: "out_refund", l10n_ve_no_upload: true },
        arch: `<list js_class="account_tree"><field name="name"/></list>`,
    });
    expect(document.querySelector(".o_button_upload_bill")).toBe(null);
});

test("sin l10n_ve_no_upload, el botón Subir se muestra normalmente en la vista lista", async () => {
    await startServer();
    await start();
    await openListView("account.move", {
        context: { default_move_type: "out_invoice" },
        arch: `<list js_class="account_tree"><field name="name"/></list>`,
    });
    expect(document.querySelector(".o_button_upload_bill")).not.toBe(null);
});

test("l10n_ve_no_upload=True oculta el botón Subir en la vista kanban de account.move", async () => {
    await startServer();
    await start();
    await openKanbanView("account.move", {
        context: { default_move_type: "in_refund", l10n_ve_no_upload: true },
        arch: `<kanban js_class="account_documents_kanban">
            <templates>
                <t t-name="card">
                    <field name="name"/>
                </t>
            </templates>
        </kanban>`,
    });
    expect(document.querySelector(".o_button_upload_bill")).toBe(null);
});

test("sin l10n_ve_no_upload, el botón Subir se muestra normalmente en la vista kanban", async () => {
    await startServer();
    await start();
    await openKanbanView("account.move", {
        context: { default_move_type: "in_invoice" },
        arch: `<kanban js_class="account_documents_kanban">
            <templates>
                <t t-name="card">
                    <field name="name"/>
                </t>
            </templates>
        </kanban>`,
    });
    expect(document.querySelector(".o_button_upload_bill")).not.toBe(null);
});