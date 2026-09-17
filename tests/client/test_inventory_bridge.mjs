import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const bridgePath = new URL('../../client-recovered/patches/inventory-bridge.js', import.meta.url);
const {createBridge} = require(fileURLToPath(bridgePath));

const ROUTE = 'logic.playerHandler.useItem';
const RESYNC = 'connector.inventoryHandler.resync';
const CONTENT = '11111111-1111-4111-8111-111111111111';
const ACTION_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const ACTION_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

function bytes(value) {
  if (value instanceof Uint8Array) return value;
  return new Uint8Array(value.buffer || value, value.byteOffset || 0, value.byteLength);
}

function utf8(value) {
  return new TextEncoder().encode(value);
}

function text(value) {
  return new TextDecoder('utf-8', {fatal: true}).decode(value);
}

function packageFrame(type, body = new Uint8Array()) {
  body = bytes(body);
  const result = new Uint8Array(4 + body.length);
  result[0] = type;
  result[1] = body.length >>> 16;
  result[2] = body.length >>> 8;
  result[3] = body.length;
  result.set(body, 4);
  return result;
}

function varint(value) {
  const result = [];
  do {
    let part = value & 0x7f;
    value = Math.floor(value / 128);
    if (value) part |= 0x80;
    result.push(part);
  } while (value);
  return result;
}

function responseFrame(requestId, payload) {
  return packageFrame(4, new Uint8Array([4, ...varint(requestId), ...utf8(JSON.stringify(payload))]));
}

function decodePackage(value) {
  const valueBytes = bytes(value);
  assert.ok(valueBytes.length >= 4);
  const length = valueBytes[1] * 65536 + valueBytes[2] * 256 + valueBytes[3];
  assert.equal(valueBytes.length, length + 4);
  return {type: valueBytes[0], body: valueBytes.slice(4)};
}

function readVarint(value, start) {
  let result = 0;
  let multiplier = 1;
  let offset = start;
  for (;;) {
    const part = value[offset++];
    result += (part & 0x7f) * multiplier;
    if (!(part & 0x80)) return [result, offset];
    multiplier *= 128;
  }
}

function decodeRequest(value) {
  const packet = decodePackage(value);
  assert.equal(packet.type, 4);
  assert.equal(packet.body[0], 0);
  let [requestId, offset] = readVarint(packet.body, 1);
  const routeLength = packet.body[offset++];
  const route = text(packet.body.slice(offset, offset + routeLength));
  offset += routeLength;
  const payloadText = text(packet.body.slice(offset));
  return {requestId, route, payloadText, payload: JSON.parse(payloadText)};
}

function handshakeFrame(version, items = {'7': {kindId: 321, count: 2}}) {
  return packageFrame(1, utf8(JSON.stringify({
    code: 200,
    sys: {heartbeat: 0, dict: {}, protos: {}},
    user: {
      protocolVersion: 1,
      capability: 'native-inventory-v1',
      playerId: 10001,
      serverId: 1,
      contentVersionId: CONTENT,
      allowedRoutes: [ROUTE],
      fullPlayerSnapshot: false,
      snapshotMode: 'replace-bag',
      snapshot: {version, contentVersionId: CONTENT, bag: {items}},
    },
  })));
}

function snapshotResult(version, items) {
  return {
    code: 200,
    result: {
      snapshotMode: 'replace-bag',
      fullPlayerSnapshot: false,
      snapshot: {version, contentVersionId: CONTENT, bag: {items}},
    },
  };
}

function mutationResult(actionId, version, items, rewards = {}) {
  return {
    code: 200,
    commandId: actionId,
    version,
    contentVersionId: CONTENT,
    result: {bag: {items}, _temp: {route: ROUTE, entityCountMap: rewards}},
    eventIds: ['22222222-2222-4222-8222-222222222222'],
  };
}

