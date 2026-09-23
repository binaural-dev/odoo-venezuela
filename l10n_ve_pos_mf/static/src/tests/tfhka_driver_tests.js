/** @odoo-module */

import { registry } from "@web/core/registry";
import { FiscalProtocol } from "@l10n_ve_mf_base/core/FiscalProtocol";
import { StatusParser } from "@l10n_ve_mf_base/core/StatusParser";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";
import { composeDiscountPercent, computeLineDiscountAmount } from "@l10n_ve_mf_base/core/DiscountMath";
import { MockSerialConnection } from "./MockSerialConnection";

function buildS1Payload({
    lastInvoiceNumber = 0,
    lastNCNumber = 0,
    dailyClosureCounter = 0,
    serialMachine = "Z1F0000000",
    rif = "J123456789",
}) {
    const fields = [
        "01",
        "000000000000",
        String(lastInvoiceNumber).padStart(8, "0"),
        "00000001",
        "00000000",
        "00000000",
        String(dailyClosureCounter),
        "00000000",
        rif,
        serialMachine,
        "120000",
        "200626",
        String(lastNCNumber).padStart(8, "0"),
        "00000001",
    ];

    return `S1${fields.join("\n")}`;
}

/**
 * Suite de Tests para el Driver de Máquina Fiscal TFHKA
 * 
 * Tests implementados:
 * 1. Cálculo correcto de LRC (XOR checksum)
 * 2. Parsing de tramas con STX/ETX/LRC
 * 3. Reintentos automáticos ante NAK
 * 4. Detección de error de papel (STS2 bit 6)
 * 5. Detección de memoria fiscal llena (STS1 bit 4)
 * 6. Factura completa exitosa
 */

// ============ TESTS DE PROTOCOLO (FiscalProtocol) ============

QUnit.module("TFHKA - FiscalProtocol");

QUnit.test("Cálculo correcto de LRC (XOR checksum)", (assert) => {
    // Test 1: Comando simple "I0X" (Reporte X)
    const frame1 = FiscalProtocol.buildFrame("I0X");
    
    // La trama debe ser: STX + 'I' + '0' + 'X' + ETX + LRC
    assert.strictEqual(frame1[0], 0x02, "Inicia con STX (0x02)");
    assert.strictEqual(frame1[1], 0x49, "Contiene 'I' (0x49)");
    assert.strictEqual(frame1[2], 0x30, "Contiene '0' (0x30)");
    assert.strictEqual(frame1[3], 0x58, "Contiene 'X' (0x58)");
    assert.strictEqual(frame1[4], 0x03, "Contiene ETX (0x03)");
    
    // Calcular LRC manualmente: 0x49 ^ 0x30 ^ 0x58 ^ 0x03 (sin STX)
    const expectedLRC1 = 0x49 ^ 0x30 ^ 0x58 ^ 0x03;
    assert.strictEqual(frame1[5], expectedLRC1, `LRC correcto: 0x${expectedLRC1.toString(16)}`);
    
    // Test 2: Comando con RIF "@J123456789"
    const frame2 = FiscalProtocol.buildFrame("@J123456789");
    const dataBytes = frame2.slice(1, frame2.length - 1);
    const calculatedLRC = FiscalProtocol.calculateLRC(dataBytes);
    assert.strictEqual(frame2[frame2.length - 1], calculatedLRC, "LRC correcto para comando con RIF");
});

QUnit.test("Parsing de respuesta válida con STX/ETX/LRC", (assert) => {
    // Construir una respuesta simulada: STX + "OK" + ETX + LRC
    const encoder = new TextEncoder();
    const data = encoder.encode("OK");
    
    const frameWithoutLRC = new Uint8Array(1 + data.length + 1);
    frameWithoutLRC[0] = FiscalProtocol.STX;
    frameWithoutLRC.set(data, 1);
    frameWithoutLRC[frameWithoutLRC.length - 1] = FiscalProtocol.ETX;
    
    const lrc = FiscalProtocol.calculateLRC(frameWithoutLRC.slice(1));
    const frame = new Uint8Array(frameWithoutLRC.length + 1);
    frame.set(frameWithoutLRC, 0);
    frame[frame.length - 1] = lrc;
    
    // Parsear
    const parsed = FiscalProtocol.parseResponse(frame);
    
    assert.ok(parsed.valid, "Respuesta marcada como válida");
    assert.strictEqual(parsed.data, "OK", "Data extraída correctamente");
    assert.strictEqual(parsed.error, "", "Sin errores");
});

QUnit.test("Parsing de respuesta con LRC inválido", (assert) => {
    // Construir trama con LRC incorrecto
    const frame = new Uint8Array([
        FiscalProtocol.STX,
        0x4F, // 'O'
        0x4B, // 'K'
        FiscalProtocol.ETX,
        0xFF  // LRC inválido (debería ser otro valor)
    ]);
    
    const parsed = FiscalProtocol.parseResponse(frame);
    
    assert.notOk(parsed.valid, "Respuesta marcada como inválida");
    assert.ok(parsed.error.includes("LRC inválido"), "Error de LRC detectado");
});

QUnit.test("Detección de ACK y NAK", (assert) => {
    const ackFrame = new Uint8Array([FiscalProtocol.ACK]);
    const nakFrame = new Uint8Array([FiscalProtocol.NAK]);
    const otherFrame = new Uint8Array([0x42]); // Cualquier otro byte
    
    assert.ok(FiscalProtocol.isACK(ackFrame), "ACK detectado correctamente");
    assert.notOk(FiscalProtocol.isACK(nakFrame), "NAK no es ACK");
    
    assert.ok(FiscalProtocol.isNAK(nakFrame), "NAK detectado correctamente");
    assert.notOk(FiscalProtocol.isNAK(ackFrame), "ACK no es NAK");
    assert.notOk(FiscalProtocol.isNAK(otherFrame), "Otro byte no es NAK");
});

// ============ TESTS DE STATUS PARSER ============

QUnit.module("TFHKA - StatusParser");

QUnit.test("Parser de STS1 (Estado de la impresora)", (assert) => {
    // STS1 = 0x64 (0110 0100)
    // Bit 2 (Modo Fiscal) = 1
    // Bit 5 (Buffer Lleno) = 1
    const sts1 = 0x64;
    const state = StatusParser.parseSTS1(sts1);
    
    assert.ok(state.fiscalMode, "Modo Fiscal detectado");
    assert.ok(state.bufferFull, "Buffer lleno detectado");
    assert.notOk(state.fiscalMemoryFull, "Memoria fiscal no llena");
    assert.ok(state.isFiscalReady, "Estado: Fiscal en espera");
});

QUnit.test("Parser de STS2 (Errores de la impresora)", (assert) => {
    // STS2 = 0x48 (0100 1000)
    // Bit 3 (Gaveta) = 1
    const sts2 = 0x48;
    const errors = StatusParser.parseSTS2(sts2);
    
    assert.ok(errors.drawerError, "Error de gaveta detectado");
    assert.notOk(errors.paperError, "Sin error de papel");
    assert.notOk(errors.criticalError, "Sin error crítico");
    assert.ok(errors.hasDrawerIssue, "Helper: Gaveta con problema");
});

QUnit.test("Detección de error de papel (STS2 bit 6)", (assert) => {
    // STS2 = 0x41 (Sin papel - bit 6 en alto)
    const sts2 = 0x41;
    const errors = StatusParser.parseSTS2(sts2);
    
    assert.ok(errors.paperError, "Error de papel detectado");
    assert.ok(errors.hasPaperIssue, "Helper: Problema de papel");
    assert.notOk(StatusParser.isOperational(0x60, sts2), "Impresora NO operativa por falta de papel");
});

QUnit.test("Detección de memoria fiscal llena (STS1 bit 4)", (assert) => {
    // STS1 = 0x14 (Bit 4 en alto - memoria llena)
    const sts1 = 0x14;
    const state = StatusParser.parseSTS1(sts1);
    
    assert.ok(state.fiscalMemoryFull, "Memoria fiscal llena detectada");
    assert.notOk(StatusParser.isOperational(sts1, 0x40), "Impresora NO operativa por memoria llena");
});

QUnit.test("Estado operativo sin errores", (assert) => {
    // STS1 = 0x60 (Fiscal en espera), STS2 = 0x40 (Sin errores)
    const sts1 = 0x60;
    const sts2 = 0x40;
    
    assert.ok(StatusParser.isOperational(sts1, sts2), "Impresora operativa");
    assert.notOk(StatusParser.hasErrors(sts2), "Sin errores activos");
    
    const statusText = StatusParser.getStatusText(sts1, sts2);
    assert.ok(typeof statusText === "string" && statusText.length > 0, "Texto de status correcto");
});

// ============ TESTS DE DRIVER (TfhkaDriver con Mock) ============

QUnit.module("TFHKA - TfhkaDriver (con MockSerialConnection)");

QUnit.test("Conexión exitosa y lectura de status", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    // Configurar respuesta de status simulada (STS1=0x60, STS2=0x40)
    driver.connection.setNextResponse("STATUS");
    
    const connected = await driver.connect();
    assert.ok(connected, "Driver conectado exitosamente");
    
    const status = await driver.getStatus();
    assert.ok(status, "Status recibido");
    assert.ok(status.raw, "Status contiene datos raw");
});

QUnit.test("Reintentos automáticos ante NAK (3 intentos)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 10; // Reducir delay para testing
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    // Configurar secuencia: NAK, NAK, ACK (éxito al 3er intento)
    driver.connection.setResponseSequence(["NAK", "NAK", "ACK"]);
    
    const result = await driver.sendCommand("I0X");
    
    assert.ok(result.success, "Comando exitoso después de reintentos");
    assert.strictEqual(result.data, "ACK", "Respuesta correcta recibida");
    
    // Verificar que se enviaron 3 comandos
    const commandsHistory = driver.connection
        .getSentCommands()
        .filter((cmd) => !(cmd.raw?.length === 1 && cmd.raw[0] === FiscalProtocol.ENQ));
    assert.strictEqual(commandsHistory.length, 3, "Se enviaron exactamente 3 comandos fiscales");
});

QUnit.test("Fallo después de agotar reintentos (3 NAK seguidos)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 10;
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    // Configurar 3 NAK seguidos (sin ACK)
    driver.connection.setResponseSequence(["NAK", "NAK", "NAK"]);
    
    const result = await driver.sendCommand("I0X");
    
    assert.notOk(result.success, "Comando falló después de reintentos");
    assert.ok(result.error.includes("reintentos"), "Error indica reintentos agotados");
});

QUnit.test("Apertura de gaveta (comando '0')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.openDrawer();
    
    assert.ok(result.success, "Gaveta abierta exitosamente");
    
    // Verificar que se envió el comando correcto
    const lastCommand = driver.connection.getLastCommand();
    assert.ok(lastCommand.text.includes("0"), "Comando '0' enviado");
});

QUnit.test("Impresión de Reporte X (comando 'I0X')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.printReportX();
    
    assert.ok(result.success, "Reporte X impreso exitosamente");
    assert.ok(driver.connection.wasCommandSent("I0X"), "Comando 'I0X' enviado");
});

QUnit.test("Impresión de Reporte Z (comando 'I0Z')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.printReportZ();
    
    assert.ok(result.success, "Reporte Z impreso exitosamente");
    assert.ok(driver.connection.wasCommandSent("I0Z"), "Comando 'I0Z' enviado");
});

