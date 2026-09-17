import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {createBridge} = require(fileURLToPath(new URL('../../client-recovered/patches/inventory-bridge.js', import.meta.url)));

let stdin = '';
for await (const chunk of process.stdin) stdin += chunk;
const {url, token, contentVersionId, bagIndex} = JSON.parse(stdin);
const actions = [
  '10000000-0000-4000-8000-000000000001',
  '10000000-0000-4000-8000-000000000002',
  '10000000-0000-4000-8000-000000000003',
  '10000000-0000-4000-8000-000000000004',
];
const staleAction = '10000000-0000-4000-8000-000000000005';
const hello = {
  protocolVersion: 1,
  capabilities: ['native-inventory-v1'],
  playerId: 10001,
  serverId: 1,
  contentVersionId,
};

let socketNumber = 0;
class InjectedWebSocket {
  constructor(target) {
    this.inner = new WebSocket(target);
    this.number = socketNumber++;
    this._binaryType = 'arraybuffer';
    this.inner.binaryType = 'arraybuffer';
    this.inner.addEventListener('open', event => this.onopen?.(event));
    this.inner.addEventListener('error', event => this.onerror?.(event));
    this.inner.addEventListener('close', event => this.onclose?.(event));
    this.inner.addEventListener('message', event => {
      const data = new Uint8Array(event.data);
      if (this.number === 0 && data[0] === 4) {
        this.inner.close();
        return;
      }
      this.onmessage?.({data: event.data});
    });
  }
  set binaryType(value) { this._binaryType = value; this.inner.binaryType = value; }
  get binaryType() { return this._binaryType; }
  send(value) { this.inner.send(value); }
  close() { this.inner.close(); }
}

const observations = {snapshots: [], deltas: [], rewards: [], errors: []};
function makeBridge(WebSocketImpl = InjectedWebSocket, sink = observations) {
  return createBridge({
    WebSocket: WebSocketImpl,
    setTimeout,
    clearTimeout,
    onSnapshot: value => sink.snapshots.push(value),
    onDelta: value => sink.deltas.push(value),
    onReward: value => sink.rewards.push(value),
    onError: error => sink.errors.push(error.code),
  });
}
function connect(bridge, options) {
  return new Promise((resolve, reject) => bridge.connect(options, (error, value) => error ? reject(error) : resolve(value)));
}
function reconnect(bridge, nextToken) {
  return new Promise((resolve, reject) => bridge.reconnect(nextToken, (error, value) => error ? reject(error) : resolve(value)));
}
function useItem(bridge, actionId) {
  return new Promise((resolve, reject) => bridge.useItem(actionId, bagIndex, 1, (error, value) => error ? reject(error) : resolve(value)));
}
function resync(bridge) {
  return new Promise((resolve, reject) => bridge.resync((error, value) => error ? reject(error) : resolve(value)));
}
async function waitFor(predicate, label) {
  const deadline = Date.now() + 5000;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error(`timeout waiting for ${label}`);
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}

async function rejectedConnection(nextToken, nextHello) {
  const sink = {snapshots: [], deltas: [], rewards: [], errors: []};
  const bridge = makeBridge(InjectedWebSocket, sink);
  let code = null;
  try {
    await connect(bridge, {url, token: nextToken, hello: nextHello});
  } catch (error) {
    code = error.code;
  }
  bridge.close();
  return {code, errors: sink.errors};
}

const bridge = makeBridge();
let secondary = null;
try {
  await connect(bridge, {url, token, hello});
  const lostResponse = useItem(bridge, actions[0]);
  await waitFor(() => bridge.getState().status === 'disconnected', 'lost-response disconnect');
  await reconnect(bridge, token);
  await lostResponse;

  await useItem(bridge, actions[1]);

  const secondarySink = {snapshots: [], deltas: [], rewards: [], errors: []};
  secondary = makeBridge(InjectedWebSocket, secondarySink);
  await connect(secondary, {url, token, hello});
  await useItem(secondary, actions[2]);
  secondary.close();
  secondary = null;

  const beforeResync = bridge.getState();
  let conflictCode = null;
  try {
    await useItem(bridge, staleAction);
  } catch (error) {
    conflictCode = error.code;
  }
  await waitFor(() => bridge.getState().version >= beforeResync.version + 1, 'automatic conflict resync');
  const afterResync = bridge.getState();
  await useItem(bridge, actions[3]);

  const invalid = await rejectedConnection('invalid-session', hello);
  const foreign = await rejectedConnection(token, {...hello, playerId: 10002});
  const result = {
    actions,
    staleAction,
    lostResponseReplayed: observations.rewards.length === 2,
    beforeResync,
    afterResync,
    conflictCode,
    finalState: bridge.getState(),
    snapshots: observations.snapshots,
    deltas: observations.deltas,
    rewards: observations.rewards,
    errors: observations.errors,
    invalid,
    foreign,
  };
  process.stdout.write(`${JSON.stringify(result)}\n`);
} finally {
  secondary?.close();
  bridge.close();
}