function harness() {
  const sockets = [];
  const timers = new Map();
  let timerId = 0;
  function FakeWebSocket(url) {
    this.url = url;
    this.readyState = 0;
    this.binaryType = '';
    this.sent = [];
    sockets.push(this);
  }
  FakeWebSocket.prototype.send = function (value) { this.sent.push(bytes(value).slice()); };
  FakeWebSocket.prototype.close = function () { this.readyState = 2; };
  FakeWebSocket.prototype.open = function () {
    this.readyState = 1;
    this.onopen({});
  };
  FakeWebSocket.prototype.message = function (value) {
    const copy = bytes(value).slice();
    this.onmessage({data: copy.buffer});
  };
  FakeWebSocket.prototype.drop = function () {
    this.readyState = 3;
    this.onclose({code: 1006});
  };
  return {
    sockets,
    timers,
    WebSocket: FakeWebSocket,
    setTimeout(fn) {
      timerId += 1;
      timers.set(timerId, fn);
      return timerId;
    },
    clearTimeout(id) { timers.delete(id); },
    fireTimer() {
      const entry = timers.entries().next();
      assert.equal(entry.done, false, 'expected an armed timer');
      timers.delete(entry.value[0]);
      entry.value[1]();
    },
  };
}

function hello() {
  return {
    protocolVersion: 1,
    capabilities: ['native-inventory-v1'],
    playerId: 10001,
    serverId: 1,
    contentVersionId: CONTENT,
  };
}

function ready(h, bridge, {token = 'secret-token', version = 5, items, reconnect = false} = {}) {
  const calls = [];
  const done = (error, value) => calls.push([error, value]);
  if (reconnect) bridge.reconnect(token, done);
  else bridge.connect({url: 'ws://127.0.0.1:21002/inventory', token, hello: hello()}, done);
  const socket = h.sockets.at(-1);
  socket.open();
  const handshake = decodePackage(socket.sent[0]);
  assert.equal(handshake.type, 1);
  const body = JSON.parse(text(handshake.body));
  assert.equal(body.user.token, token);
  socket.message(handshakeFrame(version, items));
  assert.equal(decodePackage(socket.sent[1]).type, 2);
  assert.equal(decodePackage(socket.sent[1]).body.length, 0);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], null);
  return {socket, handshake: body, calls};
}

test('handshake carries the token only in its body and installs a copied replacement snapshot', () => {
  const h = harness();
  const snapshots = [];
  const bridge = createBridge({...h, onSnapshot: value => snapshots.push(value)});
  const connected = ready(h, bridge, {token: 'do-not-expose'});

  assert.equal(connected.socket.url, 'ws://127.0.0.1:21002/inventory');
  assert.deepEqual(connected.handshake, {
    sys: {type: 'kbht-inventory', version: '1'},
    user: {token: 'do-not-expose', hello: hello()},
  });
  assert.equal(JSON.stringify(connected.socket.sent.slice(1)).includes('do-not-expose'), false);
  assert.deepEqual(bridge.getState(), {
    status: 'ready', version: 5, bag: {items: {'7': {kindId: 321, count: 2}}},
  });
  const exposed = bridge.getState();
  exposed.bag.items['7'].count = 999;
  snapshots[0].bag.items['7'].count = 998;
  assert.equal(bridge.getState().bag.items['7'].count, 2);
  assert.equal(JSON.stringify(bridge.getState()).includes('do-not-expose'), false);
});

test('content identifiers accept canonical UUIDs that do not encode an RFC version nibble', () => {
  const h = harness();
  const bridge = createBridge({...h});
  const versionZeroHello = {...hello(), contentVersionId: '00000000-0000-0000-0000-000000000010'};
  let callbackError;
  bridge.connect({url: 'ws://127.0.0.1:21002/inventory', token: 'token', hello: versionZeroHello}, error => { callbackError = error; });
  assert.equal(callbackError, undefined);
  assert.equal(h.sockets.length, 1);
  bridge.close();
});