QUnit.test("Impresión de factura con impuestos y métodos de pago", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    const mockOrder = {
        partner: {
            vat: "J123456789",
            name: "EMPRESA TEST",
        },
        lines: [
            {
                product_name: "Producto Exento",
                fiscal_code: "0",
                quantity: 1,
                price_unit: 10.0,
            },
            {
                product_name: "Producto Reducido",
                fiscal_code: "2",
                quantity: 1,
                price_unit: 20.0,
            }
        ],
        payment_lines: [
            { payment_method_code: "01", amount: 10.0 },
            { payment_method_code: "02", amount: 20.0 },
        ],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };
    
    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 863,
        dailyClosureCounter: 18,
        serialMachine: "Z1F0022949",
    }));
    
    const result = await driver.printInvoice(mockOrder);
    
    assert.ok(result.success, "Factura impresa exitosamente");
    assert.strictEqual(result.invoiceNumber, "863", "Número de factura retornado desde S1");
    assert.strictEqual(result.serial, "Z1F0022949", "Serial retornado desde S1");
    assert.strictEqual(result.reportZ, 19, "Z afectado calculado desde contador diario");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>iR*J123456789<ETX>")), "RIF enviado");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>iS*EMPRESA TEST<ETX>")), "Razón social enviada");
    assert.ok(asciiHistory.some((cmd) => cmd.startsWith("<STX> 0000001000")), "Línea exenta enviada (tax code 0)");
    assert.ok(asciiHistory.some((cmd) => cmd.startsWith("<STX>\"0000002000")), "Línea reducida enviada (tax code 2)");
    // El método de mayor monto (02, 20.00) es el que cierra con 1XX; el otro (01) va como 2XX.
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>201000000001000<ETX>")), "Pago parcial método 01 (no-cierre) enviado como 2XX");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>202000000002000<ETX>")), "El método de cierre (02) NO se envía como 2XX");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")), "Cierre fiscal con 1XX (102, mayor monto)");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>101<ETX>")), "No cierra con 101 (el método de mayor monto es 02, no 01)");
});

// ============ TESTS DE IGTF (manual TFHKA v1.1.0) ============

QUnit.test("_isDivisaPaymentMethod clasifica códigos 01-19 como nacional y 20-24 como divisa", (assert) => {
    const driver = new TfhkaDriver();

    assert.notOk(driver._isDivisaPaymentMethod("01"), "01 es nacional");
    assert.notOk(driver._isDivisaPaymentMethod("19"), "19 es nacional (límite superior)");
    assert.notOk(driver._isDivisaPaymentMethod("00"), "00 es nacional");
    assert.ok(driver._isDivisaPaymentMethod("20"), "20 es divisa (límite inferior)");
    assert.ok(driver._isDivisaPaymentMethod("24"), "24 es divisa (límite superior)");
    assert.notOk(driver._isDivisaPaymentMethod("25"), "25 fuera de rango IGTF, no es divisa");
    assert.ok(driver._isDivisaPaymentMethod(20), "Acepta número además de string");
});

QUnit.test("_hasDivisaPayment detecta si algún pago de la orden es en divisa", (assert) => {
    const driver = new TfhkaDriver();

    assert.notOk(
        driver._hasDivisaPayment([{ payment_method_code: "01" }, { payment_method_code: "02" }]),
        "Sin divisa si todos los métodos son 01-19"
    );
    assert.ok(
        driver._hasDivisaPayment([{ payment_method_code: "01" }, { payment_method_code: "20" }]),
        "Detecta divisa si al menos un método está en 20-24"
    );
    assert.notOk(driver._hasDivisaPayment([]), "Sin pagos, no hay divisa");
    assert.notOk(driver._hasDivisaPayment(undefined), "payment_lines undefined no rompe, retorna false");
});

QUnit.test("IGTF: pago con divisa cierra con 199 (no con 1XX) y envía TODOS los métodos como 2XX", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const mockOrder = {
        partner: { vat: "J123456789", name: "EMPRESA DIVISA TEST" },
        lines: [
            { product_name: "Producto Gravado", fiscal_code: "1", quantity: 1, price_unit: 100.0 },
        ],
        payment_lines: [
            { payment_method_code: "01", amount: 40.0 },  // nacional (mayor monto, normalmente cerraría con 1XX)
            { payment_method_code: "20", amount: 60.0 },  // DIVISA -> dispara IGTF
        ],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(20).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 900,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(mockOrder);
    assert.ok(result.success, "Factura con pago en divisa impresa exitosamente");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

    // Ambos métodos deben ir como 2XX (incluyendo el de mayor monto, que normalmente
    // cerraría con 1XX si no hubiera divisa involucrada)
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>201000000004000<ETX>")), "Pago nacional 01 enviado como 2XX");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>220000000006000<ETX>")), "Pago en divisa 20 enviado como 2XX");

    // NO debe enviarse ningún cierre directo 1XX (ni 101 ni 120)
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>101<ETX>")), "No se envía 1XX (101) con divisa presente");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>120<ETX>")), "No se envía 1XX (120) con divisa presente");

    // El cierre debe ser el 199 final (siempre presente al cerrar el documento)
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>199<ETX>")), "Cierre con 199 (obligatorio con IGTF)");
});

QUnit.test("Sin divisa: comportamiento normal se mantiene (cierre con 1XX, no 199 de pago)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const mockOrder = {
        partner: { vat: "J123456789", name: "EMPRESA NACIONAL TEST" },
        lines: [
            { product_name: "Producto Gravado", fiscal_code: "1", quantity: 1, price_unit: 100.0 },
        ],
        payment_lines: [
            { payment_method_code: "01", amount: 40.0 },
            { payment_method_code: "02", amount: 60.0 },
        ],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(20).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 901,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(mockOrder);
    assert.ok(result.success, "Factura sin divisa impresa exitosamente");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

    // El de mayor monto (02, 60.00) debe cerrar con 1XX; el otro (01) va como 2XX
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>201000000004000<ETX>")), "Pago no-cierre 01 enviado como 2XX");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>202000000006000<ETX>")), "El método de cierre NO se envía como 2XX");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")), "Cierre directo con 1XX (102, mayor monto)");
});

QUnit.test("_parseS25Data calcula el monto de IGTF como diferencia entre total con y sin IGTF", (assert) => {
    const driver = new TfhkaDriver();

    // Campos: bases, impuesto, totalConIgtf, cantArticulos, totalSinIgtf, cantPagos, tipoDocumento
    const payload = "S2\n0000000010000\n0000000001600\n0000000014980\n000001\n0000000011600\n0001\n1";
    const data = driver._parseS25Data(payload);

    assert.ok(data, "Parseo exitoso");
    assert.strictEqual(data.subtotalBases, 100.0, "Subtotal de bases imponibles correcto");
    assert.strictEqual(data.subtotalTax, 16.0, "Subtotal de impuesto correcto");
    assert.strictEqual(data.totalWithoutIgtf, 116.0, "Monto a pagar sin IGTF correcto");
    assert.strictEqual(data.totalWithIgtf, 149.8, "Monto a pagar incluyendo IGTF correcto");
    assert.strictEqual(data.igtfAmount, 33.8, "IGTF calculado como diferencia (149.80 - 116.00)");
    assert.strictEqual(data.documentType, "1", "Tipo de documento: Factura");
    assert.strictEqual(data.documentTypeLabel, "Factura", "Label de tipo de documento correcto");
});

QUnit.test("_parseS25Data retorna null con payload vacío o insuficiente", (assert) => {
    const driver = new TfhkaDriver();
    assert.strictEqual(driver._parseS25Data(""), null, "Payload vacío retorna null");
    assert.strictEqual(driver._parseS25Data("S2\n123"), null, "Payload con muy pocos campos retorna null");
});

QUnit.test("_formatDisplayAmount formatea con punto de miles y coma decimal (formato venezolano)", (assert) => {
    const driver = new TfhkaDriver();

    assert.strictEqual(driver._formatDisplayAmount(15), "15,00", "Monto simple sin miles");
    assert.strictEqual(driver._formatDisplayAmount(50), "50,00", "Monto simple sin miles (2)");
    assert.strictEqual(driver._formatDisplayAmount(39290.94), "39.290,94", "Monto con miles y decimales");
    assert.strictEqual(driver._formatDisplayAmount(1234567.89), "1.234.567,89", "Monto con múltiples separadores de miles");
    assert.strictEqual(driver._formatDisplayAmount(0), "0,00", "Monto cero");
    assert.strictEqual(driver._formatDisplayAmount(999.5), "999,50", "Redondeo a 2 decimales");
    assert.strictEqual(driver._formatDisplayAmount(1000), "1.000,00", "Límite exacto de mil");
});

QUnit.test("Nota de crédito con pago en divisa también cierra con 199 (no 1XX)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const creditNoteOrder = {
        partner: { vat: "V17527041", name: "Cliente NC Divisa" },
        invoice_affected: {
            number: "900",
            serial_machine: "Z1F0022949",
            date: "20/06/2026",
        },
        lines: [
            { product_name: "Producto Devuelto", product_code: "P001", fiscal_code: "1", quantity: 1, price_unit: 60 },
        ],
        payment_lines: [{ payment_method_code: "20", amount: 60 }],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(20).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 900,
        lastNCNumber: 1235,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printCreditNote(creditNoteOrder);
    assert.ok(result.success, "NC con pago en divisa impresa exitosamente");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>220000000006000<ETX>")), "Pago en divisa enviado como 2XX");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>120<ETX>")), "No se envía cierre directo 1XX con divisa");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>199<ETX>")), "Cierre con 199");
});

QUnit.test("Impresión de nota de crédito con secuencia fiscal correcta", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    const creditNoteOrder = {
        partner: {
            vat: "V17527041",
            name: "Cliente NC",
        },
        invoice_affected: {
            number: "863",
            serial_machine: "Z1F0022949",
            date: "20/06/2026",
        },
        lines: [
            {
                product_name: "Producto Devuelto",
                product_code: "P001",
                fiscal_code: "1",
                quantity: 2,
                price_unit: 50,
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 100 }],
        additional_lines: ["OPERADOR: TEST"],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 863,
        lastNCNumber: 1234,
        dailyClosureCounter: 18,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printCreditNote(creditNoteOrder);

    assert.ok(result.success, "Nota de crédito impresa exitosamente");
    assert.strictEqual(result.invoiceNumber, "1234", "Número de nota de crédito leído desde S1");

    const fiscalCommands = driver.connection
        .getSentCommands()
        .map((cmd) => cmd.ascii)
        .filter((cmd) => cmd.includes("<STX>"));

    assert.notOk(fiscalCommands.some((cmd) => cmd.includes("PH01")), "No se envía PH01 en NC");
    assert.ok(fiscalCommands[0].includes("<STX>iR*V17527041<ETX>"), "NC inicia con iR*");
    assert.ok(fiscalCommands[1].includes("<STX>iS*Cliente NC<ETX>"), "NC continúa con iS*");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>iF*00000863<ETX>")), "Factura afectada enviada en iF*");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>iI*Z1F0022949<ETX>")), "Serial afectado enviado en iI*");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>iD*20/06/2026<ETX>")), "Fecha afectada enviada en iD*");
    // La descripción se trunca a 14 chars: MAX_LINE_LEN(40) - overhead(2 + 10 de
    // precio + 8 de cantidad + 6 de "|P001|") = 14 -> "Producto Devue".
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>d1000000500000002000|P001|Producto Devue<ETX>")), "Línea NC enviada con prefijo d");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>101<ETX>")), "Cierre NC con método de pago correcto");
});

QUnit.test("Código fiscal t0 se mapea como exento", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const orderWithTaxPrefix = {
        partner: {
            vat: "V12345678",
            name: "CLIENTE EXENTO",
        },
        lines: [
            {
                product_name: "Producto Exento Prefijo",
                fiscal_code: "t0",
                quantity: 1,
                price_unit: 10.0,
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 10.0 }],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(20).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 1001,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(orderWithTaxPrefix);
    assert.ok(result.success, "Factura con fiscal_code t0 impresa exitosamente");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
    // La descripción se trunca a 21 chars: MAX_LINE_LEN(40) - overhead(1 + 10
    // de precio + 8 de cantidad, sin código) = 21 -> "Producto Exento Prefi".
    const exemptLine = asciiHistory.find((cmd) => cmd.includes("Producto Exento Prefi"));
    assert.ok(exemptLine && exemptLine.startsWith("<STX> 0000001000"), "La línea se envía como exenta (prefijo espacio)");
    assert.notOk(exemptLine && exemptLine.startsWith("<STX>!0000001000"), "La línea no se envía como gravada (G)");
});

