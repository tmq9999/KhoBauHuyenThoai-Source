'use strict';
// Host IO exists only here, outside the evaluated pinned modules. No host
// function/object is injected into their VM; only JSON strings cross the seam.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ARTIFACT_HASH = '73a690818bc83f3857c7032cae8340f723963691efc2baa3194a7be788486168';
try {
  const raw = fs.readFileSync(process.argv[2]);
  if (raw.length > 600000 || crypto.createHash('sha256').update(raw).digest('hex') !== ARTIFACT_HASH)
    throw new Error('artifact');
  const artifact = JSON.parse(raw);
  const input = fs.readFileSync(0, 'utf8');
  if (Buffer.byteLength(input) > 2000000) throw new Error('input limit');
  const definitions = Object.entries(artifact.modules).map(([name, item]) =>
    `${JSON.stringify(name)}: function(e,t,n){\n${item.body}\n}`).join(',\n');
  const context = vm.createContext(Object.create(null), {
    codeGeneration: {strings: false, wasm: false}, microtaskMode: 'afterEvaluate'
  });
  const script = new vm.Script(`
'use strict';
const input = JSON.parse(${JSON.stringify(input)});
function deny() { throw new Error('capability denied'); }
Math.random = deny;
Date = class { constructor() { deny(); } static now() { deny(); } };
const console = {log: deny, warn: deny, error: deny};
const cc = {_RF: {push() {}, pop() {}}};
function validate(value, depth=0) {
  if (depth>32) throw new Error('depth');
  if (typeof value==='number' && !Number.isFinite(value)) throw new Error('number');
  if (value && typeof value==='object') {
    for (const key of Object.keys(value)) {
      if (['__proto__','constructor','prototype'].includes(key)) throw new Error('key');
      validate(value[key],depth+1);
    }
  }
}
validate(input);
function integer(value,min,max) {
  if (!Number.isSafeInteger(value)||value<min||value>max) throw new Error('integer');
}
if (input.format!=='kbht-battle-input-v1') throw new Error('format');
integer(input.seed,1,0xffffffff); integer(input.smapId,1,1000000000);
if (!Array.isArray(input.actions)||input.actions.length>256) throw new Error('manual limit');
let previousAction=null;
const actionKeys=new Set();
for(const action of input.actions) {
  if(Object.keys(action).sort().join(',')!=='skillId,tick,zone') throw new Error('action keys');
  integer(action.zone,1,10); integer(action.tick,1,1802); integer(action.skillId,1,1000000000);
  if(previousAction && (action.zone<previousAction.zone ||
     (action.zone===previousAction.zone && action.tick<previousAction.tick)))
    throw new Error('action order');
  const actionKey=action.zone+':'+action.tick+':'+action.skillId;
  if(actionKeys.has(actionKey)) throw new Error('duplicate action');
  actionKeys.add(actionKey);
  previousAction=action;
}
integer(input.team.playerId,1,Number.MAX_SAFE_INTEGER);
if (!Array.isArray(input.team.roles)||input.team.roles.length<1||input.team.roles.length>5
    ||!Array.isArray(input.team.ships)||input.team.ships.length) throw new Error('team');
const indices = new Set(), kinds = new Set();
for (const role of input.team.roles) {
  integer(role.idx,1,5); integer(role.kindId,1,1000000000);
  if(indices.has(role.idx)||kinds.has(role.kindId)) throw new Error('duplicate role');
  indices.add(role.idx); kinds.add(role.kindId);
  integer(role.level,1,1000); integer(role.star,1,10); integer(role.awakeLevel,0,100);
  for (const attr of ['hp','maxHp','mp','atk','def','mdef','hit','dodge','crit']) {
    if(typeof role[attr]!=='number'||role[attr]<0||role[attr]>1e12) throw new Error('attribute');
  }
  if(role.hp<=0||role.maxHp<=0||role.hp>role.maxHp||role.mp>1000) throw new Error('health');
  for(const attr of ['unDizzinessRate','critRate','dmg2HpRate','dodgeRate','atkSpeedRate',
    'keepMp','reboundDmgHp','skillDmg2HpRate','unConfusedRate','hitReduceMpRate',
    'hitRepeledRate','hitReduceAtkSpeedRate','hitRateSilence','missReboundTeamRate',
    'missReboundRate','unDizziness1Rate']) {
    if(Object.hasOwn(role,attr) && (typeof role[attr]!=='number'||Math.abs(role[attr])>1e12))
      throw new Error('optional attribute');
  }
  if(!Array.isArray(role.skills)||!Array.isArray(role.awakeSkills)||role.skills.length>20||role.awakeSkills.length>20)
    throw new Error('skills');
  const skills = new Set();
  for(const skill of role.skills.concat(role.awakeSkills)) {
    integer(skill.kindId,1,1000000000); integer(skill.level,0,1000);
    if(skills.has(skill.kindId)) throw new Error('duplicate skill');
    skills.add(skill.kindId);
  }
}
const modules = {${definitions}}, cache = Object.create(null);
const tables = input.tables, dataApi = Object.create(null);
for (const name of ['smap','bmap','mob','role','entity','fightSkill','buff','math']) {
  if (!tables[name]||Array.isArray(tables[name])) throw new Error('table');
  dataApi[name] = {findById(id) {
    // Undefined first skill of the source ship placeholder is an optional read.
    if (id===undefined) return null;
    if(!Object.hasOwn(tables[name],id)) throw new Error('missing content '+name+':'+id);
    const row = tables[name][id];
    if(row.kindId!==Number(id)) throw new Error('content id');
    return row;
  }};
}
dataApi.math.findBy=function(field,value) {
  if(field!=='level') throw new Error('math lookup');
  const rows=Object.values(tables.math).filter(row=>row.level===value);
  if(rows.length!==1) throw new Error('missing math level');
  return rows;
};
dataApi.findEntityById = function(id) {
  const entity = dataApi.entity.findById(id);
  if(entity.type!=='role') throw new Error('entity type');
  return Object.assign({},entity,dataApi.role.findById(id));
};
const stage = dataApi.smap.findById(input.smapId);
integer(stage.mobZoneCount,1,10);
stage.bmap = dataApi.bmap.findById(stage.bmapId);
for(let zone=1;zone<=stage.mobZoneCount;zone++) {
  if(!Array.isArray(stage['mobZone'+zone])||stage['mobZone'+zone].length<1||stage['mobZone'+zone].length>5)
    throw new Error('mob zone');
}
let events=[], eventBytes=0, over=[];
const sink = {emit(route,event) {
  const encoded=JSON.stringify(event);
  eventBytes+=encoded.length;
  if(events.length>=50000||eventBytes>3000000) throw new Error('event limit');
  events.push(encoded);
  if(route==='onOver') over.push(JSON.parse(encoded));
}};
const adapters = {dataApi,'battle.msgHandler':sink,
  serverConfig:new Proxy({}, {get:deny})}; // Only TAIL boss-money path reads it.
function requireModule(name) {
  if(Object.hasOwn(adapters,name)) return adapters[name];
  if(Object.hasOwn(cache,name)) return cache[name].exports;
  if(!Object.hasOwn(modules,name)) throw new Error('module denied');
  const module={exports:{}}; cache[name]=module;
  modules[name](requireModule,module,module.exports);
  return module.exports;
}
// Pinned fightHandler schedules just the area start at zero. Wall-clock timer
// capabilities remain absent; all combat uses the recovered scheduler/timer.
let pendingStart=null;
function _setTimeout(callback,delay) {
  if(delay!==0||pendingStart||typeof callback!=='function') throw new Error('timer denied');
  pendingStart=callback; return 1;
}
const _setInterval=deny, _clearInterval=deny;
const main=requireModule('battleMain'), handler=requireModule('battle.fightHandler');
const Timer=requireModule('battle.timer');
// Adapter around run's original instant while-loop permits explicit bounded
// ticks; start still activates every original target and passive unchanged.
Timer.prototype.run=function() { if(!this.area.isOver) this.interval=true; };
main.battleType=requireModule('battle.consts').BATTLE_TYPE.SMAP;
main.rolesCount=input.team.roles.length;
main.isAuto=false; main.isInstant=false; main.isShow=false;
main.manualSkillIds=input.team.roles.flatMap(role=>{
  const id=dataApi.findEntityById(role.kindId).skillIds[0];
  return role.skills.some(skill=>skill.kindId===id)?[id]:[];
});
main.setSeed(input.seed);
// Source selectBattleRolesScene48796 orders by positionPriority, stable ties.
input.team.roles.sort((a,b)=>dataApi.findEntityById(a.kindId).positionPriority-dataApi.findEntityById(b.kindId).positionPriority);
handler.smapBattle(input.team,input.smapId,null);
const zones=[]; let ticks=0;
let actionCursor=0;
const acceptedActions=[];
for(let zone=1;zone<=stage.mobZoneCount;zone++) {
  if(!pendingStart) throw new Error('missing area start');
  const start=pendingStart; pendingStart=null; start();
  const area=handler.area; let zoneTicks=0;
  while(!area.isOver) {
    if(++zoneTicks>1802||++ticks>18000) throw new Error('tick limit');
    area.timer.tick(50);
    // Native UI queues a skill, and original timer10989 invokes useSkill only
    // after completing that tick. Reproduce the same boundary, not immediate
    // damage or a rewritten cooldown formula. Range/status resolution stays in
    // the original action engine after selection.
    while(actionCursor<input.actions.length && input.actions[actionCursor].zone===zone &&
          input.actions[actionCursor].tick===zoneTicks) {
      const action=input.actions[actionCursor++];
      if(area.isOver || !main.manualSkillIds.includes(action.skillId)) throw new Error('illegal action');
      const actor=area.getEntityBySkillId(action.skillId);
      if(!actor || actor.teamId!==1 || actor.isSummon || actor.died || actor.hp<=0 ||
         actor.mp<actor.maxMp || !actor.fightSkills[action.skillId] ||
         actor.fightSkills[action.skillId].coolDownTime>0) throw new Error('action not ready');
      if(requireModule('battle.consts').FIGHT_SKILL.USE_ONE_TIMES_IDS.includes(action.skillId)&&actor.usedSkillIdMap[action.skillId])
        throw new Error('one-use action');
      handler.useSkill(action.skillId);
      acceptedActions.push(action);
    }
    for(const entity of Object.values(area.entities)) {
      for(const key of ['x','y']) if(!Number.isFinite(entity[key])) throw new Error('nonfinite position');
      if(entity.type!=='missile') for(const key of ['hp','atk','def','mdef'])
        if(!Number.isFinite(entity[key])) throw new Error('nonfinite combat');
    }
  }
  if(over.length!==zone) throw new Error('missing over');
  const result=over[zone-1];
  const remainingRoles=Object.values(area.entities).filter(e=>e.type==='role'&&e.teamId===1&&!e.isSummon)
    .map(e=>({kindId:e.kindId,idx:e._opts.idx,hp:e.hp,maxHp:e.initMaxHp,mp:e.mp}));
  zones.push({zone,ticks:zoneTicks,result,remainingRoles});
  if(!result.isWin||zone===stage.mobZoneCount) break;
  handler.smapBattleNext();
}
const last=zones[zones.length-1];
if(actionCursor!==input.actions.length) throw new Error('unconsumed action');
JSON.stringify({report:{format:'kbht-battle-report-v1',seed:input.seed,smapId:input.smapId,
  isWin:last.result.isWin,star:last.result.star,zones,ticks,remainingRoles:last.remainingRoles,
  acceptedActions,eventCount:events.length},events});
`, {filename:'audited-recovered-battle.js'});
  const result = JSON.parse(script.runInContext(context,{timeout:5000}));
  result.report.eventDigest = crypto.createHash('sha256').update(result.events.join('\n')).digest('hex');
  result.report.engineSourceSha256 = artifact.sourceSha256;
  result.report.engineArtifactSha256 = ARTIFACT_HASH;
  result.report.executionPolicy = 'smap-manual-tick-input-v1';
  result.report.inputSha256 = crypto.createHash('sha256').update(input).digest('hex');
  process.stdout.write(JSON.stringify(result.report));
} catch (_) {
  process.stderr.write('battle computation rejected\n');
  process.exitCode=1;
}
