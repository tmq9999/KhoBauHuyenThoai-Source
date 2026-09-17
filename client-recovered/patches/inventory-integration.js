(function (root) {
    "use strict";

    var USE_ITEM = "logic.playerHandler.useItem";
    var attached = false;
    var fenced = false;
    var bridge = null;
    var runtime = null;
    var generation = 0;

    function own(object, key) {
        return Object.prototype.hasOwnProperty.call(object, key);
    }

    function errorCode(error, fallback) {
        return error && typeof error.code === "string" && /^[A-Z0-9_]{1,64}$/.test(error.code) ? error.code : fallback;
    }

    function safeError(code, expected) {
        if (runtime && (expected === undefined || expected === generation)) runtime.sync({code: 500, msg: code});
    }

    function validLoopback(url) {
        var match = typeof url === "string" && /^ws:\/\/(?:127\.0\.0\.1|\[::1\]):([0-9]{1,5})\/inventory$/.exec(url);
        var port = match && Number(match[1]);
        return !!match && port >= 1 && port <= 65535;
    }

    function validScope(expected) {
        var player;
        if (!runtime || expected !== generation) return false;
        player = runtime.getPlayer();
        return !!player && player.id === runtime.playerId && player.serverId === runtime.serverId;
    }

    function replacement(snapshot, expected) {
        if (!validScope(expected)) return;
        var player = runtime.getPlayer();
        var oldItems = player && player.bag && player.bag.items || {};
        var nextItems = snapshot && snapshot.bag && snapshot.bag.items || {};
        var items = {};
        var key;
        for (key in oldItems) if (own(oldItems, key)) items[key] = null;
        for (key in nextItems) if (own(nextItems, key)) items[key] = nextItems[key];
        runtime.sync({bag: {items: items}});
    }

    function attach(options) {
        var player;
        var module;
        var deps;
        var token;
        var callback;
        if (attached) throw new Error("inventory integration already attached");
        if (!options || options.inventoryIdentity !== "postgres-v1" || !validLoopback(options.url) ||
                typeof options.token !== "string" || !options.token || !options.hello ||
                typeof options.getPlayer !== "function" || typeof options.sync !== "function" ||
                typeof options.showRewards !== "function" || typeof options.nextActionId !== "function" ||
                typeof options.suspendLegacy !== "function") {
            throw new Error("invalid inventory integration options");
        }
        player = options.getPlayer();
        if (!player || player.id !== options.hello.playerId || player.serverId !== options.hello.serverId) throw new Error("inventory player scope mismatch");
        module = options.bridgeModule || root.kbhtInventoryBridge;
        deps = options.deps;
        if (!module || typeof module.createBridge !== "function" || !deps || typeof deps.WebSocket !== "function" ||
                typeof deps.setTimeout !== "function" || typeof deps.clearTimeout !== "function") {
            throw new Error("inventory bridge dependencies missing");
        }
        runtime = {
            getPlayer: options.getPlayer,
            sync: options.sync,
            showRewards: options.showRewards,
            nextActionId: options.nextActionId,
            playerId: options.hello.playerId,
            serverId: options.hello.serverId
        };
        fenced = true;
        options.suspendLegacy();
        attached = true;
        generation += 1;
        var activeGeneration = generation;
        bridge = module.createBridge({
            WebSocket: deps.WebSocket,
            setTimeout: deps.setTimeout,
            clearTimeout: deps.clearTimeout,
            onSnapshot: function (snapshot) { replacement(snapshot, activeGeneration); },
            onDelta: function (delta) { if (validScope(activeGeneration)) runtime.sync({bag: delta.bag}); },
            onReward: function (reward) { if (validScope(activeGeneration)) runtime.showRewards(reward); },
            onError: function (error) { safeError(errorCode(error, "INVENTORY_ERROR"), activeGeneration); }
        });
        token = options.token;
        callback = typeof options.callback === "function" ? options.callback : function () {};
        bridge.connect({url: options.url, token: token, hello: options.hello}, function (error, value) {
            token = null;
            if (!validScope(activeGeneration)) return;
            callback(error ? {code: errorCode(error, "INVENTORY_ERROR")} : null, value);
        });
    }

    function handleRequest(route, message, callback) {
        var actionId;
        if (!fenced) return false;
        if (!attached || !bridge) {
            safeError("INVENTORY_DETACHED");
            return true;
        }
        if (!validScope(generation)) {
            safeError("INVENTORY_SCOPE_CHANGED");
            return true;
        }
        if (route !== USE_ITEM) {
            safeError("ONLINE_ROUTE_BLOCKED");
            return true;
        }
        if (!message || typeof message.bagIndex !== "string" || typeof message.itemCount !== "number") {
            safeError("VALIDATION_ERROR");
            return true;
        }
        try {
            actionId = runtime.nextActionId();
        } catch (ignored) {
            safeError("ACTION_ID_UNAVAILABLE");
            return true;
        }
        if (typeof actionId !== "string") {
            safeError("ACTION_ID_UNAVAILABLE");
            return true;
        }
        var requestGeneration = generation;
        bridge.useItem(actionId, message.bagIndex, message.itemCount, function (error, result) {
            if (!validScope(requestGeneration)) return;
            // The bridge's onError is authoritative for native error UI.
            // Validation/domain/fatal errors also complete action callbacks;
            // forwarding both paths would dismiss loading and show hints twice.
            // Explicit close is handled by detach before its generation fence.
            if (error) return;
            if (typeof callback === "function") callback({_temp: {route: USE_ITEM}});
        });
        return true;
    }

    function reconnect(token, callback) {
        if (!attached || !bridge || typeof token !== "string" || !token) throw new Error("inventory integration is not attached");
        if (!validScope(generation)) throw new Error("inventory player scope mismatch");
        var reconnectGeneration = generation;
        bridge.reconnect(token, function (error, value) {
            if (!validScope(reconnectGeneration)) return;
            if (typeof callback === "function") callback(error ? {code: errorCode(error, "INVENTORY_ERROR")} : null, value);
        });
    }

    function detach() {
        var wasAttached = attached;
        fenced = true;
        attached = false;
        if (wasAttached && runtime) runtime.sync({code: 500, msg: "INVENTORY_DETACHED"});
        generation += 1;
        if (bridge) bridge.close();
        bridge = null;
    }

    var api = {attach: attach, detach: detach, reconnect: reconnect, handleRequest: handleRequest};
    root.kbhtInventoryIntegration = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window !== "undefined" ? window : this));