test('one mutation is inflight and later queued envelopes take the latest synchronized version', () => {
  const h = harness();
  const deltas = [];
  const rewards = [];
  const bridge = createBridge({...h, onDelta: value => deltas.push(value), onReward: value => rewards.push(value)});
  const {socket} = ready(h, bridge);
  const callbacks = [];
  bridge.useItem(ACTION_A, '7', 1, (error, value) => callbacks.push([error, value]));
  const first = decodeRequest(socket.sent[2]);
  assert.equal(first.route, ROUTE);
  assert.deepEqual(first.payload, {
    command_id: ACTION_A,
    player_id: 10001,
    server_id: 1,
    route: ROUTE,
    expected_version: 5,
    content_version_id: CONTENT,
    payload: {bagIndex: '7', itemCount: 1},
  });
  bridge.useItem(ACTION_B, '8', 2, (error, value) => callbacks.push([error, value]));
  assert.equal(socket.sent.length, 3, 'second mutation must remain queued');

  socket.message(responseFrame(first.requestId, mutationResult(ACTION_A, 6, {'7': {kindId: 321, count: 1}}, {'49902': 6})));
  assert.equal(callbacks.length, 1);
  assert.equal(callbacks[0][0], null);
  assert.deepEqual(deltas, [{version: 6, contentVersionId: CONTENT, bag: {items: {'7': {kindId: 321, count: 1}}}}]);
  assert.deepEqual(rewards, [{'49902': 6}]);
  const second = decodeRequest(socket.sent[3]);
  assert.equal(second.payload.expected_version, 6);
  assert.equal(second.payload.command_id, ACTION_B);
  assert.deepEqual(second.payload.payload, {bagIndex: '8', itemCount: 2});

  socket.message(responseFrame(second.requestId, mutationResult(ACTION_B, 7, {'8': null})));
  assert.equal(callbacks.length, 2);
  socket.message(responseFrame(first.requestId, mutationResult(ACTION_A, 6, {'7': {kindId: 321, count: 1}}, {'49902': 6})));
  assert.equal(callbacks.length, 2, 'late replay must not complete twice');
  assert.equal(rewards.length, 1, 'late replay must not show reward twice');
  assert.deepEqual(bridge.getState(), {
    status: 'ready', version: 7, bag: {items: {'7': {kindId: 321, count: 1}}},
  });
});

test('unexpected close retains and reconnect resends the exact first-send envelope', () => {
  const h = harness();
  const deltas = [];
  const rewards = [];
  const errors = [];
  const bridge = createBridge({...h, onDelta: value => deltas.push(value), onReward: value => rewards.push(value), onError: error => errors.push(error.code)});
  const {socket} = ready(h, bridge, {version: 10});
  const callbacks = [];
  bridge.useItem(ACTION_A, '7', 2, (error, value) => callbacks.push([error, value]));
  const original = decodeRequest(socket.sent[2]);
  socket.drop();
  assert.equal(h.sockets.length, 1, 'bridge must not silently auto-reconnect');
  assert.equal(callbacks.length, 0);
  assert.equal(bridge.getState().status, 'disconnected');
  assert.deepEqual(errors, ['CONNECTION_CLOSED']);

  const next = ready(h, bridge, {token: 'fresh-token', version: 12, items: {'9': {kindId: 49902, count: 12}}, reconnect: true});
  const replay = decodeRequest(next.socket.sent[2]);
  assert.notEqual(replay.requestId, original.requestId);
  assert.equal(replay.payloadText, original.payloadText);
  next.socket.message(responseFrame(replay.requestId, mutationResult(ACTION_A, 11, {'7': null}, {'49902': 12})));
  assert.equal(callbacks.length, 1);
  assert.equal(callbacks[0][0], null);
  assert.deepEqual(deltas, []);
  assert.deepEqual(rewards, []);
  assert.deepEqual(bridge.getState().bag.items, {'9': {kindId: 49902, count: 12}});
  assert.equal(bridge.getState().version, 12);
});

test('a mutation response gap requests replacement before the queued action and shows reward once', () => {
  const h = harness();
  const snapshots = [];
  const deltas = [];
  const rewards = [];
  const bridge = createBridge({...h, onSnapshot: value => snapshots.push(value), onDelta: value => deltas.push(value), onReward: value => rewards.push(value)});
  const {socket} = ready(h, bridge, {version: 1, items: {'7': {kindId: 321, count: 2}, '99': {kindId: 49902, count: 1}}});
  const calls = [];
  bridge.useItem(ACTION_A, '7', 1, (error, value) => calls.push([error, value]));
  bridge.useItem(ACTION_B, '8', 1, (error, value) => calls.push([error, value]));
  const mutation = decodeRequest(socket.sent[2]);
  socket.message(responseFrame(mutation.requestId, mutationResult(ACTION_A, 3, {'7': null}, {'49902': 6})));
  assert.deepEqual(deltas, []);
  const resync = decodeRequest(socket.sent[3]);
  assert.equal(resync.route, RESYNC);
  socket.message(responseFrame(resync.requestId, snapshotResult(3, {'10': {kindId: 49902, count: 6}})));
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], null);
  assert.deepEqual(bridge.getState().bag.items, {'10': {kindId: 49902, count: 6}});
  assert.deepEqual(rewards, [{'49902': 6}]);
  assert.equal(snapshots.length, 2);
  const second = decodeRequest(socket.sent[4]);
  assert.equal(second.payload.command_id, ACTION_B);
  assert.equal(second.payload.expected_version, 3);
});

