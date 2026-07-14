# Matriz de Pruebas - Hito POS 17 Maquina Fiscal

## Alcance

Esta matriz consolida pruebas automatizadas (QUnit con `MockSerialConnection`) y pruebas funcionales UAT para el hito de integracion POS 17 + TFHKA Web Serial.

## Ejecucion de Referencia

- Comando ejecutado en contenedor Odoo 17:

```bash
docker exec "odoo-odoo17" odoo -d "bd17" --workers=0 --http-port=8079 --test-enable --test-tags="tfhka_driver_tests" --stop-after-init
```

- Resultado observado:
  - El backend arranca correctamente.
  - `0 post-tests` / `0 tests` (esperado para tests JS QUnit que no se ejecutan por `--test-tags` de Python).

- Ejecucion correcta de QUnit JS (recomendada para esta suite):

```text
http://localhost:8117/web/tests?mod=web&failfast
```

## Como correr tests JS en pipeline (CI)

Esta suite es JS/QUnit del frontend POS. No se ejecuta con `--test-tags` de tests Python.

### Opcion recomendada (headless navegador)

1. Levantar Odoo 17 en modo test (`workers=0`) y exponer HTTP de pruebas.
2. Ejecutar el endpoint de QUnit en modo headless.
3. Fallar el job si hay cualquier test en rojo.

Ejemplo de URL objetivo en CI:

```text
http://127.0.0.1:8117/web/tests?mod=web&failfast
```

### Ejemplo Playwright (smoke de QUnit)

```bash
node -e '
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8117/web/tests?mod=web&failfast", { waitUntil: "networkidle" });
  await page.waitForFunction(() => {
    const done = document.querySelector("#qunit-testresult")?.textContent || "";
    return /completed/i.test(done);
  }, { timeout: 300000 });
  const summary = await page.$eval("#qunit-testresult", (el) => el.textContent || "");
  console.log(summary.trim());
  const failed = /\b(\d+)\s+failed\b/i.exec(summary);
  await browser.close();
  if (failed && Number(failed[1]) > 0) process.exit(1);
})();'
```

### Nota de integracion CI

- Mantener `--workers=0` para evitar conflictos en tests.
- Ejecutar contra base de datos de pruebas (no productiva).
- Si el pipeline corre en Docker, exponer el puerto HTTP interno del contenedor de Odoo para el runner headless.

## Snippets listos para CI

### GitHub Actions (job)

```yaml
jobs:
  pos-js-qunit:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: Levantar stack Odoo
        run: |
          ./odoo start 17

      - name: Esperar Odoo (8117)
        run: |
          python - <<'PY'
          import time, urllib.request
          url = 'http://127.0.0.1:8117/web/login'
          for _ in range(120):
              try:
                  with urllib.request.urlopen(url, timeout=2):
                      print('Odoo listo')
                      raise SystemExit(0)
              except Exception:
                  time.sleep(2)
          raise SystemExit('Timeout esperando Odoo')
          PY

      - name: Configurar Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Instalar Playwright Chromium
        run: |
          npm install --no-save playwright
          npx playwright install --with-deps chromium

      - name: Ejecutar QUnit POS (headless)
        run: |
          node -e '
            const { chromium } = require("playwright");
          (async () => {
            const browser = await chromium.launch({ headless: true });
            const page = await browser.newPage();
            await page.goto("http://127.0.0.1:8117/web/tests?mod=web&failfast", { waitUntil: "networkidle" });
            await page.waitForFunction(() => {
              const done = document.querySelector("#qunit-testresult")?.textContent || "";
              return /completed/i.test(done);
            }, { timeout: 300000 });
            const summary = await page.$eval("#qunit-testresult", (el) => el.textContent || "");
            console.log(summary.trim());
            const failed = /\b(\d+)\s+failed\b/i.exec(summary);
            await browser.close();
            if (failed && Number(failed[1]) > 0) process.exit(1);
          })();'

      - name: Apagar stack
        if: always()
        run: |
          ./odoo stop 17
```

### GitLab CI (job)

