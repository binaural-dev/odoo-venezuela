import test from "node:test";
import assert from "node:assert/strict";

import {
  FISCAL_PRINT_CLASSIFICATION,
  classifyFiscalPrintResponse,
  getFiscalTripletFromJSON,
  getMissingFiscalFields,
  hasCompleteFiscalTriplet,
} from "../static/src/js/fiscal_payload_utils.js";

test("rehidratación fiscal toma mf_reportz desde JSON", () => {
  const payload = getFiscalTripletFromJSON({
    fiscal_machine: "FM-01",
    mf_invoice_number: "000123",
    mf_reportz: "Z-99",
  });

  assert.equal(payload.mf_reportz, "Z-99");
  assert.equal(payload.fiscal_machine, "FM-01");
  assert.equal(payload.mf_invoice_number, "000123");
});

test("detección de tripleta incompleta reporta faltantes", () => {
  const missing = getMissingFiscalFields({
    fiscal_machine: "FM-01",
    mf_invoice_number: "000123",
    mf_reportz: false,
  });

  assert.deepEqual(missing, ["mf_reportz"]);
  assert.equal(
    hasCompleteFiscalTriplet({
      fiscal_machine: "FM-01",
      mf_invoice_number: "000123",
      mf_reportz: false,
    }),
    false
  );
});

test("clasificación: impreso sin tripleta confirmada => falla", () => {
  const classification = classifyFiscalPrintResponse({
    valid: true,
    pending_sync: true,
    fiscal_pending_reason: "mf_s1_missing",
  });

  assert.equal(classification.type, FISCAL_PRINT_CLASSIFICATION.PRINT_FAILED);
  assert.equal(classification.printer_connection, false);
});

test("clasificación: falla real de impresión", () => {
  const classification = classifyFiscalPrintResponse({
    valid: false,
    message: "Puerto ocupado",
  });

  assert.equal(classification.type, FISCAL_PRINT_CLASSIFICATION.PRINT_FAILED);
  assert.equal(classification.printer_connection, false);
});
