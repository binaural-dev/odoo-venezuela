/** @odoo-module **/

import { IoTLongpolling } from '@iot_base/network_utils/longpolling';
import { post } from '@iot_base/network_utils/http';
import { patch } from "@web/core/utils/patch";

const PRIVATE_IP_HOST_RE = /^(\d+)\.(\d+)\.(\d+)\.(\d+)(?:\..*)?$/;
const PRIVATE_IP_RE = /^(\d{1,3}\.){3}\d{1,3}$/;

function isLocalIoTHost(host) {
    if (!host) {
        return false;
    }
    return PRIVATE_IP_HOST_RE.test(host) || PRIVATE_IP_RE.test(host);
}

/**
 * Extrae la IP real desde un hostname tipo 192-168-1-22.xxx.odoo-iot.com
 * Ej: "192-168-1-22.89539812.odoo-iot.com" -> "192.168.1.22"
 */
function extractRawIp(host) {
    const match = host.match(/^(\d+)-(\d+)-(\d+)-(\d+)/);
    if (match) {
        return `${match[1]}.${match[2]}.${match[3]}.${match[4]}`;
    }
    return host;
}

patch(IoTLongpolling.prototype, {
    setup() {
        super.setup(...arguments);
        // Timeouts extendidos (ms) para máquinas fiscales venezolanas (procesamiento lento)
        this.POLL_TIMEOUT = 3000000;
        this.ACTION_TIMEOUT = 1000000;

        if (typeof odoo !== 'undefined' && 'use_lna' in odoo) {
            this.setLna(Boolean(odoo.use_lna));
        }
    },

    /**
     * Mantenemos el formato de body sin el wrapper `params` que introduce
     * Odoo 19 estándar, para compatibilidad con el firmware de las cajas
     * fiscales venezolanas que esperan el formato plano original.
     */
    action(iot_ip, device_identifier, data, fallback = false, route = null) {
        const body = {
            session_id: this._session_id,
            device_identifier: device_identifier,
            data,
        };
        console.log(`IoT Action: iot_ip=${iot_ip}, device_identifier=${device_identifier}, data=${JSON.stringify(data)}, route=${route}`);
        return this._rpcIoT(iot_ip, route || this.actionRoute, body, this.ACTION_TIMEOUT, fallback);
    },

    async _rpcIoT(iot_ip, route, params, timeout, fallback, headers) {
        // Para hosts locales, el Odoo del IoT Box escucha en puerto 8069
        const isLocal = isLocalIoTHost(iot_ip);
        const targetIp = isLocal ? `${extractRawIp(iot_ip)}` : iot_ip;

        if (isLocal && window.location.protocol === "https:") {
            // Proxy a través del servidor Odoo (misma LAN)
            // Usamos el proxy para TODAS las rutas (action y event).
            // La conexión directa desde HTTPS a HTTP siempre da error CORS,
            // por lo que no hacemos fallback directo.
            try {
                const resp = await fetch("/l10n_ve_iot_mf/action", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
                    body: JSON.stringify({
                        iot_ip: extractRawIp(iot_ip),
                        route,
                        params,
                        timeout: Math.min((timeout || this.ACTION_TIMEOUT) / 1000, 120),
                    }),
                });
                const result = await resp.json();
                console.log("Proxy result:", result);
                if (result?.status !== "unreachable" && !result?.error) {
                    return result;
                }
                // Proxy respondió con error -> propagamos para que el poll reintente
                throw new Error(result?.error || "IoT proxy returned error");
            } catch (error) {
                if (!fallback && error?.name !== "AbortError") {
                    this._doWarnFail(iot_ip);
                }
                throw error;
            }
        }

        // HTTP page o IP no-local: conectar directo
        const originalUseLna = this.useLna;
        if (isLocal) {
            this.useLna = true;
        }
        try {
            const abortController = new AbortController();
            if (this._listeners[iot_ip] && route === this.pollRoute) {
                this._listeners[iot_ip].abortController = abortController;
            }
            return await post(targetIp, route, params, timeout, headers, abortController.signal, this.useLna);
        } catch (error) {
            if (!fallback && error?.name !== "AbortError") {
                this._doWarnFail(iot_ip);
            }
            throw new Error("Longpolling action failed");
        } finally {
            this.useLna = originalUseLna;
        }
    }
});