QUnit.test("_applyDiscount aplica porcentaje sobre la base y redondea", (assert) => {
    // Espejo del helper en PosStore._applyDiscount sin requerir PosStore.
    const round = (value, decimals = 2) => Number(Number(value).toFixed(decimals));
    const applyDiscount = (unitPrice, percent) =>
        round(Number(unitPrice || 0) * (1 - Number(percent || 0) / 100));

    assert.strictEqual(applyDiscount(100, 10), 90, "10% sobre 100 → 90.00");
    assert.strictEqual(applyDiscount(100, 0), 100, "0% sobre 100 → 100.00");
    assert.strictEqual(applyDiscount(0, 10), 0, "Cualquier % sobre 0 → 0.00");
    assert.strictEqual(applyDiscount(90, 10), 81, "Cascada: 100 → 90 → 81");
    assert.strictEqual(applyDiscount(99.99, 10), 89.99, "Redondeo a 2 decimales");
    assert.strictEqual(applyDiscount(50, 50), 25, "50% sobre 50 → 25.00");
    assert.strictEqual(applyDiscount(1, 100), 0, "100% sobre 1 → 0.00");
});

QUnit.test("Descuento global (Strategy A) no envía q- y refleja monto en líneas", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    // Strategy A: el PosStore ya aplicó la cascada y la tasa global al price_unit.
    // Cada línea positiva llega con su precio base ya neto de descuento.
    const orderWithGlobalDiscount = {
        partner: {
            vat: "J123456789",
            name: "CLIENTE DESCUENTO",
        },
        lines: [
            {
                product_name: "Producto A",
                product_code: "A001",
                fiscal_code: "1",
                quantity: 1,
                price_unit: 85,   // 100 base - 15% (10% global sobre base 100)
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 85 }],
        global_discount_amount: 15,
        global_discount_rate: 15,
        global_clamped: false,
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(30).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 999,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(orderWithGlobalDiscount);
    assert.ok(result.success, "Factura con descuento global impresa exitosamente");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
    const close101Count = asciiHistory.filter((cmd) => cmd.includes("<STX>101<ETX>")).length;
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>q-")), "No se envía q- con Strategy A");
    // Fallback: esta orden legacy no trae `gross_price_unit`, así que el ítem
    // debe registrarse con `price_unit` (85,00) tal como antes.
    assert.ok(
        asciiHistory.some((cmd) => cmd.startsWith("<STX>!0000008500")),
        "Sin gross_price_unit, printInvoice cae de vuelta a price_unit (85,00)"
    );
    // Sin `line_discount_via_q` (interruptor en OFF, que es el default) la
    // factura sigue emitiendo la línea agregada "DESC. GLOBAL" del pie, tal
    // como en la Estrategia A original.
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL = 15,00<ETX>")),
        "Con el interruptor en OFF la factura conserva la línea agregada DESC. GLOBAL, en el índice i00 y como línea completa"
    );
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("Descuento Global<ETX>")), "No hay línea negativa enviada como item");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>201000000008500<ETX>")), "Pago único no se envía como parcial 2XX");
    assert.strictEqual(close101Count, 1, "Pago único con método 01 envía 101 una sola vez");
    assert.strictEqual(result.global_discount_amount, 15, "Monto del descuento global retornado al caller");
    assert.strictEqual(result.global_discount_rate, 15, "Tasa del descuento global retornada al caller");
    assert.notOk(result.global_clamped, "Sin clamp en este caso");
});

QUnit.test("Descuento global (Strategy A) emite aviso adicional cuando es clampado", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const orderWithClampedDiscount = {
        partner: {
            vat: "J123456789",
            name: "CLIENTE DESCUENTO",
        },
        lines: [
            {
                product_name: "Producto A",
                product_code: "A001",
                fiscal_code: "1",
                quantity: 1,
                price_unit: 0,    // Base reducida al 100% por el clamp del PosStore
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 0 }],
        global_discount_amount: 50,
        global_discount_rate: 100,
        global_clamped: true,
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(30).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 1000,
        dailyClosureCounter: 21,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(orderWithClampedDiscount);
    assert.ok(result.success, "Factura con descuento clampado impresa");

    const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
    // Interruptor en OFF (default): la factura conserva las dos líneas
    // agregadas de la Estrategia A y además devuelve el aviso al caller.
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL = 50,00<ETX>")),
        "La factura emite la línea informativa DESC. GLOBAL en i00, como línea completa"
    );
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i01DESC. GLOBAL EXCEDIO SUBTOTAL<ETX>")),
        "La factura emite la línea de aviso por clamp en i01, como línea completa"
    );
    assert.ok(result.global_clamped, "Bandera global_clamped=true hacia el caller");
    assert.strictEqual(
        result.global_discount_amount,
        50,
        "El monto del descuento global se sigue devolviendo al caller"
    );
});

// ============ TESTS DE DESCUENTO POR LÍNEA (Estrategia C, comando q-) ============
//
// NOTA: Ninguno de estos tests prueba hardware real. Verifican que el driver
// CONSTRUYA la trama correcta. Que la impresora TFHKA física acepte `q-` tras
// un ítem con ACK sigue pendiente de validación con equipo real — por eso el
// interruptor `mf_line_discount_via_q_command` nace en OFF. Ver
// DISCOUNT_STRATEGY.md, sección "Riesgo abierto".

/** Historial de comandos fiscales (descarta los frames ENQ de status). */
function fiscalAscii(driver) {
    return driver.connection
        .getSentCommands()
        .map((cmd) => cmd.ascii)
        .filter((cmd) => cmd.startsWith("<STX>"));
}

function buildLineDiscountOrder(lines) {
    return {
        partner: { vat: "J123456789", name: "CLIENTE DESC LINEA" },
        lines,
        payment_lines: [{ payment_method_code: "01", amount: 100 }],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
        // Interruptor `mf_line_discount_via_q_command` en ON. Con el default
        // (OFF / ausente) el driver ignora `gross_price_unit`/`discount_amount`
        // — eso lo cubre el test "interruptor en OFF" más abajo.
        line_discount_via_q: true,
    };
}

/** Driver con MockSerialConnection listo para imprimir. */
async function buildConnectedDriver() {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;
    await driver.connection.requestPort();
    driver.isConnected = true;
    return driver;
}

async function primeDriver(driver, invoiceNumber = 1100) {
    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(40).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: invoiceNumber,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));
}

QUnit.test("Estrategia C: q- se emite justo después de su ítem, con el precio BRUTO y el monto exacto", async (assert) => {
    const driver = await buildConnectedDriver();

    const order = buildLineDiscountOrder([
        {
            product_name: "PROD DESC",
            product_code: "A001",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 85,            // neto (lo usan NC/ND, aquí NO debe usarse)
            gross_price_unit: 100,     // bruto (lo usa printInvoice)
            discount_amount: 15,       // monto EXACTO en Bs, calculado en Odoo
        },
    ]);

    await primeDriver(driver, 1100);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura con descuento de línea impresa");

    const history = fiscalAscii(driver);
    const itemIndex = history.findIndex((cmd) => cmd.includes("PROD DESC"));
    assert.ok(itemIndex >= 0, "El ítem fue enviado");

    // Flag 21 = "00": precio 8 enteros + 2 decimales, cantidad 5 + 3.
    assert.ok(
        history[itemIndex].startsWith("<STX>!0000010000" + "00001000"),
        "El ítem se registra con el precio BRUTO (100,00), no con el neto (85,00)"
    );
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>!0000008500")),
        "El precio neto (85,00) no se envía como precio del ítem en la factura"
    );

    // q- inmediatamente DESPUÉS del ítem (el protocolo lo aplica al ítem previo).
    // OJO: `ascii` incluye el byte LRC al final de la trama (ej.
    // "<STX>q-000001500<ETX>Z"), por eso se compara con startsWith y no con
    // strictEqual. Flag 21 = "00" -> disc_int 7 + disc_decimal 2.
    assert.ok(
        history[itemIndex + 1].startsWith("<STX>q-000001500<ETX>"),
        "q-000001500 (15,00 Bs) se emite en el comando inmediatamente siguiente al ítem"
    );
    assert.deepEqual(result.line_discount_overflow_lines, [], "Ninguna línea desbordó el campo");

    // Sin descuento global del botón (`global_only_discount_amount` ausente) no
    // hay nada que agregar al pie: el único descuento del pedido es el de
    // campaña, y ya salió impreso bajo su producto.
    assert.notOk(
        history.some((cmd) => cmd.includes("DESC. GLOBAL")),
        "Sin porción global no se emite la línea agregada del pie"
    );
    assert.strictEqual(
        history.filter((cmd) => cmd.startsWith("<STX>q-")).length,
        1,
        "Un único q-: el de la línea. No hay q- agregado tras el subtotal"
    );
});

QUnit.test("Estrategia C: el formato del monto de q- SÍ depende del Flag 21", async (assert) => {
    // Manual V8.5.0, Tabla 22 págs. 27-28 ("DESCUENTO Y RECARGO POR MONTO"):
    // los dígitos del monto los fija el Flag 21. Es el MISMO formato que ya usa
    // el descuento global agregado de NC/ND (`config.disc_int`/`disc_decimal`).
    const cases = [
        // flag "00" -> disc_int 7, disc_decimal 2
        { flag21: "00", amount: 15, expected: "<STX>q-000001500<ETX>" },
        { flag21: "00", amount: 7.5, expected: "<STX>q-000000750<ETX>" },
        { flag21: "00", amount: 1234.56, expected: "<STX>q-000123456<ETX>" },
        // flag "02" comparte el mismo bloque de descuento que "00"
        { flag21: "02", amount: 15, expected: "<STX>q-000001500<ETX>" },
        // flag "30" -> disc_int 15, disc_decimal 2 (trama MÁS LARGA: prueba
        // que el formato NO es fijo, a diferencia del viejo comando p-)
        { flag21: "30", amount: 15, expected: "<STX>q-00000000000001500<ETX>" },
        { flag21: "30", amount: 1234.56, expected: "<STX>q-00000000000123456<ETX>" },
    ];

    for (const testCase of cases) {
        const driver = await buildConnectedDriver();

        const order = buildLineDiscountOrder([
            {
                product_name: "Producto Flag",
                fiscal_code: "1",
                quantity: 1,
                gross_price_unit: 2000,
                discount_amount: testCase.amount,
            },
        ]);
        order.flag_21 = testCase.flag21;

        await primeDriver(driver, 1101);
        const result = await driver.printInvoice(order);
        assert.ok(result.success, `Factura impresa (flag 21 = ${testCase.flag21})`);

        assert.ok(
            fiscalAscii(driver).some((cmd) => cmd.startsWith(testCase.expected)),
            `Flag 21 = ${testCase.flag21}, ${testCase.amount} Bs -> ${testCase.expected}`
        );
    }
});

