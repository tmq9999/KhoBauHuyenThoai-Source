/* Server-issued battle identity/seed and native consumed-tick action recording. */
(function (root) {
    'use strict';
    var current = null, frozen = null;
    function integer(value, min, max) {
        return typeof value === 'number' && isFinite(value) && Math.floor(value) === value && value >= min && value <= max;
    }
    function copy(value) { return JSON.parse(JSON.stringify(value)); }
    function validTeam(team) {
        if (!Array.isArray(team) || !team.length || team.length > 5) return false;
        var seen = {};
        for (var i = 0; i < team.length; i++) {
            if (typeof team[i] !== 'string' || !/^[1-5]$/.test(team[i]) || seen[team[i]]) return false;
            seen[team[i]] = true;
        }
        return true;
    }
    var api = {
        begin: function (battle, smapId, team) {
            if (!battle || battle.protocolVersion !== 1 || !integer(battle.seed, 1, 4294967295) ||
                    !integer(smapId, 1, 9007199254740991) || battle.smapId !== smapId ||
                    typeof battle.battleId !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(battle.battleId) ||
                    !validTeam(team)) throw new Error('Invalid authoritative battle');
            if (current && current.battleId === battle.battleId) {
                if (current.seed !== battle.seed || current.smapId !== smapId || JSON.stringify(current.team) !== JSON.stringify(team))
                    throw new Error('Battle identity conflict');
                return;
            }
            if (current) throw new Error('Previous authoritative battle is unresolved');
            current = {battleId: battle.battleId, seed: battle.seed, smapId: smapId, team: copy(team), actions: []};
            frozen = null;
        },
        seed: function (battleId, smapId) {
            if (!current || current.battleId !== battleId || current.smapId !== smapId || frozen) throw new Error('Authoritative battle missing');
            return current.seed;
        },
        consumed: function (battleId, zone, tick, skillIds) {
            if (!current || current.battleId !== battleId || frozen || !integer(zone, 1, 10) || !integer(tick, 1, 1802) || !Array.isArray(skillIds))
                throw new Error('Invalid battle action boundary');
            if (current.actions.length + skillIds.length > 256) throw new Error('Battle action limit');
            var previous = current.actions[current.actions.length - 1], pending = [];
            if (previous && (zone < previous.zone || (zone === previous.zone && tick < previous.tick)))
                throw new Error('Battle action order');
            for (var i = 0; i < skillIds.length; i++) {
                if (!integer(skillIds[i], 1, 1000000000)) throw new Error('Invalid skill');
                for (var j = 0; j < current.actions.length; j++) {
                    var item = current.actions[j];
                    if (item.zone === zone && item.tick === tick && item.skillId === skillIds[i]) throw new Error('Duplicate action');
                }
                if (skillIds.indexOf(skillIds[i]) !== i) throw new Error('Duplicate action');
                pending.push({zone: zone, tick: tick, skillId: skillIds[i]});
            }
            current.actions = current.actions.concat(pending);
        },
        settlement: function (battleId, star, team) {
            if (!current || current.battleId !== battleId || !integer(star, 0, 3) || !validTeam(team) || JSON.stringify(team) !== JSON.stringify(current.team))
                throw new Error('Invalid battle settlement');
            var request = {battleId: current.battleId, protocolVersion: 1, star: star, teamIndexs: copy(team), actions: copy(current.actions)};
            if (frozen && JSON.stringify(frozen) !== JSON.stringify(request)) throw new Error('Settlement changed');
            frozen = request;
            return copy(frozen);
        },
        settled: function (battleId) {
            if (!current || !frozen || current.battleId !== battleId) throw new Error('Unexpected settlement');
            current = frozen = null;
        },
        active: function () { return current !== null; },
        matches: function (battleId) { return current !== null && current.battleId === battleId && !frozen; }
    };
    root.kbhtBattleCommands = api;
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : this));
