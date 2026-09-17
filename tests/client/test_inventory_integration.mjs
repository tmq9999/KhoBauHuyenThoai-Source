import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const integration = require(fileURLToPath(new URL('../../client-recovered/patches/inventory-integration.js', import.meta.url)));
const realBridge = require(fileURLToPath(new URL('../../client-recovered/patches/inventory-bridge.js', import.meta.url)));

const ROUTE = 'logic.playerHandler.useItem';
const CONTENT = '11111111-1111-4111-8111-111111111111';
const ACTION = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

function packet(type, value, requestId) {
  const json = [...new TextEncoder().encode(JSON.stringify(value))];
  const body = requestId === undefined ? json : [4, requestId, ...json];
  return new Uint8Array([type, body.length >>> 16, body.length >>> 8 & 255, body.length & 255, ...body]);
}

// Minimal copied consumer branches only. Pinned project.js SHA256:
// 9776b6e20978d5d911bc0abb85830820bac5a3bfb8db4e65a617c5d18646a818.
// Bag.update: 5842-5847; player.update bag branch: 40126-40130;
// serverMain.sync: 51679-51711; socket request: 53992-54020;
// bag UI success callback: 5756-5762. No full recovered bundle execution.
function recoveredConsumers() {
  const ui = {dismissals: 0, hints: [], rewards: [], successes: 0, legacy: 0};
  const bag = {items: {'9': {kindId: 1, count: 1}}, update(e) {
    for (const t in e) if (e[t]) {
      this.items[t] = e[t];
      this.items[t].idx = t;
    } else delete this.items[t];
  }};
  const player = {id: 10001, serverId: 1, bag, update(e) {
    for (const s in e) if (this[s] !== undefined && s === 'bag') this.bag.update(e.bag.items);
  }};
  function sync(e) {
    ui.dismissals += 1;
    if (500 != e.code) player.update(e);
    else ui.hints.push(e.msg);
  }
  const queue = [];
  function legacyRequest(e, t, n) {
    // Transport boundary double; recovered _request's response order remains:
    // sync before success callback; code 500 never reaches success callback.
    ui.legacy += 1;
    const response = {code: 500, msg: 'LEGACY_FALLBACK'};
    sync(response);
    if (response.code != 500) n(response);
    queue.shift();
    if (queue.length > 0) {
      const next = queue[0];
      legacyRequest(next.route, next.msg, next.cb);
    }
  }
  function request(e, t, n) {
    if (integration.handleRequest(e, t, n)) return;
    // Copied queue behavior after the staged early-return hook; logs omitted.
    queue.push({route: e, msg: t, cb: n});
    if (1 == queue.length) legacyRequest(e, t, n);
  }
  function use(itemCount = 1) {
    request(ROUTE, {bagIndex: '7', itemCount}, e => {
      ui.successes += 1;
      if (e._temp.entityCountMap) ui.rewards.push(e._temp.entityCountMap);
    });
  }
  return {ui, player, sync, use};
}

function realHarness() {
  const c = recoveredConsumers(), sockets = [], timers = new Map();
  let timerId = 0;
  class WireSocket {
    constructor() { this.sent = []; sockets.push(this); }
    send(value) { this.sent.push(new Uint8Array(value)); }
    close() {}
    receive(value) { this.onmessage({data: value.buffer}); }
  }
  integration.attach({
    inventoryIdentity: 'postgres-v1', url: 'ws://127.0.0.1:21002/inventory', token: 'test-only',
    hello: {protocolVersion: 1, capabilities: ['native-inventory-v1'], playerId: 10001, serverId: 1, contentVersionId: CONTENT},
    getPlayer: () => c.player, sync: c.sync, showRewards: r => c.ui.rewards.push(r),
    nextActionId: () => ACTION, suspendLegacy() {}, bridgeModule: realBridge,
    deps: {WebSocket: WireSocket, setTimeout(fn) { timers.set(++timerId, fn); return timerId; }, clearTimeout(id) { timers.delete(id); }},
  });
  function ready() {
    const s = sockets.at(-1);
    s.onopen();
    s.receive(packet(1, {code: 200, sys: {heartbeat: 0, dict: {}, protos: {}}, user: {
      protocolVersion: 1, capability: 'native-inventory-v1', playerId: 10001, serverId: 1,
      contentVersionId: CONTENT, allowedRoutes: [ROUTE], fullPlayerSnapshot: false, snapshotMode: 'replace-bag',
      snapshot: {version: 0, contentVersionId: CONTENT, bag: {items: {'7': {kindId: 321, count: 2}}}},
    }}));
    c.ui.dismissals = 0;
    return s;
  }
  function timeout() { const [id, fn] = timers.entries().next().value; timers.delete(id); fn(); }
  return {...c, sockets, ready, timeout};
}