QUnit.test("Estrategia C: una línea sin descuento NO genera comando q-", async (assert) => {
    const driver = await buildConnectedDriver();

    const order = buildLineDiscountOrder([
        {
            product_name: "PROD CERO",
            fiscal_code: "1",
            quantity: 1,
            gross_price_unit: 40,
            discount_amount: 0,            // explícitamente cero
        },
        {
            product_name: "PROD NOAMT",
            fiscal_code: "1",
            quantity: 1,
            gross_price_unit: 30,
            // discount_amount ausente por completo
        },
        {
            product_name: "PROD DESC",
            fiscal_code: "1",
            quantity: 2,
            gross_price_unit: 30,
            discount_amount: 12,           // 20% de 30 x 2 unidades = 12,00 Bs
        },
    ]);

    await primeDriver(driver, 1102);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura mixta impresa");

    const history = fiscalAscii(driver);
    const discountCommands = history.filter((cmd) => cmd.startsWith("<STX>q-"));
    assert.strictEqual(discountCommands.length, 1, "Solo se emite un q-, el de la única línea con descuento");
    assert.ok(
        discountCommands[0].startsWith("<STX>q-000001200<ETX>"),
        "El q- emitido lleva el monto total de la línea (12,00 Bs por 2 unidades), no el unitario"
    );

    // Y está pegado a SU ítem, no a los otros dos.
    const withDiscountIndex = history.findIndex((cmd) => cmd.includes("PROD DESC"));
    assert.ok(history[withDiscountIndex + 1].startsWith("<STX>q-000001200<ETX>"), "q- sigue al ítem correcto");

    const zeroIndex = history.findIndex((cmd) => cmd.includes("PROD CERO"));
    assert.notOk(history[zeroIndex + 1].startsWith("<STX>q-"), "La línea con 0,00 Bs no es seguida de q-");

    const missingIndex = history.findIndex((cmd) => cmd.includes("PROD NOAMT"));
    assert.notOk(history[missingIndex + 1].startsWith("<STX>q-"), "La línea sin discount_amount no es seguida de q-");
});

QUnit.test("Estrategia C: un monto que no cabe en los dígitos del Flag 21 omite el q- y se reporta", async (assert) => {
    const driver = await buildConnectedDriver();

    // Flag 21 = "00" -> disc_int = 7, es decir hasta 9.999.999,99 Bs. Un monto
    // de 10.000.000,00 desbordaría el campo y produciría una trama malformada:
    // el driver debe omitir el q- y dejar el ítem impreso a su precio bruto.
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD ENORME",
            fiscal_code: "1",
            quantity: 1,
            gross_price_unit: 12000000,
            discount_amount: 10000000,
        },
        {
            product_name: "PROD NORMAL",
            fiscal_code: "1",
            quantity: 1,
            gross_price_unit: 100,
            discount_amount: 10,
        },
    ]);

    await primeDriver(driver, 1103);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "La factura se imprime igual, sin trama malformada");

    const history = fiscalAscii(driver);
    const overflowIndex = history.findIndex((cmd) => cmd.includes("PROD ENORME"));
    assert.ok(overflowIndex >= 0, "El ítem que desborda sí se imprime");
    assert.ok(
        history[overflowIndex].startsWith("<STX>!1200000000"),
        "El ítem que desborda se imprime a su precio BRUTO (12.000.000,00)"
    );
    assert.notOk(
        history[overflowIndex + 1].startsWith("<STX>q-"),
        "No se emite ningún q- para la línea que desborda"
    );

    const discountCommands = history.filter((cmd) => cmd.startsWith("<STX>q-"));
    assert.strictEqual(discountCommands.length, 1, "Solo la línea que sí cabe emite q-");
    assert.ok(
        discountCommands[0].startsWith("<STX>q-000001000<ETX>"),
        "La otra línea emite su q- normalmente (10,00 Bs)"
    );

    assert.deepEqual(
        result.line_discount_overflow_lines,
        ["PROD ENORME"],
        "La línea que desbordó se reporta al caller para que el PosStore avise al usuario"
    );
});

QUnit.test("Interruptor en OFF: la factura vuelve al comportamiento histórico (Estrategia A)", async (assert) => {
    const driver = await buildConnectedDriver();

    // MISMA orden que produce _convertOrderForDriver (trae los dos campos
    // nuevos) pero con el interruptor apagado, que es el default del campo
    // `mf_line_discount_via_q_command`.
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD DESC",
            product_code: "A001",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 85,
            gross_price_unit: 100,
            discount_amount: 15,
        },
    ]);
    order.line_discount_via_q = false;
    order.global_discount_amount = 15;
    order.global_discount_rate = 15;
    order.global_clamped = false;

    await primeDriver(driver, 1104);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura impresa con el interruptor en OFF");

    const history = fiscalAscii(driver);
    assert.ok(
        history.some((cmd) => cmd.startsWith("<STX>!0000008500")),
        "El ítem se registra con el precio NETO (85,00), ignorando gross_price_unit"
    );
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>!0000010000")),
        "El precio bruto (100,00) no se envía"
    );
    assert.notOk(history.some((cmd) => cmd.startsWith("<STX>q-")), "No se emite ningún q- por línea");
    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 15,00")),
        "Vuelve la línea agregada DESC. GLOBAL del pie"
    );
    assert.deepEqual(result.line_discount_overflow_lines, [], "Sin líneas desbordadas");
});

QUnit.test("DiscountMath: composición multiplicativa de campaña + global", (assert) => {
    // Función REAL de producción (la misma que usan _applyGlobalDiscountBeforeValidation
    // y _convertOrderForDriver), no una copia espejo.
    assert.strictEqual(composeDiscountPercent(10, 10), 19, "10% + 10% componen 19%, no 20%");
    assert.strictEqual(composeDiscountPercent(0, 15), 15, "Sin campaña, el compuesto es el global");
    assert.strictEqual(composeDiscountPercent(15, 0), 15, "Sin global, el compuesto es el de campaña");
    assert.strictEqual(composeDiscountPercent(0, 0), 0, "Sin descuentos, 0%");
    assert.strictEqual(composeDiscountPercent(50, 50), 75, "50% + 50% componen 75%");
    assert.strictEqual(composeDiscountPercent(100, 50), 100, "100% de campaña absorbe cualquier global");
    assert.strictEqual(composeDiscountPercent(20, 25), 40, "20% + 25% componen 40%");

    // El compuesto debe coincidir con la cascada de precios que calcula
    // _applyDiscount, que es lo que garantiza que el ticket cuadre.
    const composed = composeDiscountPercent(10, 10);
    const cascade = 100 * (1 - 10 / 100) * (1 - 10 / 100);
    assert.strictEqual(
        Number((100 * (1 - composed / 100)).toFixed(2)),
        Number(cascade.toFixed(2)),
        "Aplicar el % compuesto da el mismo neto que aplicar los dos en cascada"
    );
});

QUnit.test("DiscountMath: computeLineDiscountAmount redondea cada total ANTES de restar", (assert) => {
    // Función REAL de producción: la misma que usa
    // PosStore._convertOrderForDriver para poblar `discount_amount`.
    const R = 0.01;
    const amount = (gross, net, qty) =>
        computeLineDiscountAmount({
            grossUnitPrice: gross,
            netUnitPrice: net,
            quantity: qty,
            rounding: R,
        });

    // --- Cantidad ENTERA: el resultado es el "obvio", idéntico al de la
    // fórmula anterior (redondear la diferencia y multiplicar).
    assert.strictEqual(amount(100, 85, 1), 15, "1 x (100 → 85) descuenta 15,00");
    assert.strictEqual(amount(30, 24, 2), 12, "2 x (30 → 24) descuenta 12,00");
    assert.strictEqual(amount(50, 0, 3), 150, "3 x línea regalada descuenta el bruto completo");
    assert.strictEqual(amount(100, 100, 4), 0, "Sin descuento el monto es 0,00");

    // --- Cantidad FRACCIONARIA: aquí es donde importa el orden de las
    // operaciones. 1,5 unidades a 5,00 con 5% de descuento (neto 4,75):
    //   round(5,00 × 1,5) = 7,50      round(4,75 × 1,5) = round(7,125) = 7,13
    //   ✓ nuevo: 7,50 − 7,13 = 0,37
    //   ✗ viejo: round((5,00 − 4,75) × 1,5) = round(0,375) = 0,38
    // Con 0,38 el ticket cerraría en 7,12 y no en los 7,13 que cobra Odoo:
    // un céntimo de descuadre, suficiente para que la impresora rechace el 199.
    assert.strictEqual(amount(5, 4.75, 1.5), 0.37, "1,5 x (5,00 → 4,75) descuenta 0,37 y no 0,38");
    assert.notStrictEqual(
        amount(5, 4.75, 1.5),
        round_pr((5 - 4.75) * 1.5, R),
        "El resultado difiere a propósito de redondear la diferencia unitaria"
    );

    // --- La INVARIANTE que hace cuadrar el ticket, sobre varios casos:
    //     round(bruto × qty) − descuento === round(neto × qty)
    const cases = [
        { gross: 5, net: 4.75, qty: 1.5 },
        { gross: 5.07, net: 4.56, qty: 1.5 },
        { gross: 5.12, net: 4.51, qty: 1.5 },
        { gross: 10, net: 8.55, qty: 1.5 },
        { gross: 19.99, net: 17.99, qty: 2.5 },
        { gross: 7.77, net: 6.99, qty: 0.75 },
        { gross: 100, net: 85, qty: 1 },
        { gross: 30, net: 24, qty: 3 },
    ];
    for (const { gross, net, qty } of cases) {
        // Comparado con 2 decimales: es la precisión con la que el monto viaja
        // a la impresora (`_formatAmount` hace `toFixed`), y evita el ruido de
        // coma flotante de `round_pr` en el lado derecho.
        assert.strictEqual(
            (round_pr(gross * qty, R) - amount(gross, net, qty)).toFixed(2),
            round_pr(net * qty, R).toFixed(2),
            `bruto×${qty} − descuento == round(neto×${qty}) para ${gross} → ${net}`
        );
    }

    // --- Guardas defensivas.
    assert.strictEqual(amount(80, 100, 2), 0, "Un neto MAYOR que el bruto no produce monto negativo");
    assert.strictEqual(
        computeLineDiscountAmount({}),
        0,
        "Sin argumentos útiles el monto es 0 (no NaN)"
    );
    assert.strictEqual(
        computeLineDiscountAmount({ grossUnitPrice: 100, netUnitPrice: 85, quantity: 1 }),
        15,
        "Sin `rounding` explícito se asume la precisión de 0,01"
    );
});

QUnit.test("Estrategia C: con cantidad fraccionaria el q- cuadra exacto con lo que cobra Odoo", async (assert) => {
    const driver = await buildConnectedDriver();

    // 1,5 kg a 5,00 Bs con 5% de descuento. Es el caso donde la fórmula vieja
    // (redondear la diferencia unitaria y multiplicar) daba 0,38 y descuadraba
    // el total de la línea en un céntimo.
    const GROSS = 5;
    const NET = 4.75;
    const QTY = 1.5;
    const discountAmount = computeLineDiscountAmount({
        grossUnitPrice: GROSS,
        netUnitPrice: NET,
        quantity: QTY,
        rounding: 0.01,
    });
    assert.strictEqual(discountAmount, 0.37, "El monto que arma el PosStore es 0,37");

    const order = buildLineDiscountOrder([
        {
            product_name: "PROD KILO",
            fiscal_code: "1",
            quantity: QTY,
            price_unit: NET,
            gross_price_unit: GROSS,
            discount_amount: discountAmount,
        },
    ]);

    await primeDriver(driver, 1106);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura con cantidad fraccionaria impresa");

    const history = fiscalAscii(driver);
    const itemIndex = history.findIndex((cmd) => cmd.includes("PROD KILO"));
    // Flag 21 = "00": precio 8+2 (0000000500) y cantidad 5+3 (00001500).
    assert.ok(
        history[itemIndex].startsWith("<STX>!0000000500" + "00001500"),
        "El ítem va a precio BRUTO 5,00 con cantidad 1,500"
    );
    assert.ok(
        history[itemIndex + 1].startsWith("<STX>q-000000037<ETX>"),
        "El q- lleva 0,37 Bs (no 0,38)"
    );

    // La invariante que evita el NAK del cierre 199: lo que la impresora
    // calcula para la línea (bruto × cantidad − descuento) tiene que ser
    // EXACTAMENTE el total que Odoo cobró por ella.
    assert.strictEqual(
        round_pr(GROSS * QTY, 0.01) - discountAmount,
        round_pr(NET * QTY, 0.01),
        "bruto×qty − q- == round(neto×qty) = 7,13"
    );
    assert.deepEqual(result.line_discount_overflow_lines, [], "Sin desbordamiento de descuento");
    assert.deepEqual(result.line_gross_price_overflow_lines, [], "Sin desbordamiento de precio bruto");
});

