/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";

const DEFAULT_MESSAGE_DURATION_MS = 5000;

export class Root extends Component {
    static template = "cadipa_hikvision.Root";

    setup() {
        this.state = useState({
            currentMessage: null,
            isWaiting: true,
            backgroundColor: null,
            waitingMessage: "Esperando...",
            waitingColor: "#2c3e50",
        });

        this.channel = "cadipa_hikvision_test_channel";
        this.messageTimeout = null;

        onWillStart(async () => {
            try {
                const config = await jsonrpc("/cadipa_hikvision/get_waiting_config");
                if (config) {
                    this.state.waitingMessage = config.waiting_message || "Esperando...";
                    this.state.waitingColor = config.waiting_color || "#2c3e50";
                }
            } catch (error) {
                console.error("Error getting waiting configuration:", error);
            }

            this.busService = this.env.services.bus_service;
            if (this.busService) {
                this.busService.addChannel(this.channel);
                this.busService.addEventListener("notification", this.onMessage);
            }
        });

        onWillUnmount(() => {
            if (this.messageTimeout) clearTimeout(this.messageTimeout);
            if (this.busService) {
                this.busService.deleteChannel(this.channel);
                this.busService.removeEventListener("notification", this.onMessage);
            }
        });
    }

    onMessage = ({ detail: notifications }) => {
        if (!notifications) return;
        const items = notifications.filter(
            (item) => item.payload.channel === this.channel
        );
        if (!items.length) return;

        if (this.messageTimeout) clearTimeout(this.messageTimeout);

        const last = items[items.length - 1];
        const messageData = last.payload.data;
        
        this.state.currentMessage = messageData;
        this.state.isWaiting = false;
        
        if (messageData.color) {
            const color = messageData.color.startsWith('#') 
                ? messageData.color 
                : `#${messageData.color}`;
            this.state.backgroundColor = color;
        } else {
            this.state.backgroundColor = null;
        }
        
        const duration = messageData.duration_ms || DEFAULT_MESSAGE_DURATION_MS;
        
        this.messageTimeout = setTimeout(() => {
            this.messageTimeout = null;
            this.state.currentMessage = null;
            this.state.isWaiting = true;
            this.state.backgroundColor = null;
        }, duration);
    };
}

export default Root;