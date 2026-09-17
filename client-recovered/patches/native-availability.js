/* Source-consumer guards only. No player, products, prices or rewards invented. */
(function (root) {
    "use strict";
    var api = {
        hasServers: function (reply) {
            if (!reply || reply.code === 500 || reply.code === 503 || reply.code === 504 ||
                    !Array.isArray(reply.serverList) || reply.serverList.length === 0) return false;
            for (var i = 0; i < reply.serverList.length; i++) {
                var row = reply.serverList[i];
                if (!row || typeof row.serverId !== "number" || row.serverId <= 0 ||
                        Math.floor(row.serverId) !== row.serverId || row.serverId > 2147483647 ||
                        row.oldServerId !== row.serverId || typeof row.name !== "string" || !row.name) return false;
            }
            return true;
        },
        entryAccepted: function (reply) {
            return !!reply && reply.code === 200;
        },
        gateAccepted: function (reply) {
            return !!reply && reply.code === 200 &&
                (reply.host === "127.0.0.1" || reply.host === "[::1]") &&
                typeof reply.port === "number" && Math.floor(reply.port) === reply.port &&
                reply.port > 0 && reply.port <= 65535;
        },
        connectorTarget: function (reply, alias) {
            if (!api.gateAccepted(reply)) return null;
            if (!alias) return {host: reply.host, port: reply.port};
            var host = alias.connectorHostMap && alias.connectorHostMap[reply.port];
            var port = alias.connectorPortMap && alias.connectorPortMap[reply.port];
            return api.gateAccepted({code: 200, host: host, port: port}) ? {host: host, port: port} : null;
        },
        shopBadge: function (items) {
            return !!(items && ((items[0] && !items[0].isSaleOut) || (items[1] && !items[1].isSaleOut)));
        }
    };
    root.kbhtNativeAvailability = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window !== "undefined" ? window : this));