QUnit.test("Estrategia C: un precio BRUTO que no cabe en el Flag 21 degrada TODO el documento a precio neto sin q- (C2)", async (assert) => {
    // Actualizado por la revisión formal (C2, ver DISCOUNT_STRATEGY.md): antes
    // sólo la línea que desbordaba se degradaba, y el resto del documento
    // seguía por el camino `q-`. Eso duplicaba el descuento global en la línea
    // degradada (su porción global ya quedaba embebida en el precio neto, y el
    // `q-` agregado del pie la restaba otra vez). Ahora CUALQUIER línea que
    // desborde en precio BRUTO degrada el DOCUMENTO COMPLETO a Estrategia A:
    // ninguna línea emite `q-`, ni siquiera las que sí cabían.
    const driver = await buildConnectedDriver();

    // Flag 21 = "00" -> max_amount_int = 8: hasta 99.999.999,99 por unidad. Un
    // bruto de 120.000.000,00 NO cabe, pero su neto (60.000.000,00) sí: es
    // justo el caso que la guarda del descuento no cubría, porque el camino
    // `q-` es el primero que manda el precio SIN descontar.
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD CARO",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 60000000,
            gross_price_unit: 120000000,
            discount_amount: 60000000,
        },
        {
            product_name: "PROD NORMAL",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 90,
            gross_price_unit: 100,
            discount_amount: 10,
        },
    ]);

    await primeDriver(driver, 1107);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "La factura se imprime igual, sin trama malformada");

    const history = fiscalAscii(driver);
    const degradedIndex = history.findIndex((cmd) => cmd.includes("PROD CARO"));
    assert.ok(degradedIndex >= 0, "La línea que desbordaba sí se imprime");
    assert.ok(
        history[degradedIndex].startsWith("<STX>!6000000000"),
        "La línea que desbordaba se imprime con el precio NETO (60.000.000,00), no con el bruto"
    );
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>!12000000000")),
        "El precio bruto (120.000.000,00) nunca se envía: habría producido un campo de 11 dígitos"
    );
    assert.notOk(
        history[degradedIndex + 1].startsWith("<STX>q-"),
        "La línea que desbordaba NO emite q-"
    );

    const normalIndex = history.findIndex((cmd) => cmd.includes("PROD NORMAL"));
    assert.ok(
        history[normalIndex].startsWith("<STX>!0000009000"),
        "PROD NORMAL, que SÍ cabía, también se degrada a su precio NETO (90,00): todo el documento cae a Estrategia A"
    );
    assert.notOk(
        history[normalIndex + 1]?.startsWith("<STX>q-"),
        "PROD NORMAL tampoco emite q- (C2): si lo hiciera, su porción global ya embebida en el neto se restaría dos veces"
    );

    // Todo comando de ítem respeta el ancho del campo de precio (8 + 2).
    const itemCommands = history.filter((cmd) => /^<STX>[ !"#]\d/.test(cmd));
    for (const cmd of itemCommands) {
        const payload = cmd.slice("<STX>".length + 1);
        assert.ok(
            /^\d{10}\d{8}/.test(payload),
            `El ítem mantiene el ancho de campo del Flag 21 (precio 10 + cantidad 8): ${cmd}`
        );
    }

    const discountCommands = history.filter((cmd) => cmd.startsWith("<STX>q-"));
    assert.strictEqual(discountCommands.length, 0, "Ningún q- se emite en todo el documento (C2)");

    assert.deepEqual(
        result.line_gross_price_overflow_lines,
        ["PROD CARO"],
        "Sólo se reporta la línea que realmente desbordaba (PROD NORMAL se degradó como consecuencia, no por sí misma)"
    );
    assert.deepEqual(
        result.line_discount_overflow_lines,
        [],
        "No se reporta como desbordamiento de descuento: el motivo fue el precio"
    );
    assert.ok(
        result.line_discount_via_q_document_degraded,
        "La bandera de degradación de documento completo llega al caller (C2)"
    );
});

QUnit.test("Estrategia C: la guarda de desbordamiento mira el monto YA REDONDEADO", async (assert) => {
    const driver = await buildConnectedDriver();

    // Flag 21 = "00" -> disc_int = 7. El monto 9.999.999,996 es MENOR que 1e7,
    // así que la comparación cruda `monto < 10 ** disc_int` lo dejaba pasar...
    // pero `_formatAmount` redondea a 2 decimales ANTES de partir el número:
    //   _formatAmount(9999999.996, 7, 2) -> "1000000000" (10 caracteres, no 9)
    // y la trama salía con un dígito de más. La guarda correcta mide la cadena
    // formateada.
    assert.strictEqual(
        driver._formatAmount(9999999.996, 7, 2).length,
        10,
        "El valor del borde SÍ produce una cadena de 10 caracteres tras el redondeo"
    );
    assert.ok(9999999.996 < Math.pow(10, 7), "...y sin embargo es menor que 1e7 (por eso fallaba)");
    assert.notOk(
        driver._amountFitsField(9999999.996, 7, 2),
        "_amountFitsField lo detecta como desbordamiento"
    );
    assert.ok(driver._amountFitsField(9999999.99, 7, 2), "El máximo real (9.999.999,99) sí cabe");

    const order = buildLineDiscountOrder([
        {
            product_name: "PROD BORDE",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 0.004,
            gross_price_unit: 10000000,
            discount_amount: 9999999.996,
        },
    ]);

    await primeDriver(driver, 1108);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "La factura se imprime sin trama malformada");

    const history = fiscalAscii(driver);
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>q-")),
        "No se emite ningún q- para el monto del borde"
    );
    assert.deepEqual(
        result.line_discount_overflow_lines,
        ["PROD BORDE"],
        "La línea del borde se reporta como desbordamiento de descuento"
    );
});

QUnit.test("El aviso de clamp se imprime TAMBIÉN con el interruptor en ON", async (assert) => {
    // El aviso "EXCEDIO SUBTOTAL" es el único rastro impreso de que el
    // descuento se recortó, así que debe salir con el interruptor en cualquier
    // posición. Junto a él sale ahora la línea de monto de la porción global.
    const driver = await buildConnectedDriver();

    const order = buildLineDiscountOrder([
        {
            product_name: "PROD CLAMP",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 0,
            gross_price_unit: 50,
            discount_amount: 20,        // campaña de la línea
        },
    ]);
    order.global_discount_amount = 80;    // histórico (pop-up, NC/ND)
    order.global_discount_rate = 100;
    order.global_clamped = true;
    order.global_only_discount_amount = 30;   // 50 bruto − 20 de campaña
    order.global_only_discount_rate = 100;
    order.footer_lines = ["PIE 1"];

    await primeDriver(driver, 1109);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura con clamp e interruptor en ON impresa");

    const history = fiscalAscii(driver);
    assert.ok(
        history.some((cmd) => cmd.includes("i00DESC. GLOBAL = 30,00<ETX>")),
        "La línea de MONTO muestra la porción global (30,00), no el histórico (80,00)"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("i01DESC. GLOBAL EXCEDIO SUBTOTAL<ETX>")),
        "El aviso de clamp se emite igual, detrás del monto"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("i02PIE 1<ETX>")),
        "El resto del pie corre detrás del aviso, con índices consecutivos"
    );
    assert.ok(result.global_clamped, "La bandera sigue llegando al caller");
});

QUnit.test("_appendFooterInfo: el aviso de clamp sale aunque el monto agregado sea 0", (assert) => {
    const driver = new TfhkaDriver();

    const withDiscount = [];
    driver._appendFooterInfo(withDiscount, {
        global_discount_rate: 100,
        global_discount_amount: 80,
        global_clamped: true,
        footer_lines: ["PIE 1"],
        additional_lines: ["OPERADOR: QA"],
    });
    assert.deepEqual(
        withDiscount,
        [
            "i00DESC. GLOBAL = 80,00",
            "i01DESC. GLOBAL EXCEDIO SUBTOTAL",
            "i02PIE 1",
            "i03OPERADOR: QA",
        ],
        "Con monto y clamp salen las dos líneas, en los tres documentos"
    );

    // Pedido cuyas líneas ya estaban TODAS al 100% de campaña: la porción
    // global agregada queda en 0 y no hay línea de monto que imprimir, pero el
    // recorte igual ocurrió y el cliente debe verlo en su ticket.
    const clampWithoutAmount = [];
    driver._appendFooterInfo(clampWithoutAmount, {
        global_discount_rate: 0,
        global_discount_amount: 0,
        global_clamped: true,
        footer_lines: ["PIE 1"],
        additional_lines: ["OPERADOR: QA"],
    });
    assert.deepEqual(
        clampWithoutAmount,
        ["i00DESC. GLOBAL EXCEDIO SUBTOTAL", "i01PIE 1", "i02OPERADOR: QA"],
        "Sin monto agregado sobrevive el aviso de clamp y reutiliza i00"
    );
});

QUnit.test("Estrategia C: el monto de descuento se calcula en Odoo, sin límite de 100%", async (assert) => {
    const driver = await buildConnectedDriver();

    // Una línea REGALADA (100% de descuento) es representable sin problema:
    // el monto es el total bruto de la línea. Con el viejo comando p- esto no
    // cabía en el campo de porcentaje (máx. 99,99%) y había que recortarlo.
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD REGALO",
            fiscal_code: "1",
            quantity: 3,
            price_unit: 0,
            gross_price_unit: 50,
            discount_amount: 150,      // 50,00 x 3 unidades = 150,00 Bs
        },
    ]);

    await primeDriver(driver, 1105);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura con línea al 100% de descuento impresa");

    const history = fiscalAscii(driver);
    const itemIndex = history.findIndex((cmd) => cmd.includes("PROD REGALO"));
    assert.ok(
        history[itemIndex].startsWith("<STX>!0000005000" + "00003000"),
        "El ítem va con precio bruto 50,00 y cantidad 3,000"
    );
    assert.ok(
        history[itemIndex + 1].startsWith("<STX>q-000015000<ETX>"),
        "El 100% se expresa como monto exacto (150,00 Bs): no hay recorte a 99,99%"
    );
    assert.deepEqual(result.line_discount_overflow_lines, [], "No hay desbordamiento");
});

// ====== SEPARACIÓN campaña (por línea) vs global (agregado al pie) ======
//
// Espejo de la aritmética de PosStore._convertOrderForDriver, que el bundle de
// QUnit no puede importar (vive en `point_of_sale._assets_pos`). Las dos
// fórmulas que deciden si el ticket cuadra —`computeLineDiscountAmount` y la
// composición de porcentajes— SÍ son las de producción; lo único replicado aquí
// es `_applyDiscount`, tres líneas sin ramas.
const R = 0.01;
const roundR = (v) => Number(Number(v).toFixed(2));
const applyPct = (unitPrice, percent) => roundR(Number(unitPrice || 0) * (1 - Number(percent || 0) / 100));

/**
 * Reproduce el reparto campaña/global de _convertOrderForDriver.
 *
 * @param {Array} rawLines - { name, grossUnitPrice, quantity, campaignPct, finalPct }
 *        `finalPct` es el % que Odoo tiene escrito en la línea (campaña YA
 *        compuesta con el global), es decir el camino `preAppliedMeta`.
 */