test('handshake timeout, duplicate action IDs, resync bound, and stale reconnect fail safely', () => {
  const timeoutHarness = harness();
  const timeoutErrors = [];
  const timeoutBridge = createBridge({...timeoutHarness, onError: error => timeoutErrors.push(error.code)});
  const connectionErrors = [];
  timeoutBridge.connect({url: 'ws://127.0.0.1:21002/inventory', token: 'ephemeral', hello: hello()}, error => connectionErrors.push(error));
  timeoutHarness.sockets[0].open();
  timeoutHarness.fireTimer();
  assert.equal(timeoutBridge.getState().status, 'disconnected');
  assert.deepEqual(connectionErrors.map(error => error.code), ['TIMEOUT']);
  assert.deepEqual(timeoutErrors, ['TIMEOUT']);

  const h = harness();
  const bridge = createBridge({...h});
  const {socket} = ready(h, bridge, {version: 5});
  const duplicateErrors = [];
  bridge.useItem(ACTION_A, '7', 1, error => duplicateErrors.push(error));
  bridge.useItem(ACTION_A, '7', 1, error => duplicateErrors.push(error));
  assert.equal(duplicateErrors[0].code, 'DUPLICATE_ACTION');
  const mutation = decodeRequest(socket.sent[2]);
  socket.message(responseFrame(mutation.requestId, mutationResult(ACTION_A, 6, {'7': {kindId: 321, count: 1}})));
  bridge.useItem(ACTION_A, '7', 1, error => duplicateErrors.push(error));
  assert.equal(duplicateErrors.at(-1).code, 'DUPLICATE_ACTION');

  const resyncErrors = [];
  for (let index = 0; index < 17; index += 1) bridge.resync(error => { if (error) resyncErrors.push(error); });
  assert.equal(resyncErrors.length, 1);
  assert.equal(resyncErrors[0].code, 'QUEUE_FULL');
  socket.drop();
  const reconnectCalls = [];
  bridge.reconnect('fresh', error => reconnectCalls.push(error));
  const next = h.sockets.at(-1);
  next.open();
  next.message(handshakeFrame(4));
  assert.equal(reconnectCalls[0].code, 'STALE_SNAPSHOT');
  assert.equal(bridge.getState().version, 6);
});

test('public resync replaces the bag and rejects stale snapshots', () => {
  const h = harness();
  const errors = [];
  const bridge = createBridge({...h, onError: error => errors.push(error.code)});
  const {socket} = ready(h, bridge, {version: 4, items: {'7': {kindId: 321, count: 2}}});
  const calls = [];
  bridge.resync((error, value) => calls.push([error, value]));
  const request = decodeRequest(socket.sent[2]);
  assert.equal(request.route, RESYNC);
  socket.message(responseFrame(request.requestId, snapshotResult(5, {'8': {kindId: 49902, count: 6}})));
  assert.equal(calls[0][0], null);
  assert.deepEqual(bridge.getState().bag.items, {'8': {kindId: 49902, count: 6}});

  bridge.resync((error, value) => calls.push([error, value]));
  const stale = decodeRequest(socket.sent[3]);
  socket.message(responseFrame(stale.requestId, snapshotResult(4, {'7': {kindId: 321, count: 99}})));
  assert.equal(calls[1][0].code, 'STALE_SNAPSHOT');
  assert.deepEqual(bridge.getState().bag.items, {'8': {kindId: 49902, count: 6}});
  assert.deepEqual(errors, ['STALE_SNAPSHOT']);
});

test('conflict rejects the stale action, resyncs, then sends a later action at the replacement version', () => {
  const h = harness();
  const bridge = createBridge({...h});
  const {socket} = ready(h, bridge, {version: 5});
  const calls = [];
  bridge.useItem(ACTION_A, '7', 1, error => calls.push(error));
  bridge.useItem(ACTION_B, '8', 1, error => calls.push(error));
  const stale = decodeRequest(socket.sent[2]);
  socket.message(responseFrame(stale.requestId, {code: 500, error: {code: 'CONFLICT'}}));
  assert.equal(calls[0].code, 'CONFLICT');
  const refresh = decodeRequest(socket.sent[3]);
  assert.equal(refresh.route, RESYNC);
  socket.message(responseFrame(refresh.requestId, snapshotResult(6, {'8': {kindId: 321, count: 1}})));
  const later = decodeRequest(socket.sent[4]);
  assert.equal(later.payload.command_id, ACTION_B);
  assert.equal(later.payload.expected_version, 6);
});

