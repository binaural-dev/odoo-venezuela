/** @odoo-module **/

import { IoTLongpolling } from '@iot_base/network_utils/longpolling';
import { patch } from "@web/core/utils/patch";

const PRIVATE_IP_HOST_RE = /^(\d+)-(\d+)-(\d+)-(\d+)(?:\..*)?$/;
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
        // Timeouts extendidos para máquinas fiscales en Venezuela (procesamiento lento)
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
        return this._rpcIoT(iot_ip, route || this.actionRoute, body, this.ACTION_TIMEOUT, fallback);
    },

    async _rpcIoT(iot_ip, route, params, timeout, fallback, headers) {
        if (isLocalIoTHost(iot_ip) && window.location.protocol === "https:") {
            const ip = extractRawIp(iot_ip);

            // 1) Try proxy through Odoo server (funciona si servidor e IoT red misma LAN)
            try {
                const resp = await fetch("/l10n_ve_iot/action", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        iot_ip: ip,
                        route,
                        params,
                        timeout: Math.min((timeout || this.ACTION_TIMEOUT) / 1000, 120),
                    }),
                });
                const result = await resp.json();
                if (result?.status !== "unreachable" && !result?.error) {
                    return result;
                }
            } catch (_) {}

            // 2) Proxy falló. Intentar directo con LNA (targetAddressSpace:local)
            //    No depende de que el post() de Odoo tenga soporte LNA.
            try {
                const url = `http://${ip}/${route}`;
                const resp = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ params }),
                    targetAddressSpace: "local",
                });
                return await resp.json();
            } catch (error) {
                if (!fallback && error?.name !== "AbortError") {
                    this._doWarnFail(iot_ip);
                }
                throw error;
            }
        }

        // Direct connection (HTTP page or non-local IP)
        const originalUseLna = this.useLna;
        if (isLocalIoTHost(iot_ip)) {
            this.useLna = true;
        }
        try {
            return await super._rpcIoT(iot_ip, route, params, timeout, fallback, headers);
        } finally {
            this.useLna = originalUseLna;
        }
    }
});