function splitDiscounts(rawLines) {
    let totalCampaign = 0;
    let totalActual = 0;
    let campaignNetSubtotal = 0;

    const lines = rawLines.map((raw) => {
        const gross = raw.grossUnitPrice;
        const qty = raw.quantity;
        const campaignNet = applyPct(gross, raw.campaignPct);
        const finalNet = applyPct(gross, raw.finalPct);

        const campaignAmount = computeLineDiscountAmount({
            grossUnitPrice: gross, netUnitPrice: campaignNet, quantity: qty, rounding: R,
        });
        const totalAmount = computeLineDiscountAmount({
            grossUnitPrice: gross, netUnitPrice: finalNet, quantity: qty, rounding: R,
        });

        totalCampaign += campaignAmount;
        totalActual += totalAmount;
        campaignNetSubtotal += roundR(campaignNet * qty);

        return {
            product_name: raw.name,
            fiscal_code: "1",
            quantity: qty,
            price_unit: finalNet,
            gross_price_unit: gross,
            discount_amount: campaignAmount,   // SÓLO campaña
            _totalAmount: totalAmount,         // auxiliar del test
            _finalNet: finalNet,
        };
    });

    const globalOnly = Math.max(0, roundR(totalActual - totalCampaign));
    const globalOnlyRate = globalOnly > 0 && campaignNetSubtotal > 0
        ? roundR((globalOnly / campaignNetSubtotal) * 100)
        : 0;

    return { lines, totalCampaign: roundR(totalCampaign), totalActual: roundR(totalActual), globalOnly, globalOnlyRate };
}

function buildSplitOrder(split) {
    const order = buildLineDiscountOrder(split.lines);
    order.global_only_discount_amount = split.globalOnly;
    order.global_only_discount_rate = split.globalOnlyRate;
    // Los históricos siguen viajando: los usan el pop-up y NC/ND.
    order.global_discount_amount = split.totalActual;
    order.global_discount_rate = 15;
    order.global_clamped = false;
    return order;
}

QUnit.test("Separación: una línea con campaña Y global imprime su q- SOLO con el monto de campaña", async (assert) => {
    const driver = await buildConnectedDriver();

    // 100,00 con 20% de campaña y 10% global encima -> compuesto 28%.
    // Campaña sola: 100 -> 80 (descuenta 20,00). Total real: 100 -> 72 (28,00).
    const split = splitDiscounts([
        { name: "PROD CAMPANA", grossUnitPrice: 100, quantity: 1, campaignPct: 20, finalPct: 28 },
    ]);
    assert.strictEqual(split.lines[0].discount_amount, 20, "El q- de la línea lleva SOLO la campaña (20,00)");
    assert.strictEqual(split.totalActual, 28, "El descuento real de la línea es 28,00");
    assert.strictEqual(split.globalOnly, 8, "La porción global agregada es 8,00");

    await primeDriver(driver, 1120);
    const result = await driver.printInvoice(buildSplitOrder(split));
    assert.ok(result.success, "Factura impresa");

    const history = fiscalAscii(driver);
    const itemIndex = history.findIndex((cmd) => cmd.includes("PROD CAMPANA"));
    assert.ok(
        history[itemIndex].startsWith("<STX>!0000010000"),
        "El ítem va a precio BRUTO (100,00)"
    );
    assert.ok(
        history[itemIndex + 1].startsWith("<STX>q-000002000<ETX>"),
        "El q- pegado al ítem es el de campaña (20,00), NO el compuesto (28,00)"
    );
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>q-000002800")),
        "En ningún lado se emite el monto compuesto (28,00)"
    );

    // El global va agregado, justo después del subtotal, igual que en NC/ND.
    const subtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    assert.ok(
        history[subtotalIndex + 1].startsWith("<STX>q-000000800<ETX>"),
        "El descuento global (8,00) se aplica agregado, después del subtotal"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 8,00")),
        "El pie muestra la porción global (8,00), no el descuento total (28,00)"
    );
});

QUnit.test("Separación: una línea SIN campaña no lleva q- propio; su descuento va al agregado", async (assert) => {
    const driver = await buildConnectedDriver();

    // Sin regla de campaña, el % de la línea lo escribió por completo el botón
    // de descuento global (flag `native_global_discount_line` en OFF).
    const split = splitDiscounts([
        { name: "PROD SIN CAMPANA", grossUnitPrice: 200, quantity: 1, campaignPct: 0, finalPct: 10 },
    ]);
    assert.strictEqual(split.lines[0].discount_amount, 0, "Sin campaña el monto por línea es 0,00");
    assert.strictEqual(split.globalOnly, 20, "Su descuento entero (20,00) se contabiliza como global");

    await primeDriver(driver, 1121);
    const result = await driver.printInvoice(buildSplitOrder(split));
    assert.ok(result.success, "Factura impresa");

    const history = fiscalAscii(driver);
    const itemIndex = history.findIndex((cmd) => cmd.includes("PROD SIN CAMPANA"));
    assert.notOk(
        history[itemIndex + 1].startsWith("<STX>q-"),
        "El ítem sin campaña NO es seguido por un q- propio"
    );
    const subtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    assert.ok(
        history[subtotalIndex + 1].startsWith("<STX>q-000002000<ETX>"),
        "Su descuento (20,00) sale una sola vez, agregado tras el subtotal"
    );
    assert.strictEqual(
        history.filter((cmd) => cmd.startsWith("<STX>q-")).length,
        1,
        "Un único q- en toda la factura: el agregado"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 20,00")),
        "El pie refleja ese mismo monto"
    );
});

QUnit.test("Separación: escenario mixto — Σ(q- por línea) + agregado == descuento real de Odoo", async (assert) => {
    const driver = await buildConnectedDriver();

    // Una línea CON campaña (20%) y otra SIN, ambas bajo el mismo global (10%).
    const split = splitDiscounts([
        { name: "CON CAMPANA", grossUnitPrice: 100, quantity: 2, campaignPct: 20, finalPct: 28 },
        { name: "SIN CAMPANA", grossUnitPrice: 50, quantity: 3, campaignPct: 0, finalPct: 10 },
    ]);

    // Línea 1: bruto 200 -> campaña 160 (descuenta 40) -> final 144 (descuenta 56)
    // Línea 2: bruto 150 -> campaña 150 (descuenta  0) -> final 135 (descuenta 15)
    assert.strictEqual(split.lines[0].discount_amount, 40, "Línea con campaña: q- de 40,00 (2 x 20,00)");
    assert.strictEqual(split.lines[1].discount_amount, 0, "Línea sin campaña: sin q- propio");
    assert.strictEqual(split.totalActual, 71, "Odoo descuenta 71,00 en total (56 + 15)");
    assert.strictEqual(split.globalOnly, 31, "La porción global es 31,00 (16 + 15)");

    // LA identidad que hace cuadrar el ticket.
    assert.strictEqual(
        roundR(split.totalCampaign + split.globalOnly),
        split.totalActual,
        "Σ(q- por línea) + agregado del pie == descuento total real del pedido"
    );

    await primeDriver(driver, 1122);
    const result = await driver.printInvoice(buildSplitOrder(split));
    assert.ok(result.success, "Factura mixta impresa");

    const history = fiscalAscii(driver);
    const conIndex = history.findIndex((cmd) => cmd.includes("CON CAMPANA"));
    const sinIndex = history.findIndex((cmd) => cmd.includes("SIN CAMPANA"));
    assert.ok(history[conIndex + 1].startsWith("<STX>q-000004000<ETX>"), "La línea con campaña lleva su q- de 40,00");
    assert.notOk(history[sinIndex + 1].startsWith("<STX>q-"), "La línea sin campaña no lleva q- propio");

    const subtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    assert.ok(
        history[subtotalIndex + 1].startsWith("<STX>q-000003100<ETX>"),
        "El agregado tras el subtotal es la porción global (31,00)"
    );
    assert.ok(history.some((cmd) => cmd.includes("DESC. GLOBAL = 31,00")), "Y el pie lo muestra igual");

    // El total que le queda a la impresora coincide con el neto de Odoo.
    const grossTotal = roundR(100 * 2) + roundR(50 * 3);
    const odooNetTotal = roundR(split.lines[0]._finalNet * 2) + roundR(split.lines[1]._finalNet * 3);
    assert.strictEqual(
        roundR(grossTotal - split.totalCampaign - split.globalOnly),
        odooNetTotal,
        "bruto − Σq- por línea − agregado == neto que cobra Odoo (lo que compara el cierre 199)"
    );
});

QUnit.test("Separación: caso real de campo — 3 x 34.266,88 al 90% de campaña + descuento global", async (assert) => {
    const driver = await buildConnectedDriver();

    // Pedido reportado desde producción: tres líneas del mismo producto a
    // 34.266,88 con 90% de campaña, más un botón de Descuento Global que en
    // Odoo genera una línea "Descuento" de -1.542,01 (≈15% del neto de
    // campaña). Compuesto por línea: 100 − (10 × 85)/100 = 91,5%.
    const split = splitDiscounts([
        { name: "PROD A", grossUnitPrice: 34266.88, quantity: 1, campaignPct: 90, finalPct: 91.5 },
        { name: "PROD B", grossUnitPrice: 34266.88, quantity: 1, campaignPct: 90, finalPct: 91.5 },
        { name: "PROD C", grossUnitPrice: 34266.88, quantity: 1, campaignPct: 90, finalPct: 91.5 },
    ]);

    // `roundR` sólo limpia el ruido IEEE-754 que `roundPrecision` deja en este
    // valor concreto (30840.190000000002). Es inocuo: `_formatAmount` hace
    // `toFixed` antes de armar la trama, como verifica el `q-` de más abajo.
    assert.strictEqual(
        roundR(split.lines[0].discount_amount),
        30840.19,
        "Cada línea imprime su q- por SOLO el 90% de campaña (30.840,19)"
    );
    assert.strictEqual(split.totalCampaign, 92520.57, "Σ de los tres q- de campaña");
    assert.strictEqual(
        split.globalOnly,
        1542.03,
        "El pie lleva la porción global: 1.542,03 (1.542,01 de Odoo + 2 céntimos de redondeo por línea)"
    );
    assert.strictEqual(split.totalActual, 94062.6, "Descuento total real del pedido");
    assert.strictEqual(
        roundR(split.totalCampaign + split.globalOnly),
        split.totalActual,
        "3 x 30.840,19 + 1.542,03 == 94.062,60, el descuento real de Odoo"
    );

    await primeDriver(driver, 1123);
    const result = await driver.printInvoice(buildSplitOrder(split));
    assert.ok(result.success, "Factura del caso real impresa");

    const history = fiscalAscii(driver);
    const lineDiscounts = history.filter((cmd) => cmd.startsWith("<STX>q-003084019"));
    assert.strictEqual(lineDiscounts.length, 3, "Los tres q- de campaña se emiten, uno por línea");
    const subtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    assert.ok(
        history[subtotalIndex + 1].startsWith("<STX>q-000154203<ETX>"),
        "El descuento global agregado (1.542,03) va tras el subtotal"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 1.542,03")),
        "Y el pie lo imprime con formato venezolano"
    );

    // Lo que la impresora termina cobrando == lo que cobra Odoo.
    const grossTotal = roundR(34266.88 * 3);
    const odooNetTotal = roundR(split.lines[0]._finalNet * 3);
    assert.strictEqual(
        roundR(grossTotal - split.totalCampaign - split.globalOnly),
        odooNetTotal,
        "102.800,64 − 92.520,57 − 1.542,03 == 8.738,04, el neto de Odoo"
    );
});

