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
    assert.ok(statusText.includes("Lista") || statusText.includes("Operativa"), "Texto de status correcto");
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
    const commandsHistory = driver.connection.getSentCommands();
    assert.strictEqual(commandsHistory.length, 3, "Se enviaron exactamente 3 comandos");
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
    driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
    driver.connection.setNextResponse(buildS1Payload({
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
    assert.ok(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")), "Cierre de documento usa método principal 02");
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
    driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
    driver.connection.setNextResponse(buildS1Payload({
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