```yaml
pos_js_qunit:
  stage: test
  image: mcr.microsoft.com/playwright:v1.54.1-jammy
  timeout: 30m
  script:
    - ./odoo start 17
    - |
      python - <<'PY'
      import time, urllib.request
      url = 'http://127.0.0.1:8117/web/login'
      for _ in range(120):
          try:
              with urllib.request.urlopen(url, timeout=2):
                  print('Odoo listo')
                  raise SystemExit(0)
          except Exception:
              time.sleep(2)
      raise SystemExit('Timeout esperando Odoo')
      PY
    - |
      node -e '
      const { chromium } = require("playwright");
      (async () => {
        const browser = await chromium.launch({ headless: true });
        const page = await browser.newPage();
        await page.goto("http://127.0.0.1:8117/web/tests?mod=web&failfast", { waitUntil: "networkidle" });
        await page.waitForFunction(() => {
          const done = document.querySelector("#qunit-testresult")?.textContent || "";
          return /completed/i.test(done);
        }, { timeout: 300000 });
        const summary = await page.$eval("#qunit-testresult", (el) => el.textContent || "");
        console.log(summary.trim());
        const failed = /\b(\d+)\s+failed\b/i.exec(summary);
        await browser.close();
        if (failed && Number(failed[1]) > 0) process.exit(1);
      })();'
  after_script:
    - ./odoo stop 17 || true
```

## Matriz de Pruebas Unitarias (QUnit + Mock)

| ID | Escenario | Tipo | Precondicion | Pasos | Resultado Esperado | Evidencia |
|---|---|---|---|---|---|---|
| UT-01 | Impresion de factura | Automatizada | Driver con `MockSerialConnection`, S1 mockeado | Ejecutar `printInvoice` con cliente, lineas y pagos | `success=true`, retorna `invoiceNumber`, `serial`, `reportZ` | `static/src/tests/tfhka_driver_tests.js` |
| UT-02 | Impresion de nota de credito | Automatizada | Driver conectado, `invoice_affected` valido, S1 mock NC | Ejecutar `printCreditNote` | `success=true`, sin `PH01`, secuencia `iR* iS* iF* iI* iD*`, retorna nro NC | `static/src/tests/tfhka_driver_tests.js` |
| UT-03 | Calculo/formato de impuestos | Automatizada | Orden con tax codes 0 y 2 (extendible a 1 y 3) | Ejecutar `printInvoice` y validar comandos enviados | Lineas fiscales con prefijos correctos (` `, `!`, `"`, `#`) y padding TFHKA | `static/src/tests/tfhka_driver_tests.js` |
| UT-04 | Metodos de pago correctos | Automatizada | Orden con pagos mixtos `01` y `02` | Ejecutar `printInvoice` | Envia parciales `2XX` y cierre `1XX` con metodo principal por mayor monto | `static/src/tests/tfhka_driver_tests.js` |
| UT-05 | Error de conexion a maquina | Automatizada | Driver con `isConnected=false` | Ejecutar `printInvoice` | `success=false` y mensaje de impresora no conectada | `static/src/tests/tfhka_driver_tests.js` |

## Matriz de Pruebas Funcionales UAT (Caja)

| ID | Escenario | Tipo | Precondicion | Pasos | Resultado Esperado | Evidencia |
|---|---|---|---|---|---|---|
| UAT-01 | Factura fiscal end-to-end | Manual | POS abierto, impresora conectada, cliente con RIF | Crear venta y validar pago | Factura impresa, pedido guarda nro fiscal, serial y Z afectado | Ticket + consola POS |
| UAT-02 | Nota de credito con factura afectada | Manual | Existe factura fiscal previa | Reembolsar desde TicketScreen | NC impresa sin NAK, con `iF*`, `iI*`, `iD*` correctos | Ticket NC + consola POS |
| UAT-03 | Reporte X en cierre de sesion | Manual | POS en estado operativo | Click en `Reporte X` | Imprime reporte, no cierra dia fiscal | Papel impreso + consola |
| UAT-04 | Reporte Z en cierre de sesion | Manual | POS en estado operativo | Click en `Reporte Z`, confirmar | Imprime reporte Z y sincroniza `account.move.report_z` + `pos.session.report_z` | Papel + DB/registro Odoo |
| UAT-05 | Proteccion doble clic en X/Z | Manual | Popup de cierre visible | Hacer multiples clics rapidos | Botones se bloquean y muestran `Imprimiendo...` hasta fin/error | Video/captura UI |
| UAT-06 | Modo offline-first | Manual | Simular caida de internet, impresora conectada localmente | Facturar y reconectar | Impresion fiscal ocurre offline, luego sincroniza con Odoo | Cola local + logs |
| UAT-07 | Error de conexion impresora | Manual | Desconectar cable o apagar impresora | Intentar facturar o imprimir X/Z | Popup de error de conexion, sin envio parcial de documento | Popup + logs |

## Criterios de Aprobacion del Hito

1. UT-01..UT-05 verdes en QUnit.
2. UAT-01..UAT-07 completadas en caja de pruebas.
3. Sin errores bloqueantes en consola POS ni logs Odoo durante escenarios nominales.
4. Evidencia documentada (capturas/logs) anexada al ticket de release.
