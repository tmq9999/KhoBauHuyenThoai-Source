(function (root) {
    "use strict";

    function formatPower(value) {
        if (typeof value !== "number" || !isFinite(value) || value < 0) {
            throw new Error("invalid power");
        }
        return String(Math.floor(value));
    }

    function formatRankValue(value, type) {
        if (type !== "totalPower" && type !== "playerTop5power") return value;
        if (value === "?") return value;
        return formatPower(value);
    }

    var api = {formatPower: formatPower, formatRankValue: formatRankValue};
    if (typeof module !== "undefined" && module.exports) module.exports = api;
    else root.kbhtPowerDisplay = api;
}(typeof window !== "undefined" ? window : this));