QUnit.test("NC/ND sin cambios: printCreditNote ignora gross_price_unit y discount_amount", async (assert) => {
    const driver = await buildConnectedDriver();

    // La MISMA estructura de línea que produce _convertOrderForDriver (con los
    // campos nuevos) y con el interruptor incluso en ON: la NC debe seguir
    // usando price_unit (neto) y su único q- debe ser el agregado del subtotal.
    const creditNoteOrder = {
        partner: { vat: "V17527041", name: "Cliente NC" },
        invoice_affected: { number: "863", serial_machine: "Z1F0022949", date: "20/06/2026" },
        lines: [
            {
                product_name: "Producto Devuelto",
                product_code: "P001",
                fiscal_code: "1",
                quantity: 2,
                price_unit: 50,            // neto
                gross_price_unit: 100,     // NO debe usarse en NC
                discount_amount: 100,      // NO debe emitirse por línea en NC
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 100 }],
        global_discount_amount: 15,
        global_discount_rate: 15,
        global_clamped: false,
        // Campos de la separación campaña/global: la NC debe ignorarlos por
        // completo, tanto en su q- agregado como en la línea del pie.
        global_only_discount_amount: 7,
        global_only_discount_rate: 7,
        additional_lines: ["OPERADOR: TEST"],
        flag_21: "00",
        has_cashbox: false,
        line_discount_via_q: true,   // ni siquiera con el interruptor en ON
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(30).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 863,
        lastNCNumber: 1234,
        dailyClosureCounter: 18,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printCreditNote(creditNoteOrder);
    assert.ok(result.success, "NC impresa exitosamente");

    const history = fiscalAscii(driver);
    assert.ok(
        history.some((cmd) => cmd.includes("<STX>d1000000500000002000|P001|Producto Devue<ETX>")),
        "La NC sigue registrando el ítem con price_unit (50,00), byte por byte igual que antes"
    );
    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>d1000001000")),
        "La NC NO usa gross_price_unit (100,00)"
    );
    assert.notOk(history.some((cmd) => cmd.startsWith("<STX>p-")), "La NC no emite ningún comando p-");
    // El pie de la NC no cambió: sigue emitiendo la línea agregada de descuento
    // global a partir de `global_discount_amount` (el histórico), ignorando por
    // completo `global_only_discount_amount`.
    assert.ok(
        history.some((cmd) => cmd.includes("i00DESC. GLOBAL = 15,00<ETX>")),
        "La NC sigue emitiendo la línea agregada DESC. GLOBAL en el pie"
    );
    // Un ÚNICO q-, el agregado del subtotal (15,00 Bs), emitido DESPUÉS del
    // subtotal "3" — no el de la línea (100,00) ni pegado al ítem.
    const ncDiscountCommands = history.filter((cmd) => cmd.startsWith("<STX>q-"));
    assert.strictEqual(ncDiscountCommands.length, 1, "La NC emite exactamente un q-");
    assert.ok(
        ncDiscountCommands[0].startsWith("<STX>q-000001500<ETX>"),
        "El q- de la NC es el descuento global agregado (15,00), no el de la línea (100,00)"
    );
    const ncSubtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    const ncItemIndex = history.findIndex((cmd) => cmd.includes("Producto Devue"));
    assert.ok(
        history.indexOf(ncDiscountCommands[0]) === ncSubtotalIndex + 1,
        "El q- de la NC va después del subtotal, no pegado al ítem"
    );
    assert.notOk(
        history[ncItemIndex + 1].startsWith("<STX>q-"),
        "El ítem de la NC no es seguido inmediatamente por un q-"
    );
});

QUnit.test("_appendFooterInfo: la línea de descuento se emite siempre, y sólo desaparece sin monto", (assert) => {
    const driver = new TfhkaDriver();
    const orderData = {
        global_discount_rate: 15,
        global_discount_amount: 15,
        global_clamped: false,
        footer_lines: ["PIE 1"],
        additional_lines: ["OPERADOR: QA"],
    };

    const withDiscount = [];
    driver._appendFooterInfo(withDiscount, orderData);
    assert.deepEqual(
        withDiscount,
        ["i00DESC. GLOBAL = 15,00", "i01PIE 1", "i02OPERADOR: QA"],
        "Se emite la línea de descuento y los índices corren detrás"
    );

    // Ya no existe ningún parámetro para suprimirla: un tercer argumento
    // sobrante no cambia nada (la firma quedó de dos parámetros al separar el
    // descuento de campaña del global).
    const extraArg = [];
    driver._appendFooterInfo(extraArg, orderData, true);
    assert.deepEqual(
        extraArg,
        ["i00DESC. GLOBAL = 15,00", "i01PIE 1", "i02OPERADOR: QA"],
        "No hay forma de suprimir la línea agregada: ya no es redundante con ningún q-"
    );

    // Sin descuento global (pedido con sólo descuentos de campaña) no hay nada
    // que agregar y el pie arranca en i00.
    const noDiscount = [];
    driver._appendFooterInfo(noDiscount, {
        ...orderData,
        global_discount_rate: 0,
        global_discount_amount: 0,
    });
    assert.deepEqual(
        noDiscount,
        ["i00PIE 1", "i01OPERADOR: QA"],
        "Sin monto global el pie conserva sus líneas y reutiliza el índice i00"
    );
});

QUnit.test("Header y footer del POS se envían como iXX", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 0;

    await driver.connection.requestPort();
    driver.isConnected = true;

    const orderWithHeaderFooter = {
        partner: {
            vat: "V12345678",
            name: "CLIENTE HEADER",
            address: "Av Principal Torre A Piso 2",
            phone: "0212-0000000",
        },
        lines: [
            {
                product_name: "Producto Header Footer",
                product_code: "HF01",
                fiscal_code: "1",
                quantity: 1,
                price_unit: 10,
            },
        ],
        payment_lines: [{ payment_method_code: "01", amount: 10 }],
        header_lines: ["ENCABEZADO 1", "ENCABEZADO 2"],
        footer_lines: ["PIE 1"],
        additional_lines: ["OPERADOR: QA"],
        flag_21: "00",
        has_cashbox: false,
    };

    driver.connection.setNextResponse("STATUS");
    driver.connection.setResponseSequence(new Array(30).fill("ACK"));
    driver.connection.setS1Payload(buildS1Payload({
        lastInvoiceNumber: 1000,
        dailyClosureCounter: 20,
        serialMachine: "Z1F0022949",
    }));

    const result = await driver.printInvoice(orderWithHeaderFooter);
    assert.ok(result.success, "Factura con header/footer impresa exitosamente");

    const fiscalCommands = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>i02ENCABEZADO 1<ETX>")), "Header línea 1 enviada");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>i03ENCABEZADO 2<ETX>")), "Header línea 2 enviada");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>i00PIE 1<ETX>")), "Footer línea 1 enviada");
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>i01OPERADOR: QA<ETX>")), "Línea adicional se envía después del footer");
});

QUnit.test("Lectura y parsing de S3", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();

    await driver.connection.requestPort();
    driver.isConnected = true;

    const s3Payload = "S311600\n20800\n10000\n101230405";
    driver.connection.setNextResponse(s3Payload);

    const result = await driver.readS3Data();

    assert.ok(result.success, "S3 leído correctamente");
    assert.strictEqual(result.data.tax1.type, "1", "Tipo tasa 1 parseado");
    assert.strictEqual(result.data.tax1.value, 16, "Valor tasa 1 parseado");
    assert.strictEqual(result.data.tax2.typeLabel, "Incluido", "Tipo de tasa 2 interpretado");
    assert.strictEqual(result.data.igtf.value, 1.23, "IGTF parseado con 2 decimales implícitos");
    assert.deepEqual(result.data.systemFlags, [4, 5], "Flags de sistema parseados");
});

QUnit.test("Error de conexión a la máquina fiscal", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.isConnected = false;

    const result = await driver.printInvoice({
        partner: { vat: "J000000001", name: "SIN CONEXION" },
        lines: [{ product_name: "Producto", fiscal_code: "1", quantity: 1, price_unit: 10 }],
        payment_lines: [{ payment_method_code: "01", amount: 10 }],
        additional_lines: [],
        flag_21: "00",
        has_cashbox: false,
    });

    assert.notOk(result.success, "No imprime si la impresora está desconectada");
    assert.ok(result.error.includes("Impresora no conectada"), "Retorna mensaje de conexión");
});

// ====== Revisión formal 2026-09-22/23: C1, C2, C3 ======
//
// `_convertOrderForDriver` vive en `l10n_ve_pos_mf` (bundle `point_of_sale.
// assets_pos`), que este archivo NO puede importar (ver nota en la sección
// "SEPARACIÓN campaña..." más arriba): por eso C1 y C3 —que son fixes DENTRO
// de esa función— se verifican aquí reproduciendo su aritmética exacta con
// las funciones REALES de `DiscountMath` (no una reimplementación), igual que
// hace `splitDiscounts` arriba. C2 sí vive enteramente en `TfhkaDriver.js` y
// se testea de punta a punta contra el driver real.

QUnit.test("C1 (revisión formal): el q- de campaña nunca excede el descuento TOTAL real de la línea", (assert) => {
    // Reproduce el escenario de la revisión: una línea con marca de campaña
    // (90%) sobre la que el cajero tecleó DESPUÉS un descuento MANUAL menor
    // (20%). La marca `campaignDiscountPercent`/`campaignDiscountAppliedPercent`
    // de `orderline_model.js` sólo se limpia cuando el descuento vigente
    // coincide EXACTO con el último que ella misma escribió — con un manual
    // distinto queda desfasada, y `campaign_discount_percent` le sigue
    // llegando a `_convertOrderForDriver` como 90, aunque Odoo sólo esté
    // cobrando 20% en `line.discount`.
    const gross = 100;
    const qty = 1;
    const staleCampaignPct = 90;   // marca desfasada, ya no vigente
    const actualFinalPct = 20;     // lo que el cajero dejó tecleado a mano

    const campaignOnlyNet = applyPct(gross, staleCampaignPct);
    const finalNet = applyPct(gross, actualFinalPct);

    const lineTotalDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: finalNet, quantity: qty, rounding: R,
    });
    const lineCampaignDiscountAmountRaw = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: campaignOnlyNet, quantity: qty, rounding: R,
    });

    assert.ok(
        lineCampaignDiscountAmountRaw > lineTotalDiscountAmount,
        `Sin el fix, el monto de campaña de la marca desfasada (${lineCampaignDiscountAmountRaw}) ` +
        `sería MAYOR que el descuento real que cobra Odoo (${lineTotalDiscountAmount})`
    );

    // El fix de _convertOrderForDriver: Math.min(...) acota al descuento TOTAL
    // real de la línea, sin depender de arreglar el desfase de la marca.
    const lineCampaignDiscountAmount = Math.min(lineCampaignDiscountAmountRaw, lineTotalDiscountAmount);
    assert.strictEqual(
        lineCampaignDiscountAmount,
        lineTotalDiscountAmount,
        "Con el fix, el q- de campaña queda acotado exactamente al descuento real (20,00), nunca lo excede"
    );
    assert.strictEqual(lineCampaignDiscountAmount, 20, "Valor concreto: 20,00, no 90,00");

    // El driver, alimentado con el monto YA acotado, imprime exactamente ese
    // valor — nunca el de la marca desfasada.
});

QUnit.test("C1 (revisión formal): sin desfase de marca, el Math.min no cambia nada", (assert) => {
    // Caso sano (idéntico a un test de "Separación" ya existente): con
    // `campaign_discount_percent` consistente con `line.discount`, el tope no
    // debe alterar el monto que ya se calculaba.
    const gross = 100;
    const qty = 1;
    const campaignPct = 20;
    const finalPct = 28; // 20% campaña compuesto con 10% global

    const campaignOnlyNet = applyPct(gross, campaignPct);
    const finalNet = applyPct(gross, finalPct);

    const lineTotalDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: finalNet, quantity: qty, rounding: R,
    });
    const lineCampaignDiscountAmountRaw = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: campaignOnlyNet, quantity: qty, rounding: R,
    });
    const lineCampaignDiscountAmount = Math.min(lineCampaignDiscountAmountRaw, lineTotalDiscountAmount);

    assert.strictEqual(lineCampaignDiscountAmountRaw, 20, "Monto de campaña sin acotar: 20,00");
    assert.strictEqual(lineCampaignDiscountAmount, 20, "El Math.min es un no-op cuando no hay desfase");
});

