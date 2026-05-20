/** @odoo-module **/

import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import { post } from '@iot_base/network_utils/http';
import { IoTLongpolling } from '@iot_base/network_utils/longpolling';

const PRIVATE_IP_HOST_RE = /^(\d+)-(\d+)-(\d+)-(\d+)(?:\..*)?$/;
const PRIVATE_IP_RE = /^(\d{1,3}\.){3}\d{1,3}$/;

function isLocalIoTHost(host) {
  if (!host) {
    return false;
  }
  return PRIVATE_IP_HOST_RE.test(host) || PRIVATE_IP_RE.test(host);
}

export class BinauralIoTLongpolling extends IoTLongpolling {
  setup(deps) {
    super.setup(...arguments);
    this.POLL_TIMEOUT = 6000000;
    this.ACTION_TIMEOUT = 1600000;
    if (typeof odoo !== 'undefined' && 'use_lna' in odoo) {
      this.setLna(Boolean(odoo.use_lna));
    }
  }

  action(iot_ip, device_identifier, data, fallback = false, route = null) {
    this.protocol = window.location.protocol;
    const body = {
      session_id: this._session_id,
      device_identifier: device_identifier,
      data,
    };
    return this._rpcIoT(
      iot_ip,
      route || this.actionRoute,
      body,
      this.ACTION_TIMEOUT,
      fallback
    );
  }

  async _rpcIoT(iot_ip, route, params, timeout = undefined, fallback = false, headers = undefined) {
    try {
      const abortController = new AbortController();
      const useLna = this.useLna || isLocalIoTHost(iot_ip);

      if (this._listeners[iot_ip] && route === this.pollRoute) {
        this._listeners[iot_ip].abortController = abortController;
      }

      return await post(iot_ip, route, params, timeout, headers, abortController.signal, useLna);
    } catch (error) {
      const debugContext = {
        iot_ip,
        route,
        timeout,
        fallback,
        useLna: this.useLna || isLocalIoTHost(iot_ip),
        errorName: error?.name,
        errorMessage: error?.message,
        errorCause: error?.cause?.message,
      };

      console.error('IoT RPC failed', debugContext, error);

      if (!fallback && error?.name !== 'AbortError') {
        this._doWarnFail(iot_ip);
        this.notification?.add(
          `${_t('IoT request failed')}: ${error?.message || _t('Unknown error')}`,
          {
            title: _t('IoT communication error'),
            type: 'danger',
          }
        );
      }

      error.iotContext = debugContext;
      throw error;
    }
  }

  _poll(iot_ip, fallback = true) {
    const listener = this._listeners[iot_ip];

    this._rpcIoT(iot_ip, this.pollRoute, { listener: listener }, this.POLL_TIMEOUT, fallback).then(
      (result) => {
        this._retries = 0;
        this._listeners[iot_ip].abortController = null;
        if (result.result) {
          if (this._session_id === result.result.session_id) {
            this._onSuccess(iot_ip, result.result);
          }
        }
        const remainingDevices = Object.keys(this._listeners[iot_ip].devices || {});
        if (remainingDevices.length > 0 && !this._listeners[iot_ip].abortController) {
          this._poll(iot_ip);
        }
      },
      (error) => {
        if (error.name === 'TimeoutError') {
          this._onPollTimeout();
        } else {
          this._onPollNetworkError(iot_ip);
        }
      }
    );
  }
}

export const iotLongpollingService = {
  dependencies: IoTLongpolling.serviceDependencies,
  start(_, deps) {
    return new BinauralIoTLongpolling(deps);
  }
};

registry.category('services').add('iot_longpolling', iotLongpollingService, { force: true });
