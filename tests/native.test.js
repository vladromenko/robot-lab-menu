"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const vm = require("vm");
const core = require("../native/core.js");
const example = JSON.parse(fs.readFileSync("fixtures/homebrain-lab.example.json", "utf8"));

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

test("locator separates the remote descriptor and rejects shell switches", () => {
    const settings = {version: 1, ssh_destination: "operator@homebrain",
        handover_dir: "/a directory/with spaces and 'quotes", local_port: 18490,
        browser_bundle_id: "com.google.Chrome"};
    assert.equal(core.locator(settings).handover_dir, settings.handover_dir);
    assert.throws(() => core.locator({...settings, ssh_destination: "-oProxyCommand=bad"}));
    assert.throws(() => core.locator({...settings, local_port: 0}));
    assert.throws(() => core.locator({...settings, browser_bundle_id: "unknown.browser"}));
    assert.throws(() => core.locator({...settings, handover_dir: "Library/handover"}));
});

test("the canonical descriptor requires compatible versions and fixed scripts", () => {
    assert.equal(core.descriptor(example).descriptor_version, "homebrain.lab.v1");
    assert.throws(() => core.descriptor({...example, descriptor_version: "homebrain.lab.v2"}));
    assert.throws(() => core.descriptor({...example, supported_launcher_versions: ["9.0.0"]}));
    const invalid = clone(example);
    invalid.operations.handoff.argv = ["/bin/sh", "-c", "unexpected"];
    assert.throws(() => core.descriptor(invalid));
    const injection = clone(example);
    injection.authentication.post_path = '/" onload="unexpected';
    assert.throws(() => core.descriptor(injection));
});

test("handoff credentials are in the POST body while the target URL stays clean", () => {
    const ticket = {ticket: "test_ticket_that_is_never_a_real_secret", expires_in_s: 60};
    const html = core.form("http://127.0.0.1:18490", example, ticket);
    const action = /action="([^"]+)"/.exec(html)[1];
    assert.equal(action, "http://127.0.0.1:18490/api/launcher/handoff");
    assert.equal(action.includes(ticket.ticket), false);
    assert.match(html, /method="post"/);
    assert.throws(() => core.handoff({...ticket, expires_in_s: 999}));
    assert.equal(core.health({service_id: "other"}, example.service.health_expected), false);
});

function connectionContext() {
    const state = {settings: {ssh_destination: "homebrain", local_port: 18490},
        deployment: example, temporary: "/tmp/homebrain-tests"};
    const files = {};
    const calls = [];
    const context = {HB: state, HomebrainCore: core, Date, JSON,
        exists: (path) => files[path] !== undefined,
        jsonFile: (path) => JSON.parse(files[path]),
        writeText: (path, value) => { files[path] = value; },
        readText: () => "fixed remote helper",
        resources: (name) => name,
        checkedProcess: (program, argv) => { calls.push(argv); return "{}"; },
        process: () => ({code: 0}), pump: () => {}, status: () => {}};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync("native/macos-connection.js", "utf8"), context);
    return {context, files, calls};
}

test("duplicate launch reuses only the intended tunnel", () => {
    const {context, calls} = connectionContext();
    context.tunnel();
    context.tunnel();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].includes("127.0.0.1:18490:127.0.0.1:8090"), true);
    assert.equal(calls[0].includes("StrictHostKeyChecking=ask"), true);
    context.HB.settings.ssh_destination = "different-host";
    assert.throws(() => context.tunnel(), /other connection settings/);
    assert.equal(calls.length, 1);
});

test("a busy port reports failure without creating a success journal", () => {
    const {context, files} = connectionContext();
    context.checkedProcess = () => { throw new Error("Address already in use"); };
    assert.throws(() => context.tunnel(), /Address already in use/);
    assert.equal(Object.keys(files).length, 0);
});

test("an unrelated service cannot be accepted as ready", () => {
    const {context} = connectionContext();
    context.process = () => ({code: 0, output: '{"service_id":"unrelated"}'});
    assert.throws(() => context.serviceHealth(), /different service/);
    context.process = () => ({code: 7, error: "Connection refused"});
    assert.equal(context.serviceHealth(), false);
});

test("network restoration reconnects transport without issuing browser auth or arming", () => {
    const {context, calls} = connectionContext();
    context.HB.monitor = true;
    context.HB.retryDelay = 1;
    context.HB.nextCheck = 0;
    context.HB.connected = false;
    context.serviceHealth = () => true;
    context.checkConnection();
    assert.equal(context.HB.connected, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].includes("-N"), true);
});

test("the exact native shell quoting preserves a remote helper with quotes and newlines", () => {
    const {context} = connectionContext();
    const input = "import json\nprint('a path with spaces; and $characters')";
    const quoted = context.shellQuote(input);
    const {execFileSync} = require("child_process");
    const result = execFileSync("/bin/sh", ["-c", "printf %s " + quoted], {encoding: "utf8"});
    assert.equal(result, input);
});

test("an initial configuration error is not overwritten by transport monitoring", () => {
    const {context, calls} = connectionContext();
    context.HB.monitor = false;
    context.HB.nextCheck = 0;
    context.checkConnection();
    assert.equal(calls.length, 0);
});

test("a healthy common service is opened without any bootstrap start", () => {
    const {context} = connectionContext();
    const deployment = {...clone(example), fixture: false, deployed: true};
    const operations = [];
    context.HB.state = "/private/state";
    context.HB.window = {orderOut: () => {}};
    context.loadSettings = () => {};
    context.browserSupport = () => {};
    context.tunnel = () => {};
    context.serviceHealth = () => true;
    context.openAuthenticatedBrowser = () => { operations.push("handoff"); };
    context.remote = (operation) => { operations.push(operation); return deployment; };
    context.openWorkspace();
    context.openWorkspace();
    assert.deepEqual(operations, ["descriptor", "handoff", "descriptor", "handoff"]);
    assert.equal(context.HB.monitor, true);
});

test("existing strict host-key verification is honored and disabled checking is rejected", () => {
    const {context} = connectionContext();
    context.process = () => ({code: 0, output: "stricthostkeychecking true\n"});
    assert.equal(context.sshArgs().includes("StrictHostKeyChecking=yes"), true);
    context.process = () => ({code: 0, output: "stricthostkeychecking false\n"});
    assert.equal(context.sshArgs().includes("StrictHostKeyChecking=ask"), true);
});