function fakeModule() {
  const calls = {connect: [], use: [], close: 0, reconnect: []};
  let handlers;
  const bridge = {
    connect(options, callback) { calls.connect.push(options); callback(null, {}); },
    useItem(id, bag, count, callback) { calls.use.push({id, bag, count, callback}); },
    reconnect(token, callback) { calls.reconnect.push(token); callback(null, {}); },
    close() { calls.close += 1; },
  };
  return {calls, bridge, module: {createBridge(options) { handlers = options; return bridge; }}, handlers: () => handlers};
}

function options(fake, overrides = {}) {
  const syncs = [], rewards = [], ids = ['aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'];
  return {
    value: {
      inventoryIdentity: 'postgres-v1',
      url: 'ws://127.0.0.1:21002/inventory', token: 'secret',
      hello: {playerId: 10001, serverId: 1}, getPlayer: () => ({id: 10001, serverId: 1, bag: {items: {'7': {kindId: 321, count: 2}, '9': {kindId: 1, count: 1}}}}),
      sync: value => syncs.push(value), showRewards: value => rewards.push(value),
      nextActionId: () => ids.shift(), bridgeModule: fake.module,
      suspendLegacy() {},
      deps: {WebSocket() {}, setTimeout() {}, clearTimeout() {}}, callback() {}, ...overrides,
    }, syncs, rewards,
  };
}

test('inactive handler preserves legacy request and attach validates provenance/scope', () => {
  assert.equal(integration.handleRequest('legacy.route', {}, () => {}), false);
  const fake = fakeModule();
  assert.throws(() => integration.attach(options(fake, {inventoryIdentity: 'legacy'}).value), /invalid/);
  assert.throws(() => integration.attach(options(fake, {getPlayer: () => ({id: 10002, serverId: 1})}).value), /scope/);
  assert.throws(() => integration.attach(options(fake, {getPlayer: () => ({id: 10001, serverId: 2})}).value), /scope/);
});

