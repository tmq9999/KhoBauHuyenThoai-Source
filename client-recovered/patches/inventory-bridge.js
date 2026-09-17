(function (root) {
    "use strict";

    var HANDSHAKE = 1;
    var HANDSHAKE_ACK = 2;
    var DATA = 4;
    var REQUEST = 0;
    var RESPONSE = 2;
    var USE_ITEM_ROUTE = "logic.playerHandler.useItem";
    var RESYNC_ROUTE = "connector.inventoryHandler.resync";
    var MAX_REQUEST_FRAME_SIZE = 65536;
    var MAX_RESPONSE_FRAME_SIZE = 1048576;
    var MAX_QUEUED_ACTIONS = 16;
    var MAX_QUEUED_RESYNCS = 16;
    var MAX_COMPLETED_HISTORY = 64;
    var REQUEST_TIMEOUT_MS = 10000;
    var MAX_SAFE_INTEGER = 9007199254740991;
    var UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    var BAG_INDEX_PATTERN = /^[1-9][0-9]{0,15}$/;

    function noop() {}

    function own(object, key) {
        return Object.prototype.hasOwnProperty.call(object, key);
    }

    function keysExactly(object, expected) {
        var actual;
        var index;
        if (!object || Object.prototype.toString.call(object) !== "[object Object]") return false;
        actual = Object.keys(object);
        if (actual.length !== expected.length) return false;
        for (index = 0; index < expected.length; index += 1) {
            if (!own(object, expected[index])) return false;
        }
        return true;
    }

    function isInteger(value) {
        return typeof value === "number" && isFinite(value) && Math.floor(value) === value;
    }

    function isUuid(value) {
        return typeof value === "string" && UUID_PATTERN.test(value);
    }

    function bridgeError(code) {
        var error = new Error(code);
        error.code = code;
        return error;
    }

    function copy(value) {
        var result;
        var key;
        var index;
        if (value === null || typeof value !== "object") return value;
        if (Object.prototype.toString.call(value) === "[object Array]") {
            result = [];
            for (index = 0; index < value.length; index += 1) result[index] = copy(value[index]);
            return result;
        }
        result = {};
        for (key in value) {
            if (own(value, key)) result[key] = copy(value[key]);
        }
        return result;
    }

    function utf8Encode(value) {
        var output = [];
        var index;
        var code;
        var next;
        for (index = 0; index < value.length; index += 1) {
            code = value.charCodeAt(index);
            if (code >= 0xD800 && code <= 0xDBFF) {
                if (index + 1 >= value.length) throw bridgeError("INVALID_TEXT");
                next = value.charCodeAt(index + 1);
                if (next < 0xDC00 || next > 0xDFFF) throw bridgeError("INVALID_TEXT");
                code = 0x10000 + ((code - 0xD800) * 1024) + (next - 0xDC00);
                index += 1;
            } else if (code >= 0xDC00 && code <= 0xDFFF) {
                throw bridgeError("INVALID_TEXT");
            }
            if (code < 0x80) output.push(code);
            else if (code < 0x800) output.push(0xC0 | (code >> 6), 0x80 | (code & 0x3F));
            else if (code < 0x10000) output.push(0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
            else output.push(0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F));
        }
        return new Uint8Array(output);
    }

    function utf8Decode(input) {
        var output = "";
        var index = 0;
        var first;
        var second;
        var third;
        var fourth;
        var code;
        while (index < input.length) {
            first = input[index];
            index += 1;
            if (first < 0x80) {
                output += String.fromCharCode(first);
            } else if (first >= 0xC2 && first <= 0xDF) {
                if (index >= input.length) throw bridgeError("INVALID_TEXT");
                second = input[index];
                index += 1;
                if ((second & 0xC0) !== 0x80) throw bridgeError("INVALID_TEXT");
                output += String.fromCharCode(((first & 0x1F) << 6) | (second & 0x3F));
            } else if (first >= 0xE0 && first <= 0xEF) {
                if (index + 1 >= input.length) throw bridgeError("INVALID_TEXT");
                second = input[index];
                third = input[index + 1];
                index += 2;
                if ((second & 0xC0) !== 0x80 || (third & 0xC0) !== 0x80 ||
                        (first === 0xE0 && second < 0xA0) || (first === 0xED && second >= 0xA0)) {
                    throw bridgeError("INVALID_TEXT");
                }
                code = ((first & 0x0F) << 12) | ((second & 0x3F) << 6) | (third & 0x3F);
                output += String.fromCharCode(code);
            } else if (first >= 0xF0 && first <= 0xF4) {
                if (index + 2 >= input.length) throw bridgeError("INVALID_TEXT");
                second = input[index];
                third = input[index + 1];
                fourth = input[index + 2];
                index += 3;
                if ((second & 0xC0) !== 0x80 || (third & 0xC0) !== 0x80 || (fourth & 0xC0) !== 0x80 ||
                        (first === 0xF0 && second < 0x90) || (first === 0xF4 && second >= 0x90)) {
                    throw bridgeError("INVALID_TEXT");
                }
                code = ((first & 7) << 18) | ((second & 0x3F) << 12) | ((third & 0x3F) << 6) | (fourth & 0x3F);
                code -= 0x10000;
                output += String.fromCharCode(0xD800 | (code >> 10), 0xDC00 | (code & 0x3FF));
            } else {
                throw bridgeError("INVALID_TEXT");
            }
        }
        return output;
    }

    function asBytes(value) {
        if (value instanceof Uint8Array) return value;
        if (typeof ArrayBuffer !== "undefined" && value instanceof ArrayBuffer) return new Uint8Array(value);
        if (value && value.buffer instanceof ArrayBuffer && isInteger(value.byteOffset) && isInteger(value.byteLength)) {
            return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
        }
        throw bridgeError("INVALID_FRAME");
    }

    function packageFrame(type, body) {
        var result;
        if (body.length > 0xFFFFFF) throw bridgeError("FRAME_TOO_LARGE");
        result = new Uint8Array(body.length + 4);
        result[0] = type;
        result[1] = (body.length >>> 16) & 255;
        result[2] = (body.length >>> 8) & 255;
        result[3] = body.length & 255;
        result.set(body, 4);
        return result;
    }

    function decodePackage(value) {
        var input = asBytes(value);
        var length;
        if (input.length > MAX_RESPONSE_FRAME_SIZE) throw bridgeError("FRAME_TOO_LARGE");
        if (input.length < 4) throw bridgeError("INVALID_FRAME");
        length = (input[1] * 65536) + (input[2] * 256) + input[3];
        if (input.length !== length + 4) throw bridgeError("INVALID_FRAME");
        return {type: input[0], body: input.subarray(4)};
    }

    function encodeVarint(value) {
        var output = [];
        var part;
        do {
            part = value % 128;
            value = Math.floor(value / 128);
            if (value) part += 128;
            output.push(part);
        } while (value);
        return output;
    }

    function encodeRequest(requestId, route, payloadText) {
        var routeBytes = utf8Encode(route);
        var payloadBytes = utf8Encode(payloadText);
        var idBytes = encodeVarint(requestId);
        var body;
        var offset = 0;
        var index;
        if (routeBytes.length > 255) throw bridgeError("INVALID_ROUTE");
        body = new Uint8Array(2 + idBytes.length + routeBytes.length + payloadBytes.length);
        body[offset] = REQUEST << 1;
        offset += 1;
        for (index = 0; index < idBytes.length; index += 1) body[offset + index] = idBytes[index];
        offset += idBytes.length;
        body[offset] = routeBytes.length;
        offset += 1;
        body.set(routeBytes, offset);
        offset += routeBytes.length;
        body.set(payloadBytes, offset);
        if (body.length + 4 > MAX_REQUEST_FRAME_SIZE) throw bridgeError("FRAME_TOO_LARGE");
        return packageFrame(DATA, body);
    }

    function decodeResponse(body) {
        var offset = 1;
        var requestId = 0;
        var multiplier = 1;
        var count = 0;
        var part;
        var payload;
        if (!body.length || body[0] !== (RESPONSE << 1)) throw bridgeError("INVALID_REPLY");
        do {
            if (offset >= body.length || count >= 5) throw bridgeError("INVALID_REPLY");
            part = body[offset];
            offset += 1;
            requestId += (part & 0x7F) * multiplier;
            multiplier *= 128;
            count += 1;
        } while (part & 0x80);
        if (!requestId || requestId > 0xFFFFFFFF || offset >= body.length) throw bridgeError("INVALID_REPLY");
        try {
            payload = JSON.parse(utf8Decode(body.subarray(offset)));
        } catch (error) {
            throw bridgeError("INVALID_REPLY");
        }
        if (!payload || Object.prototype.toString.call(payload) !== "[object Object]") throw bridgeError("INVALID_REPLY");
        return {requestId: requestId, payload: payload};
    }

    function validateUrl(value) {
        var authority;
        if (typeof value !== "string" || value.length < 6 || value.length > 2048 ||
                !/^wss?:\/\//.test(value) || /[?#]/.test(value)) return false;
        authority = value.replace(/^wss?:\/\//, "").split("/")[0];
        return authority.length > 0 && authority.indexOf("@") < 0;
    }

    function validateHello(value) {
        var capabilities;
        var index;
        var found = false;
        if (!keysExactly(value, ["protocolVersion", "capabilities", "playerId", "serverId", "contentVersionId"])) return false;
        capabilities = value.capabilities;
        if (value.protocolVersion !== 1 || !isInteger(value.playerId) || value.playerId <= 0 || value.playerId > MAX_SAFE_INTEGER ||
                !isInteger(value.serverId) || value.serverId <= 0 || value.serverId > 2147483647 || !isUuid(value.contentVersionId) ||
                Object.prototype.toString.call(capabilities) !== "[object Array]" || capabilities.length < 1 || capabilities.length > 16) {
            return false;
        }
        for (index = 0; index < capabilities.length; index += 1) {
            if (typeof capabilities[index] !== "string" || capabilities[index].length < 1 || capabilities[index].length > 64) return false;
            if (capabilities.indexOf(capabilities[index]) !== index) return false;
            if (capabilities[index] === "native-inventory-v1") found = true;
        }
        return found;
    }

    function validateItems(items) {
        var key;
        var row;
        if (!items || Object.prototype.toString.call(items) !== "[object Object]") return false;
        for (key in items) {
            if (own(items, key)) {
                if (!BAG_INDEX_PATTERN.test(key) || Number(key) > MAX_SAFE_INTEGER) return false;
                row = items[key];
                if (!keysExactly(row, ["kindId", "count"]) || !isInteger(row.kindId) || row.kindId <= 0 ||
                        !isInteger(row.count) || row.count <= 0 || row.count > MAX_SAFE_INTEGER) return false;
            }
        }
        return true;
    }

    function validateDeltaItems(items) {
        var key;
        var row;
        if (!items || Object.prototype.toString.call(items) !== "[object Object]") return false;
        for (key in items) {
            if (own(items, key)) {
                if (!BAG_INDEX_PATTERN.test(key) || Number(key) > MAX_SAFE_INTEGER) return false;
                row = items[key];
                if (row !== null && (!keysExactly(row, ["kindId", "count"]) || !isInteger(row.kindId) || row.kindId <= 0 ||
                        !isInteger(row.count) || row.count <= 0 || row.count > MAX_SAFE_INTEGER)) return false;
            }
        }
        return true;
    }

    function validateSnapshot(snapshot, contentVersionId) {
        return keysExactly(snapshot, ["version", "contentVersionId", "bag"]) &&
            isInteger(snapshot.version) && snapshot.version >= 0 && snapshot.version < 2147483647 &&
            snapshot.contentVersionId === contentVersionId && keysExactly(snapshot.bag, ["items"]) &&
            validateItems(snapshot.bag.items);
    }

    function createBridge(options) {
        var WebSocketImpl;
        var setTimer;
        var clearTimer;
        var onSnapshot;
        var onDelta;
        var onReward;
        var onError;
        var state = {status: "idle", version: null, bag: {items: {}}};
        var url = null;
        var hello = null;
        var contentVersionId = null;
        var socket = null;
        var socketSerial = 0;
        var connectCallback = null;
        var actions = [];
        var active = null;
        var timer = null;
        var nextRequestId = 1;
        var explicitResyncCallbacks = [];
        var completedActions = {};
        var completedOrder = [];

        if (!options || typeof options.WebSocket !== "function" || typeof options.setTimeout !== "function" ||
                typeof options.clearTimeout !== "function") throw bridgeError("INVALID_OPTIONS");
        WebSocketImpl = options.WebSocket;
        setTimer = options.setTimeout;
        clearTimer = options.clearTimeout;
        onSnapshot = typeof options.onSnapshot === "function" ? options.onSnapshot : noop;
        onDelta = typeof options.onDelta === "function" ? options.onDelta : noop;
        onReward = typeof options.onReward === "function" ? options.onReward : noop;
        onError = typeof options.onError === "function" ? options.onError : noop;

        function invoke(callback, error, value) {
            try {
                callback(error, value === undefined ? undefined : copy(value));
            } catch (ignored) {}
        }

        function publish(callback, value) {
            try {
                callback(copy(value));
            } catch (ignored) {}
        }

        function report(error) {
            publish(onError, error);
        }

        function clearRequestTimer() {
            if (timer !== null) {
                clearTimer(timer);
                timer = null;
            }
        }

        function detachAndClose() {
            var current = socket;
            socket = null;
            socketSerial += 1;
            if (current) {
                if (typeof current._kbhtClearCredential === "function") current._kbhtClearCredential();
                current.onopen = noop;
                current.onmessage = noop;
                current.onerror = noop;
                current.onclose = noop;
                try { current.close(); } catch (ignored) {}
            }
        }

        function rejectResyncs(error) {
            var callbacks = explicitResyncCallbacks;
            var index;
            explicitResyncCallbacks = [];
            for (index = 0; index < callbacks.length; index += 1) invoke(callbacks[index], error);
        }

        function rejectActions(error) {
            var pending = actions;
            var index;
            actions = [];
            active = null;
            for (index = 0; index < pending.length; index += 1) invoke(pending[index].callback, error);
        }

        function fatal(code, rejectPending) {
            var error = bridgeError(code);
            clearRequestTimer();
            detachAndClose();
            state.status = "error";
            if (connectCallback) {
                invoke(connectCallback, error);
                connectCallback = null;
            }
            if (rejectPending) {
                rejectActions(error);
                rejectResyncs(error);
            }
            report(error);
        }

        function armTimeout() {
            clearRequestTimer();
            timer = setTimer(function () {
                var error;
                timer = null;
                if (!active || state.status !== "ready") return;
                error = bridgeError("TIMEOUT");
                active = null;
                detachAndClose();
                state.status = "disconnected";
                rejectResyncs(error);
                report(error);
            }, REQUEST_TIMEOUT_MS);
        }

        function armHandshakeTimeout() {
            clearRequestTimer();
            timer = setTimer(function () {
                var error;
                timer = null;
                if (state.status !== "connecting") return;
                error = bridgeError("TIMEOUT");
                detachAndClose();
                state.status = "disconnected";
                if (connectCallback) {
                    invoke(connectCallback, error);
                    connectCallback = null;
                }
                report(error);
            }, REQUEST_TIMEOUT_MS);
        }

        function requestId() {
            var value = nextRequestId;
            nextRequestId += 1;
            if (nextRequestId > 0xFFFFFFFF) nextRequestId = 1;
            return value;
        }

        function sendRequest(kind, route, payloadText, extra) {
            var id = requestId();
            active = {kind: kind, requestId: id, extra: extra || null};
            socket.send(encodeRequest(id, route, payloadText));
            armTimeout();
        }

        function installSnapshot(snapshot) {
            state.version = snapshot.version;
            state.bag = copy(snapshot.bag);
            publish(onSnapshot, {version: snapshot.version, contentVersionId: snapshot.contentVersionId, bag: snapshot.bag});
        }

        function applyDelta(result) {
            var items = result.result.bag.items;
            var key;
            var delta;
            var rewards;
            for (key in items) {
                if (own(items, key)) {
                    if (items[key] === null) delete state.bag.items[key];
                    else state.bag.items[key] = copy(items[key]);
                }
            }
            state.version = result.version;
            delta = {version: result.version, contentVersionId: result.contentVersionId, bag: {items: items}};
            publish(onDelta, delta);
            rewards = result.result._temp.entityCountMap;
            if (Object.keys(rewards).length) publish(onReward, rewards);
        }

        function finishMutation(entry, result, apply) {
            if (actions[0] !== entry) {
                fatal("UNKNOWN_REPLY", true);
                return;
            }
            if (apply) applyDelta(result);
            actions.shift();
            completedActions[entry.actionId] = entry;
            completedOrder.push(entry.actionId);
            if (completedOrder.length > MAX_COMPLETED_HISTORY) delete completedActions[completedOrder.shift()];
            invoke(entry.callback, null, result);
            dispatch();
        }

        function dispatch() {
            var entry;
            var envelope;
            if (state.status !== "ready" || active) return;
            if (explicitResyncCallbacks.length) {
                sendRequest("resync", RESYNC_ROUTE, "{}", null);
                return;
            }
            if (!actions.length) return;
            entry = actions[0];
            if (entry.envelopeText === null) {
                envelope = {
                    command_id: entry.actionId,
                    player_id: hello.playerId,
                    server_id: hello.serverId,
                    route: USE_ITEM_ROUTE,
                    expected_version: state.version,
                    content_version_id: contentVersionId,
                    payload: {bagIndex: entry.bagIndex, itemCount: entry.itemCount}
                };
                entry.expectedVersion = state.version;
                entry.envelopeText = JSON.stringify(envelope);
            }
            sendRequest("mutation", USE_ITEM_ROUTE, entry.envelopeText, entry);
        }

        function validateMutationReply(payload, entry) {
            var result;
            var rewards;
            if (!keysExactly(payload, ["code", "commandId", "version", "contentVersionId", "result", "eventIds"]) ||
                    payload.code !== 200 || payload.commandId !== entry.actionId ||
                    !isInteger(payload.version) || payload.version < 0 || payload.version >= 2147483647 ||
                    payload.contentVersionId !== contentVersionId || !keysExactly(payload.result, ["bag", "_temp"]) ||
                    !keysExactly(payload.result.bag, ["items"]) || !validateDeltaItems(payload.result.bag.items) ||
                    !keysExactly(payload.result._temp, ["route", "entityCountMap"]) ||
                    payload.result._temp.route !== USE_ITEM_ROUTE ||
                    !payload.result._temp.entityCountMap || Object.prototype.toString.call(payload.result._temp.entityCountMap) !== "[object Object]" ||
                    Object.prototype.toString.call(payload.eventIds) !== "[object Array]") return false;
            rewards = payload.result._temp.entityCountMap;
            for (result in rewards) {
                if (own(rewards, result) && (!/^[1-9][0-9]*$/.test(result) || !isInteger(rewards[result]) || rewards[result] <= 0)) return false;
            }
            for (result = 0; result < payload.eventIds.length; result += 1) if (!isUuid(payload.eventIds[result])) return false;
            return true;
        }

        function handleDomainError(payload) {
            var error;
            var entry;
            if (!keysExactly(payload, ["code", "error"]) || payload.code !== 500 ||
                    !keysExactly(payload.error, ["code"]) || typeof payload.error.code !== "string") {
                fatal("INVALID_REPLY", true);
                return;
            }
            error = bridgeError(payload.error.code);
            if (active.kind === "mutation") {
                entry = active.extra;
                if (actions[0] !== entry) {
                    fatal("UNKNOWN_REPLY", true);
                    return;
                }
                actions.shift();
                active = null;
                invoke(entry.callback, error);
            } else {
                active = null;
                rejectResyncs(error);
            }
            if (error.code === "UNAUTHENTICATED") {
                detachAndClose();
                state.status = "error";
                rejectActions(error);
                rejectResyncs(error);
                report(error);
                return;
            }
            report(error);
            if (error.code === "CONFLICT" && state.status === "ready") {
                sendRequest("conflict-resync", RESYNC_ROUTE, "{}", null);
                return;
            }
            dispatch();
        }

        function handleResync(payload, context) {
            var snapshot;
            var callbacks;
            var index;
            if (!keysExactly(payload, ["code", "result"]) || payload.code !== 200 ||
                    !keysExactly(payload.result, ["snapshotMode", "fullPlayerSnapshot", "snapshot"]) ||
                    payload.result.snapshotMode !== "replace-bag" || payload.result.fullPlayerSnapshot !== false ||
                    !validateSnapshot(payload.result.snapshot, contentVersionId)) {
                fatal("INVALID_REPLY", true);
                return;
            }
            snapshot = payload.result.snapshot;
            if (snapshot.version < state.version || (context && snapshot.version < context.targetVersion)) {
                active = null;
                if (context) {
                    fatal("STALE_SNAPSHOT", true);
                } else {
                    callbacks = explicitResyncCallbacks;
                    explicitResyncCallbacks = [];
                    for (index = 0; index < callbacks.length; index += 1) invoke(callbacks[index], bridgeError("STALE_SNAPSHOT"));
                    report(bridgeError("STALE_SNAPSHOT"));
                    dispatch();
                }
                return;
            }
            installSnapshot(snapshot);
            active = null;
            if (context) {
                finishMutation(context.entry, context.result, false);
                if (Object.keys(context.result.result._temp.entityCountMap).length) {
                    publish(onReward, context.result.result._temp.entityCountMap);
                }
            } else {
                callbacks = explicitResyncCallbacks;
                explicitResyncCallbacks = [];
                for (index = 0; index < callbacks.length; index += 1) invoke(callbacks[index], null, payload.result);
                dispatch();
            }
        }

        function handleResponse(message) {
            var current = active;
            var payload = message.payload;
            var entry;
            if (!current || message.requestId !== current.requestId) {
                if (payload && payload.code === 200 && typeof payload.commandId === "string" && completedActions[payload.commandId]) {
                    if (validateMutationReply(payload, completedActions[payload.commandId])) return;
                    fatal("MISMATCH_REPLY", true);
                    return;
                }
                fatal("UNKNOWN_REPLY", true);
                return;
            }
            clearRequestTimer();
            if (payload.code !== 200) {
                handleDomainError(payload);
                return;
            }
            if (current.kind === "resync" || current.kind === "gap-resync" || current.kind === "conflict-resync") {
                handleResync(payload, current.extra);
                return;
            }
            entry = current.extra;
            if (!validateMutationReply(payload, entry)) {
                fatal("MISMATCH_REPLY", true);
                return;
            }
            active = null;
            if (payload.version === state.version + 1) {
                finishMutation(entry, payload, true);
            } else if (payload.version <= state.version) {
                finishMutation(entry, payload, false);
            } else {
                sendRequest("gap-resync", RESYNC_ROUTE, "{}", {entry: entry, result: payload, targetVersion: payload.version});
            }
        }

        function validateNegotiation(payload) {
            var user;
            if (!keysExactly(payload, ["code", "sys", "user"]) || payload.code !== 200 ||
                    !keysExactly(payload.sys, ["heartbeat", "dict", "protos"]) || payload.sys.heartbeat !== 0 ||
                    !keysExactly(payload.sys.dict, []) || !keysExactly(payload.sys.protos, [])) return null;
            user = payload.user;
            if (!keysExactly(user, ["protocolVersion", "capability", "playerId", "serverId", "contentVersionId", "allowedRoutes", "fullPlayerSnapshot", "snapshotMode", "snapshot"]) ||
                    user.protocolVersion !== 1 || user.capability !== "native-inventory-v1" || user.playerId !== hello.playerId ||
                    user.serverId !== hello.serverId || user.contentVersionId !== hello.contentVersionId ||
                    Object.prototype.toString.call(user.allowedRoutes) !== "[object Array]" || user.allowedRoutes.length !== 1 ||
                    user.allowedRoutes[0] !== USE_ITEM_ROUTE || user.fullPlayerSnapshot !== false ||
                    user.snapshotMode !== "replace-bag" || !validateSnapshot(user.snapshot, hello.contentVersionId)) return null;
            return user;
        }

        function open(token, callback) {
            var serial;
            var suppliedToken = token;
            var current;
            state.status = "connecting";
            connectCallback = callback;
            serial = socketSerial + 1;
            socketSerial = serial;
            try {
                current = new WebSocketImpl(url);
                socket = current;
                current._kbhtClearCredential = function () { suppliedToken = null; };
                current.binaryType = "arraybuffer";
                armHandshakeTimeout();
            } catch (ignored) {
                socket = null;
                suppliedToken = null;
                fatal("CONNECTION_ERROR", false);
                return;
            }
            current.onopen = function () {
                var body;
                if (serial !== socketSerial || socket !== current) return;
                try {
                    body = utf8Encode(JSON.stringify({sys: {type: "kbht-inventory", version: "1"}, user: {token: suppliedToken, hello: hello}}));
                    current.send(packageFrame(HANDSHAKE, body));
                    suppliedToken = null;
                } catch (ignored) {
                    suppliedToken = null;
                    fatal("CONNECTION_ERROR", false);
                }
            };
            current.onmessage = function (event) {
                var packet;
                var payload;
                var user;
                var message;
                if (serial !== socketSerial || socket !== current) return;
                try {
                    packet = decodePackage(event.data);
                    if (state.status === "connecting") {
                        if (packet.type !== HANDSHAKE) throw bridgeError("INVALID_HANDSHAKE");
                        payload = JSON.parse(utf8Decode(packet.body));
                        user = validateNegotiation(payload);
                        if (!user) throw bridgeError("INVALID_HANDSHAKE");
                        if (state.version !== null && user.snapshot.version < state.version) throw bridgeError("STALE_SNAPSHOT");
                        clearRequestTimer();
                        installSnapshot(user.snapshot);
                        current.send(packageFrame(HANDSHAKE_ACK, new Uint8Array(0)));
                        state.status = "ready";
                        callback = connectCallback;
                        connectCallback = null;
                        invoke(callback, null, user);
                        dispatch();
                    } else if (state.status === "ready") {
                        if (packet.type !== DATA) throw bridgeError("INVALID_REPLY");
                        message = decodeResponse(packet.body);
                        handleResponse(message);
                    } else {
                        throw bridgeError("INVALID_REPLY");
                    }
                } catch (error) {
                    fatal(error && error.code ? error.code : "INVALID_REPLY", true);
                }
            };
            current.onerror = noop;
            current.onclose = function () {
                var error;
                if (serial !== socketSerial || socket !== current || state.status === "closed") return;
                clearRequestTimer();
                if (typeof current._kbhtClearCredential === "function") current._kbhtClearCredential();
                socket = null;
                active = null;
                state.status = "disconnected";
                error = bridgeError("CONNECTION_CLOSED");
                if (connectCallback) {
                    invoke(connectCallback, error);
                    connectCallback = null;
                }
                rejectResyncs(error);
                report(error);
            };
        }

        function connect(settings, callback) {
            var error;
            callback = typeof callback === "function" ? callback : noop;
            if (state.status !== "idle") {
                invoke(callback, bridgeError("ALREADY_CONNECTED"));
                return;
            }
            if (!settings || !validateUrl(settings.url) || typeof settings.token !== "string" ||
                    settings.token.length < 1 || settings.token.length > 4096 || !validateHello(settings.hello)) {
                error = bridgeError("VALIDATION_ERROR");
                invoke(callback, error);
                report(error);
                return;
            }
            url = settings.url;
            hello = copy(settings.hello);
            contentVersionId = hello.contentVersionId;
            open(settings.token, callback);
        }

        function reconnect(token, callback) {
            var error;
            callback = typeof callback === "function" ? callback : noop;
            if (state.status === "closed") {
                invoke(callback, bridgeError("CLOSED"));
                return;
            }
            if (!url || !hello || (state.status !== "disconnected" && state.status !== "error") ||
                    typeof token !== "string" || token.length < 1 || token.length > 4096) {
                error = bridgeError("VALIDATION_ERROR");
                invoke(callback, error);
                report(error);
                return;
            }
            clearRequestTimer();
            detachAndClose();
            open(token, callback);
        }

        function useItem(actionId, bagIndex, itemCount, callback) {
            var error;
            callback = typeof callback === "function" ? callback : noop;
            if (state.status === "closed") {
                invoke(callback, bridgeError("CLOSED"));
                return;
            }
            if (!isUuid(actionId) || typeof bagIndex !== "string" || !BAG_INDEX_PATTERN.test(bagIndex) ||
                    Number(bagIndex) > MAX_SAFE_INTEGER || !isInteger(itemCount) || itemCount < 1 || itemCount > 100) {
                error = bridgeError("VALIDATION_ERROR");
                invoke(callback, error);
                report(error);
                return;
            }
            if (completedActions[actionId]) {
                error = bridgeError("DUPLICATE_ACTION");
                invoke(callback, error);
                report(error);
                return;
            }
            for (var index = 0; index < actions.length; index += 1) {
                if (actions[index].actionId === actionId) {
                    error = bridgeError("DUPLICATE_ACTION");
                    invoke(callback, error);
                    report(error);
                    return;
                }
            }
            if (actions.length >= MAX_QUEUED_ACTIONS) {
                error = bridgeError("QUEUE_FULL");
                invoke(callback, error);
                report(error);
                return;
            }
            actions.push({actionId: actionId, bagIndex: bagIndex, itemCount: itemCount, callback: callback, envelopeText: null, expectedVersion: null});
            dispatch();
        }

        function resync(callback) {
            var error;
            callback = typeof callback === "function" ? callback : noop;
            if (state.status !== "ready") {
                error = bridgeError(state.status === "closed" ? "CLOSED" : "NOT_CONNECTED");
                invoke(callback, error);
                report(error);
                return;
            }
            if (explicitResyncCallbacks.length >= MAX_QUEUED_RESYNCS) {
                error = bridgeError("QUEUE_FULL");
                invoke(callback, error);
                report(error);
                return;
            }
            explicitResyncCallbacks.push(callback);
            dispatch();
        }

        function close() {
            var error;
            if (state.status === "closed") return;
            error = bridgeError("CLOSED");
            clearRequestTimer();
            detachAndClose();
            if (connectCallback) {
                invoke(connectCallback, error);
                connectCallback = null;
            }
            rejectActions(error);
            rejectResyncs(error);
            url = null;
            hello = null;
            contentVersionId = null;
            state.status = "closed";
        }

        function getState() {
            return {status: state.status, version: state.version, bag: copy(state.bag)};
        }

        return {connect: connect, useItem: useItem, reconnect: reconnect, resync: resync, close: close, getState: getState};
    }

    var api = {createBridge: createBridge};
    root.kbhtInventoryBridge = api;
    if (typeof module !== "undefined" && module.exports) module.exports = api;
}(typeof window !== "undefined" ? window : this));
