"use strict";
const fs = require("fs");
const vm = require("vm");
const {spawnSync} = require("child_process");
const core = require("../native/core.js");
const config = JSON.parse(fs.readFileSync(0, "utf8"));
var starts = 0;

function processCall(program, args) {
    const result = spawnSync(program, ["-F", config.ssh_config].concat(args), {encoding: "utf8", timeout: 15000});
    if (result.error) throw result.error;
    return {code: result.status, output: result.stdout, error: result.stderr};
}

function checkedProcess(program, args) {
    const result = processCall(program, args);
    if (result.code !== 0) throw new Error(result.error);
    if (args.includes("-N")) starts += 1;
    return result.output;
}

const context = {HB: {temporary: config.socket_dir,
    settings: {ssh_destination: "homebrain-test", local_port: config.local_port},
    deployment: {service: {origin: "http://127.0.0.1:1"}}}, HomebrainCore: core, JSON, Date,
    process: processCall, checkedProcess, exists: fs.existsSync,
    jsonFile: (path) => JSON.parse(fs.readFileSync(path, "utf8")),
    writeText: (path, value) => fs.writeFileSync(path, value, {mode: 0o600}),
    remove: (path) => fs.unlinkSync(path)};
vm.createContext(context);
vm.runInContext(fs.readFileSync("native/macos-connection.js", "utf8"), context);
context.tunnel();
context.tunnel();
if (!context.tunnelAlive() || starts !== 1) throw new Error("The owned SSH master was not reused.");
process.stdout.write(JSON.stringify({stale_socket_recovered: true, masters_started: starts}));