test('attached integration fences legacy writes, uses one UUID, and emits delta/reward/callback once', () => {
  const fake = fakeModule();
  const setup = options(fake);
  integration.attach(setup.value);
  assert.equal(integration.handleRequest('logic.gmHandler.addItem', {}, () => assert.fail()), true);
  assert.deepEqual(setup.syncs.pop(), {code: 500, msg: 'ONLINE_ROUTE_BLOCKED'});
  const callbacks = [];
  assert.equal(integration.handleRequest('logic.playerHandler.useItem', {bagIndex: '7', itemCount: 1}, value => callbacks.push(value)), true);
  assert.deepEqual(fake.calls.use[0], {id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', bag: '7', count: 1, callback: fake.calls.use[0].callback});
  fake.handlers().onDelta({bag: {items: {'7': null}}});
  fake.handlers().onReward({'49902': 6});
  fake.calls.use[0].callback(null, {});
  assert.deepEqual(setup.syncs.at(-1), {bag: {items: {'7': null}}});
  assert.deepEqual(setup.rewards, [{'49902': 6}]);
  assert.deepEqual(callbacks, [{_temp: {route: 'logic.playerHandler.useItem'}}]);
  integration.detach();
  assert.equal(integration.handleRequest('logic.playerHandler.useItem', {bagIndex: '7', itemCount: 1}, () => assert.fail()), true);
});

test('snapshot replacement tombstones old keys and reconnect/detach stay explicit', () => {
  const fake = fakeModule();
  const setup = options(fake);
  integration.attach(setup.value);
  fake.handlers().onSnapshot({bag: {items: {'8': {kindId: 49902, count: 6}}}});
  assert.deepEqual(setup.syncs.pop(), {bag: {items: {'7': null, '9': null, '8': {kindId: 49902, count: 6}}}});
  integration.reconnect('fresh', () => {});
  assert.deepEqual(fake.calls.reconnect, ['fresh']);
  fake.handlers().onError({code: 'TIMEOUT', message: 'contains secret'});
  assert.deepEqual(setup.syncs.pop(), {code: 500, msg: 'TIMEOUT'});
  integration.detach();
  assert.equal(fake.calls.close, 1);
});

test('old callbacks and changed player scope cannot mutate a later attachment', () => {
  const first = fakeModule();
  const firstSetup = options(first);
  integration.attach(firstSetup.value);
  const oldHandlers = first.handlers();
  integration.detach();
  const second = fakeModule();
  let player = {id: 10001, serverId: 1, bag: {items: {}}};
  const secondSetup = options(second, {getPlayer: () => player});
  integration.attach(secondSetup.value);
  oldHandlers.onDelta({bag: {items: {'7': null}}});
  oldHandlers.onReward({'49902': 6});
  oldHandlers.onError({code: 'TIMEOUT'});
  assert.deepEqual(secondSetup.syncs, []);
  assert.deepEqual(secondSetup.rewards, []);
  player = {id: 10002, serverId: 1, bag: {items: {}}};
  assert.equal(integration.handleRequest('logic.playerHandler.useItem', {bagIndex: '7', itemCount: 1}, () => assert.fail()), true);
  assert.deepEqual(secondSetup.syncs, [{code: 500, msg: 'INVENTORY_SCOPE_CHANGED'}]);
  assert.equal(second.calls.use.length, 0);
  integration.detach();
});

test('reconnect requires live scope and late completion cannot cross detach generation', () => {
  const fake = fakeModule();
  let player = {id: 10001, serverId: 1, bag: {items: {}}};
  const setup = options(fake, {getPlayer: () => player});
  integration.attach(setup.value);
  let callbackCount = 0;
  integration.handleRequest('logic.playerHandler.useItem', {bagIndex: '7', itemCount: 1}, () => { callbackCount += 1; });
  const late = fake.calls.use[0].callback;
  player = {id: 10002, serverId: 1, bag: {items: {}}};
  assert.throws(() => integration.reconnect('fresh', () => {}), /scope/);
  integration.detach();
  assert.deepEqual(setup.syncs.at(-1), {code: 500, msg: 'INVENTORY_DETACHED'});
  late(null, {});
  assert.equal(callbackCount, 0);
  assert.equal(fake.calls.reconnect.length, 0);
});

test('attach accepts only literal loopback inventory endpoint with an explicit valid port', () => {
  for (const url of [
    'ws://localhost:21002/inventory', 'ws://127.0.0.1/inventory',
    'ws://127.0.0.1:0/inventory', 'ws://127.0.0.1:65536/inventory',
    'wss://127.0.0.1:21002/inventory',
  ]) {
    const fake = fakeModule();
    assert.throws(() => integration.attach(options(fake, {url}).value), /invalid/);
    integration.detach();
  }
});

test('real bridge validation/domain errors dismiss native loading and show a hint exactly once without success', () => {
  for (const kind of ['validation', 'domain', 'fatal']) {
    const h = realHarness();
    try {
      const s = h.ready();
      h.use(kind === 'validation' ? 0 : 1);
      if (kind === 'domain') s.receive(packet(4, {code: 500, error: {code: 'INSUFFICIENT_ITEMS'}}, 1));
      if (kind === 'fatal') s.receive(packet(4, {code: 200}, 1));
      assert.equal(h.ui.dismissals, 1, kind);
      assert.deepEqual(h.ui.hints, [kind === 'validation' ? 'VALIDATION_ERROR' : kind === 'domain' ? 'INSUFFICIENT_ITEMS' : 'MISMATCH_REPLY']);
      assert.equal(h.ui.successes, 0);
      assert.equal(h.ui.legacy, 0);
      assert.deepEqual(h.ui.rewards, []);
    } finally { integration.detach(); }
  }
});

test('real bridge snapshot/delta feed copied bag consumers and replay opens only one reward popup', () => {
  const h = realHarness();
  try {
    const s = h.ready();
    assert.deepEqual(h.player.bag.items, {'7': {kindId: 321, count: 2, idx: '7'}});
    h.use();
    const reply = packet(4, {code: 200, commandId: ACTION, version: 1, contentVersionId: CONTENT,
      result: {bag: {items: {'7': null, '8': {kindId: 49902, count: 6}}}, _temp: {route: ROUTE, entityCountMap: {'49902': 6}}},
      eventIds: ['22222222-2222-4222-8222-222222222222']}, 1);
    s.receive(reply);
    s.receive(reply);
    assert.deepEqual(h.player.bag.items, {'8': {kindId: 49902, count: 6, idx: '8'}});
    assert.equal(h.ui.dismissals, 1);
    assert.equal(h.ui.successes, 1);
    assert.deepEqual(h.ui.rewards, [{'49902': 6}]);
    assert.deepEqual(h.ui.hints, []);
  } finally { integration.detach(); }
});

test('real bridge connection, timeout and detach errors remain visible and generation-fenced', () => {
  for (const kind of ['handshake-timeout', 'close', 'request-timeout', 'detach']) {
    const h = realHarness();
    try {
      const s = kind === 'handshake-timeout' ? h.sockets[0] : h.ready();
      if (kind !== 'handshake-timeout') h.use();
      const lateMessage = s.onmessage;
      if (kind === 'close') s.onclose();
      else if (kind === 'detach') integration.detach();
      else h.timeout();
      assert.equal(h.ui.dismissals, 1, kind);
      assert.deepEqual(h.ui.hints, [kind === 'close' ? 'CONNECTION_CLOSED' : kind === 'detach' ? 'INVENTORY_DETACHED' : 'TIMEOUT']);
      assert.equal(h.ui.successes, 0);
      if (kind === 'detach') {
        lateMessage({data: packet(4, {code: 500, error: {code: 'LATE_ERROR'}}, 1).buffer});
        assert.equal(h.ui.dismissals, 1);
      }
    } finally { integration.detach(); }
  }
});
