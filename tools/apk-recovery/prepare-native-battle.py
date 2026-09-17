"""Exact native SMAP seed/action/settlement staging; source input stays immutable."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path


def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def transform(source):
    replacements=(
      ('o.tick = function(e) {\nthis.totalDt += e / 1e3;',
       'o.tick = function(e) {\n'
       'if (this.area.nativeBattleId && !window.kbhtBattleCommands.matches(this.area.nativeBattleId)) {\n'
       'if (this.interval && i.isShow) _clearInterval(this.interval);\n'
       'this.interval = null; return;\n}\nthis.totalDt += e / 1e3;'),
      ('case d.SMAP_BATTLE_ATTACK_TEAM:\nvar b = function(e, t) {',
       'case d.SMAP_BATTLE_ATTACK_TEAM:\n'
       'if (!this.statusData.opts.isEndless && this.data.selectShipIdxs.length) {\n'
       'i.addHintPanel("Trận server chưa hỗ trợ tàu"); return; }\n'
       'var nativeSelection = {smapId: h.statusData.opts.smapId, roles: h.data.selectIdxs.slice(0), ships: h.data.selectShipIdxs.slice(0)};\n'
       'var b = function(e, t, battleId) {'),
      ('for (var a in h.data.selectShipIdxs) {\nvar s = m.player.bag.getItemByIdx(h.data.selectShipIdxs[a]);',
       'for (var a in nativeSelection.ships) {\nvar s = m.player.bag.getItemByIdx(nativeSelection.ships[a]);'),
      ('for (var a in h.data.selectIdxs) {\nvar c = m.player.team.getRoleByIdx(h.data.selectIdxs[a], !0);',
       'for (var a in nativeSelection.roles) {\nvar c = m.player.team.getRoleByIdx(nativeSelection.roles[a], !0);'),
      ('var d = P.buildBattleTeam(m.player.id, n, u), p = r.smap.findById(h.statusData.opts.smapId)',
       'var d = P.buildBattleTeam(m.player.id, n, u), p = r.smap.findById(nativeSelection.smapId)'),
      ('smapId: h.statusData.opts.smapId,\nshowEntityIdsMap: e,',
       'smapId: nativeSelection.smapId,\nnativeBattleId: battleId || null,\nshowEntityIdsMap: e,'),
      ('selectIdxs: h.data.selectIdxs,\nisEndless: t,',
       'selectIdxs: nativeSelection.roles.slice(0),\nisEndless: t,'),
      ('k.beginSmap(this.statusData.opts.smapId, this.data.selectIdxs, function(e) {\nb(e._temp.showEntityIdsMap, !1);',
       'k.beginSmap(nativeSelection.smapId, nativeSelection.roles.slice(0), function(e) {\n'
       'try { window.kbhtBattleCommands.begin(e._temp.battle, nativeSelection.smapId, nativeSelection.roles); }\n'
       'catch (ignored) { i.removeLoading(); i.addHintPanel("Không đồng bộ được trận server"); return; }\n'
       'b(e._temp.showEntityIdsMap, !1, e._temp.battle.battleId);'),
      ('a.request("logic.smapHandler.beginSmap", {\nsmapId: e,\nteamIndexs: t',
       'a.request("logic.smapHandler.beginSmap", {\nsmapId: e,\nprotocolVersion: 1,\nteamIndexs: t'),
      ('l.endSmap = function(e, t, n) {\na.request("logic.smapHandler.endSmap", {\nstar: e,\nteamIndexs: t\n}, function(e) {\nn && n(e);',
       'l.endSmap = function(e, t, n, battleId) {\nvar request;\n'
       'try { request = window.kbhtBattleCommands.settlement(battleId, e, t); }\n'
       'catch (ignored) { a.receiveCb && a.receiveCb({code: 500, msg: "Trận server không hợp lệ"}); return; }\n'
       'a.request("logic.smapHandler.endSmap", request, function(e) {\n'
       'try { window.kbhtBattleCommands.settled(e._temp.battleId); }\n'
       'catch (ignored) { a.receiveCb && a.receiveCb({code: 500, msg: "Kết quả trận không khớp"}); return; }\nn && n(e);'),
      ('_.endSmap(n, this.statusData.opts.selectIdxs, function(e) {\no(e._temp.entityCountMap);\n});',
       '_.endSmap(n, this.statusData.opts.selectIdxs, function(e) {\no(e._temp.entityCountMap);\n}, this.statusData.opts.nativeBattleId);'),
      ('S.smapBattle(this.statusData.team1, t.manualShipSkillIds, t.manualSkillIds, this.statusData.opts.smapId, this.statusData.opts.showEntityIdsMap);',
       'S.smapBattle(this.statusData.team1, t.manualShipSkillIds, t.manualSkillIds, this.statusData.opts.smapId, this.statusData.opts.showEntityIdsMap, this.statusData.opts.nativeBattleId);'),
      ('i.smapBattle = function(e, t, n, l, s) {',
       'i.smapBattle = function(e, t, n, l, s, nativeBattleId) {'),
      ('i.setSeed(Date.now());\nr.smapBattle(e, l, s);',
       'i.setSeed(nativeBattleId ? window.kbhtBattleCommands.seed(nativeBattleId, l) : Date.now());\nr.smapBattle(e, l, s, nativeBattleId);'),
      ('i.smapBattleNext = function() {\ni.useSkillIds = [];',
       'i.smapBattleNext = function(nativeBattleId) {\n'
       'if (r.nativeBattleId && (nativeBattleId !== r.nativeBattleId || !window.kbhtBattleCommands.matches(nativeBattleId))) throw new Error("Stale native battle");\ni.useSkillIds = [];'),
      ('smapBattle: function(e, t, n) {\nthis.team = a.clone(e);',
       'smapBattle: function(e, t, n, nativeBattleId) {\nthis.nativeBattleId = nativeBattleId || null;\nthis.team = a.clone(e);'),
      ('smapId: this.smapId,\nshowEntityIdsMap: this.showEntityIdsMap',
       'smapId: this.smapId,\nnativeBattleId: this.nativeBattleId || null,\nshowEntityIdsMap: this.showEntityIdsMap'),
      ('S.smapBattleNext();', 'S.smapBattleNext(this.statusData.opts.nativeBattleId);'),
      ('this.smapId = Number(e.smapId);\nthis.showEntityIdsMap',
       'this.smapId = Number(e.smapId);\nthis.nativeBattleId = e.nativeBattleId || null;\nthis.showEntityIdsMap'),
      ('if (!i.isInstant) {\nfor (var d in i.useSkillIds) r.useSkill(i.useSkillIds[d]);',
       'if (!i.isInstant) {\n'
       'if (i.battleType == a.BATTLE_TYPE.SMAP && this.area.nativeBattleId) {\n'
       'if (!window.kbhtBattleCommands.matches(this.area.nativeBattleId)) {\n'
       'if (this.interval && i.isShow) _clearInterval(this.interval); this.interval = null; return; }\n'
       'window.kbhtBattleCommands.consumed(this.area.nativeBattleId, this.area.zoneId, this.tickNumber, i.useSkillIds);\n}\n'
       'for (var d in i.useSkillIds) r.useSkill(i.useSkillIds[d]);'),
      ('onAuto_: function(e, t) {\nthis.nextBt.active',
       'onAuto_: function(e, t) {\n'
       'if (this.statusData.battleType == L.SMAP && this.statusData.opts.nativeBattleId) { this.data.isAuto = false; S.isAuto = false; return; }\nthis.nextBt.active'),
    )
    for before,after in replacements:
        if source.count(before)!=1: raise ValueError('native battle pin missing or duplicated: '+before[:70])
        source=source.replace(before,after,1)
    return source


def stage(staged,reference,patch,availability_patch,stage_root,*,power_display=False):
    paths=module('battle_paths','stage-client-patches.py')
    root=paths._validate_stage(stage_root)
    inputs=[paths._require_plain_file(p,'battle input') for p in (staged,reference,patch,availability_patch)]
    staged,reference,patch,availability_patch=inputs
    if not paths._under(staged,root) or staged.stat().st_nlink!=1: raise ValueError('battle destination escape or hardlink')
    for i,left in enumerate(inputs):
        for right in inputs[i+1:]:
            if os.path.samefile(left,right): raise ValueError('battle input alias')
    raw=reference.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=paths.PINNED_PROJECT_SHA256: raise ValueError('battle reference hash mismatch')
    prepare=module('battle_prior','prepare-lab-bootstrap.py')
    available=module('battle_available','prepare-native-availability.py')
    expected=prepare.apply_local_auth_transform(prepare.remap_build_ext_text(raw.decode('utf-8')))
    if power_display: expected=prepare.apply_power_display_transform(expected)
    expected=availability_patch.read_text(encoding='utf-8')+'\n'+available.transform(expected)
    if staged.read_bytes()!=expected.encode('utf-8'): raise ValueError('battle staged predecessor mismatch')
    output=patch.read_bytes()+b'\n'+transform(expected).encode('utf-8')
    staged.write_bytes(output)
    return hashlib.sha256(output).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','reference','patch','availability-patch','stage-root'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--power-display',action='store_true')
    args=parser.parse_args()
    try: digest=stage(args.input,args.reference,args.patch,args.availability_patch,args.stage_root,power_display=args.power_display)
    except (ValueError,OSError) as error: parser.error(str(error))
    print('native_battle_sha256='+digest)

if __name__=='__main__':main()