QUnit.test("C2 (revisión formal): una línea que desborda en precio BRUTO degrada TODO el documento a Estrategia A", async (assert) => {
    const driver = await buildConnectedDriver();

    // Dos líneas: una sana con descuento de campaña (emitiría su propio q- si
    // el documento no degradara) y otra cuyo precio BRUTO no cabe en el Flag
    // 21 (max_amount_int = 8 con flag "00"). Antes del fix, sólo la segunda
    // se degradaba y el `q-` agregado del pie seguía restando la porción
    // global de la línea degradada una segunda vez (duplicación). Con el fix,
    // NINGUNA línea emite q- y el pie usa los montos HISTÓRICOS.
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD SANO",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 90,
            gross_price_unit: 100,
            discount_amount: 10,
        },
        {
            product_name: "PROD DESBORDA",
            fiscal_code: "1",
            quantity: 1,
            price_unit: 60000000,
            gross_price_unit: 120000000,   // > 99.999.999,99 (8 enteros)
            discount_amount: 60000000,
        },
    ]);
    // Históricos (Estrategia A) vs "_only" (Estrategia C): deben ser
    // DISTINTOS en este test para poder verificar cuál usa el pie.
    order.global_discount_amount = 999;      // histórico
    order.global_discount_rate = 12.34;      // histórico
    order.global_clamped = false;
    order.global_only_discount_amount = 5;   // "solo global" — NO debe usarse
    order.global_only_discount_rate = 1.23;  // "solo global" — NO debe usarse

    await primeDriver(driver, 1140);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "La factura se imprime igual, sin trama malformada");

    const history = fiscalAscii(driver);

    assert.notOk(
        history.some((cmd) => cmd.startsWith("<STX>q-")),
        "NINGÚN q- se emite en todo el documento: ni el de campaña de la línea sana, ni ningún agregado"
    );

    const sanoIndex = history.findIndex((cmd) => cmd.includes("PROD SANO"));
    assert.ok(
        history[sanoIndex].startsWith("<STX>!0000009000"),
        "La línea sana también se degrada: se imprime a su precio NETO (90,00), no al bruto (100,00)"
    );

    assert.deepEqual(
        result.line_gross_price_overflow_lines,
        ["PROD DESBORDA"],
        "Sólo se reporta la línea que realmente desbordaba"
    );
    assert.ok(
        result.line_discount_via_q_document_degraded,
        "La bandera de degradación de DOCUMENTO COMPLETO llega al caller"
    );

    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 999,00")),
        "El pie usa el monto HISTÓRICO (999,00), no la porción 'solo global' (5,00)"
    );
    assert.notOk(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 5,00")),
        "La porción 'solo global' NUNCA se imprime: el documento completo cayó a Estrategia A"
    );
});

QUnit.test("C3 (revisión formal, ticket físico 2026-09-23): la fuente exacta elimina el desfase de 1 céntimo", async (assert) => {
    // Reconstrucción numérica exacta del ticket real: 2 líneas iguales a
    // 34.266,88 con 90% de campaña (camino ON: native_global_discount_line en
    // true, la línea nativa "Descuento" de Odoo queda separada), más un botón
    // de Descuento Global del 15% que en Odoo genera una línea "Descuento" de
    // exactamente -1.028,01. Odoo real: BI 5.825,37 / Total (16% IVA) 6.757,43.
    const gross = 34266.88;
    const campaignPct = 90;

    const campaignOnlyNet = applyPct(gross, campaignPct); // 3.426,69
    const positiveBaseSum = roundR(campaignOnlyNet * 2);  // 6.853,38 (2 líneas)

    // Monto EXACTO de la línea nativa "Descuento" que Odoo calcula (15% sobre
    // la base ya neta de campaña) — el mismo dato que `globalDiscountAmount`
    // recoge en el camino ON de `_convertOrderForDriver`.
    const nativeDiscountAmount = roundR(positiveBaseSum * 0.15);
    assert.strictEqual(nativeDiscountAmount, 1028.01, "Reconstruye el monto real de Odoo (1.028,01)");

    const lineCampaignDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: campaignOnlyNet, quantity: 1, rounding: R,
    });
    assert.strictEqual(lineCampaignDiscountAmount, 30840.19, "q- de campaña por línea");

    // --- Fórmula ANTIGUA (por diferencia de dos sumas por línea ya redondeadas) ---
    const globalRateOld = roundR((nativeDiscountAmount / positiveBaseSum) * 100);
    const finalNetOld = roundR(campaignOnlyNet * (1 - globalRateOld / 100));
    const lineTotalDiscountAmountOld = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: finalNetOld, quantity: 1, rounding: R,
    });
    const totalCampaignOld = roundR(lineCampaignDiscountAmount * 2);
    const totalActualOld = roundR(lineTotalDiscountAmountOld * 2);
    const globalOnlyOld = Math.max(0, roundR(totalActualOld - totalCampaignOld));
    assert.strictEqual(
        globalOnlyOld,
        1028.00,
        "La fórmula ANTIGUA reproduce el desfase real: 1.028,00 impreso vs 1.028,01 de Odoo (el bug reportado)"
    );

    // --- Fórmula NUEVA (fuente exacta: `globalDiscountAmount` ya calculado
    // arriba en `_convertOrderForDriver`, sin rederivar por diferencia) ---
    const globalOnlyNew = nativeDiscountAmount;
    assert.strictEqual(
        globalOnlyNew,
        1028.01,
        "La fórmula NUEVA usa el monto exacto de la línea nativa: cuadra con Odoo, sin desfase"
    );

    // Lo que efectivamente queda registrado en la impresora (gross − Σq- de
    // campaña − q- agregado) es lo que hay que comparar contra la Base
    // Imponible real de Odoo — NO el precio neto por línea, que con el flag
    // en ON ni siquiera se envía a la impresora (se registra el bruto).
    const grossTotal = roundR(gross * 2);
    assert.strictEqual(
        roundR(grossTotal - totalCampaignOld - globalOnlyNew),
        5825.37,
        "bruto − Σ(q- de campaña) − q- agregado(NUEVO) == BI real de Odoo (5.825,37), sin desfase"
    );
    assert.notStrictEqual(
        roundR(grossTotal - totalCampaignOld - globalOnlyOld),
        5825.37,
        "Con la fórmula ANTIGUA el resultado NO cuadraba con la BI real (quedaba en 5.825,38)"
    );

    // Extremo a extremo contra el driver real.
    const driver = await buildConnectedDriver();
    const order = buildLineDiscountOrder([
        {
            product_name: "PROD A", fiscal_code: "1", quantity: 1,
            price_unit: finalNetOld, gross_price_unit: gross,
            discount_amount: lineCampaignDiscountAmount,
        },
        {
            product_name: "PROD B", fiscal_code: "1", quantity: 1,
            price_unit: finalNetOld, gross_price_unit: gross,
            discount_amount: lineCampaignDiscountAmount,
        },
    ]);
    order.global_only_discount_amount = globalOnlyNew;
    order.global_only_discount_rate = globalRateOld;
    order.global_discount_amount = nativeDiscountAmount; // histórico == "solo global" en el camino ON
    order.global_discount_rate = globalRateOld;
    order.global_clamped = false;

    await primeDriver(driver, 1141);
    const result = await driver.printInvoice(order);
    assert.ok(result.success, "Factura del caso real (2026-09-23) impresa");

    const history = fiscalAscii(driver);
    const subtotalIndex = history.findIndex((cmd) => cmd.startsWith("<STX>3<ETX>"));
    assert.ok(
        history[subtotalIndex + 1].startsWith("<STX>q-000102801<ETX>"),
        "El q- agregado tras el subtotal imprime 1.028,01 (no el 1.028,00 de la fórmula antigua)"
    );
    assert.ok(
        history.some((cmd) => cmd.includes("DESC. GLOBAL = 1.028,01")),
        "El pie muestra el monto exacto, coincidente con Odoo"
    );
});

QUnit.test("C3 (revisión formal): camino OFF (campaña compuesta con composeDiscountPercent) sigue exacto tras el fix", (assert) => {
    // Complemento del test anterior: ese cubre el camino ON (el de la
    // evidencia real de campo). Este cubre el camino OFF
    // (`native_global_discount_line` en `false`, campaña y global se componen
    // vía `composeDiscountPercent` en un solo `line.discount`) con el caso de
    // referencia de `DISCOUNT_STRATEGY.md`: 3 líneas a 34.266,88, 90% de
    // campaña, compuesto con el global a 91,5%.
    //
    // Es la comprobación de que la fórmula corregida usa la resta
    // (`globalDiscountAmount histórico − Σ campaña`) SÓLO en este camino, y NO
    // el monto crudo pre-composición (`inference.pendingDiscountAmount` /
    // "1.542,01"): ese monto crudo no reproduce lo que Odoo realmente cobra
    // una vez que `composeDiscountPercent` redondeó el % compuesto (91,5%) —
    // ver la sección "Cómo se calcula la porción global" del documento para el
    // análisis numérico completo.
    const gross = 34266.88;
    const campaignPct = 90;
    const combinedPct = 91.5; // composeDiscountPercent(90, ~15) redondeado
    const n = 3;

    const campaignOnlyNet = applyPct(gross, campaignPct);           // 3.426,69
    const finalNet = applyPct(gross, combinedPct);                  // 2.912,68

    const lineCampaignDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: campaignOnlyNet, quantity: 1, rounding: R,
    });
    const lineTotalDiscountAmount = computeLineDiscountAmount({
        grossUnitPrice: gross, netUnitPrice: finalNet, quantity: 1, rounding: R,
    });
    assert.strictEqual(lineCampaignDiscountAmount, 30840.19, "q- de campaña por línea (igual que en el camino ON)");
    assert.strictEqual(lineTotalDiscountAmount, 31354.20, "Descuento TOTAL real por línea (91,5% compuesto)");

    const totalCampaignDiscountAmount = roundR(lineCampaignDiscountAmount * n);
    // `globalDiscountAmount` histórico en el camino OFF ==
    // `preAppliedMeta.global_discount_amount` == Σ lineTotalDiscountAmount,
    // porque ambos se derivan del MISMO `line.discount` (91,5%) real que Odoo
    // aplicó — no hay dos fuentes independientes aquí, a diferencia del ON.
    const globalDiscountAmountHistoric = roundR(lineTotalDiscountAmount * n);
    assert.strictEqual(globalDiscountAmountHistoric, 94062.60, "Descuento TOTAL combinado (histórico, 3 líneas)");

    const pendingDiscountAmountCrudo = 1542.01; // monto crudo de la línea nativa, ANTES de componer

    const globalOnlyFixed = Math.max(0, roundR(globalDiscountAmountHistoric - totalCampaignDiscountAmount));
    assert.strictEqual(globalOnlyFixed, 1542.03, "Fórmula corregida (resta en el camino OFF): 1.542,03, coincide con Odoo");
    assert.notStrictEqual(
        globalOnlyFixed,
        pendingDiscountAmountCrudo,
        "La fórmula corregida NO coincide con el monto crudo pre-composición (1.542,01): esa variante se descartó"
    );

    const grossTotal = roundR(gross * n);
    assert.strictEqual(
        roundR(grossTotal - totalCampaignDiscountAmount - globalOnlyFixed),
        roundR(finalNet * n),
        "bruto − Σ(q- de campaña) − globalOnly(corregido) == lo que Odoo REALMENTE cobra (Σ subtotales reales por línea)"
    );
    assert.notStrictEqual(
        roundR(grossTotal - totalCampaignDiscountAmount - pendingDiscountAmountCrudo),
        roundR(finalNet * n),
        "Con el monto crudo pre-composición, el total registrado NO habría coincidido con lo que Odoo cobra (riesgo de NAK en el 199)"
    );
});

// Registrar tests en el registry de Odoo
registry.category("web_tour.tours").add("tfhka_driver_tests", {
    test: true,
    url: "/web",
    steps: () => [],
});