test('queue/input bounds and protocol mismatches reject without exposing credentials', () => {
  const h = harness();
  const seenErrors = [];
  const bridge = createBridge({...h, onError: error => seenErrors.push(error)});
  const {socket} = ready(h, bridge, {token: 'credential-never-report'});
  const bad = [];
  bridge.useItem('not-a-uuid', '7', 1, error => bad.push(error));
  bridge.useItem(ACTION_A, '01', 1, error => bad.push(error));
  bridge.useItem(ACTION_A, '7', 0, error => bad.push(error));
  assert.deepEqual(bad.map(error => error.code), ['VALIDATION_ERROR', 'VALIDATION_ERROR', 'VALIDATION_ERROR']);
  assert.equal(socket.sent.length, 2);

  const queued = [];
  for (let index = 0; index < 17; index += 1) {
    const action = `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
    bridge.useItem(action, String(index + 1), 1, error => queued.push(error));
  }
  assert.equal(queued.length, 1);
  assert.equal(queued[0].code, 'QUEUE_FULL');
  const inflight = decodeRequest(socket.sent[2]);
  socket.message(responseFrame(inflight.requestId + 100, mutationResult(inflight.payload.command_id, 6, {})));
  assert.equal(bridge.getState().status, 'error');
  assert.equal(seenErrors.at(-1).code, 'UNKNOWN_REPLY');
  assert.equal(JSON.stringify(seenErrors).includes('credential-never-report'), false);
});

test('request timeout keeps the same action for explicit reconnect while close rejects and clears it', () => {
  const h = harness();
  const errors = [];
  const bridge = createBridge({...h, onError: error => errors.push(error.code)});
  const {socket} = ready(h, bridge, {version: 20});
  const callbacks = [];
  bridge.useItem(ACTION_A, '7', 1, error => callbacks.push(error));
  const original = decodeRequest(socket.sent[2]);
  h.fireTimer();
  assert.equal(bridge.getState().status, 'disconnected');
  assert.deepEqual(errors, ['TIMEOUT']);
  assert.equal(callbacks.length, 0);

  const next = ready(h, bridge, {token: 'rotated-token', version: 20, reconnect: true});
  const replay = decodeRequest(next.socket.sent[2]);
  assert.equal(replay.payloadText, original.payloadText);
  bridge.close();
  assert.equal(callbacks.length, 1);
  assert.equal(callbacks[0].code, 'CLOSED');
  assert.equal(bridge.getState().status, 'closed');
  assert.equal(h.timers.size, 0);
  let reconnectError;
  bridge.reconnect('another-token', error => { reconnectError = error; });
  assert.equal(reconnectError.code, 'CLOSED');
});

test('expired authentication fails pending callbacks and oversized input fails safely', () => {
  const h = harness();
  const errors = [];
  const bridge = createBridge({...h, onError: error => errors.push(error.code)});
  const {socket} = ready(h, bridge);
  const calls = [];
  bridge.useItem(ACTION_A, '7', 1, error => calls.push(error));
  bridge.useItem(ACTION_B, '8', 1, error => calls.push(error));
  const request = decodeRequest(socket.sent[2]);
  socket.message(responseFrame(request.requestId, {code: 500, error: {code: 'UNAUTHENTICATED'}}));
  assert.deepEqual(calls.map(error => error.code), ['UNAUTHENTICATED', 'UNAUTHENTICATED']);
  assert.equal(bridge.getState().status, 'error');
  assert.equal(errors.at(-1), 'UNAUTHENTICATED');

  const secondHarness = harness();
  const secondErrors = [];
  const second = createBridge({...secondHarness, onError: error => secondErrors.push(error.code)});
  const connection = ready(secondHarness, second);
  connection.socket.message(new Uint8Array(1048577));
  assert.equal(second.getState().status, 'error');
  assert.deepEqual(secondErrors, ['FRAME_TOO_LARGE']);
});
