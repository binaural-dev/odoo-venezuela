/** @odoo-module */

import { registry } from "@web/core/registry";
import { FiscalProtocol } from "../core/FiscalProtocol";
import { StatusParser } from "../core/StatusParser";
import { TfhkaDriver } from "../drivers/TfhkaDriver";
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
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>201000000001000<ETX>")), "Pago parcial método 01 enviado");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>202000000002000<ETX>")), "Pago parcial método 02 enviado");
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>101<ETX>")), "Cierre fiscal final 101 enviado");
    assert.notOk(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")), "No se envía 1XX para pago múltiple");
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
    assert.ok(fiscalCommands.some((cmd) => cmd.includes("<STX>d1000000500000002000|P001|Producto Devuelto<ETX>")), "Línea NC enviada con prefijo d");
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
    const exemptLine = asciiHistory.find((cmd) => cmd.includes("Producto Exento Prefijo"));
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
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL 15% = 15.00<ETX>")),
        "Línea informativa de descuento global con porcentaje y monto presentes"
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
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL 100% = 50.00<ETX>")),
        "Línea informativa del descuento clampado presente"
    );
    assert.ok(
        asciiHistory.some((cmd) => cmd.includes("i01DESC. GLOBAL EXCEDIO SUBTOTAL<ETX>")),
        "Línea de aviso por clamp emitida"
    );
    assert.ok(result.global_clamped, "Bandera global_clamped=true hacia el caller");
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

// Registrar tests en el registry de Odoo
registry.category("web_tour.tours").add("tfhka_driver_tests", {
    test: true,
    url: "/web",
    steps: () => [],
});
