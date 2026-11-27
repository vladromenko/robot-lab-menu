/* Descriptor and locator rules shared by the native launcher and tests. */
"use strict";
var VERSION = "0.2.0";
var DEFAULT_HANDOVER = "~/.local/share/homebrain-lab/handover";
var BROWSERS = ["com.google.Chrome", "com.microsoft.edgemac", "com.apple.Safari"];

function fail(message) {
    throw new Error(message);
}

function text(value, label, maximum) {
    if (typeof value !== "string" || !value || value.length > maximum || /[\u0000-\u001f]/.test(value)) {
        fail("Invalid " + label + ".");
    }
    return value;
}

function path(value, label) {
    text(value, label, 1024);
    if (!/^\/[A-Za-z0-9_./~-]*$/.test(value) || value.indexOf("..") !== -1) {
        fail("Invalid " + label + ".");
    }
    return value;
}

function locator(value) {
    if (!value || value.version !== 1) {
        fail("Connection settings have an unsupported version.");
    }
    text(value.ssh_destination, "SSH destination", 200);
    if (!/^[A-Za-z0-9_][A-Za-z0-9_.@-]*$/.test(value.ssh_destination)) {
        fail("Use an existing SSH host alias or user@host destination.");
    }
    var directory = text(value.handover_dir, "remote handover directory", 1024);
    if (directory[0] !== "/" && directory.indexOf("~/") !== 0) {
        fail("The remote handover directory must be absolute or start with ~/.");
    }
    if (!Number.isInteger(value.local_port) || value.local_port < 1024 || value.local_port > 65535) {
        fail("Choose a local port between 1024 and 65535.");
    }
    if (BROWSERS.indexOf(value.browser_bundle_id) === -1) {
        fail("Select an installed supported browser in Connection Settings.");
    }
    return value;
}

function origin(value) {
    var match = /^http:\/\/(127\.0\.0\.1|localhost):([0-9]{1,5})$/.exec(value || "");
    if (!match || Number(match[2]) < 1 || Number(match[2]) > 65535) {
        fail("The service must declare an HTTP loopback origin on Homebrain.");
    }
    return {host: match[1], port: Number(match[2])};
}

function command(value, operation) {
    if (!value) {
        return null;
    }
    var expected = {status: "status", start: "start", handoff: "handoff"}[operation];
    var argv = value.argv;
    if (!expected || !Array.isArray(argv) || argv.length !== 2 || argv[1] !== expected) {
        fail("The descriptor contains an unsupported " + operation + " command.");
    }
    text(argv[0], operation + " script path", 1024);
    if (argv[0][0] !== "/") fail("The launcher script path must be absolute.");
    if (!/\/homebrain-lab-launcher(?:\.py)?$/.test(argv[0]) || !/^[a-f0-9]{64}$/.test(value.sha256 || "")) {
        fail("The descriptor command must name the pinned Homebrain Lab launcher script.");
    }
    return value;
}

function descriptor(value) {
    if (!value || value.descriptor_version !== "homebrain.lab.v1") {
        fail("The service descriptor version is incompatible with Homebrain " + VERSION + ".");
    }
    if (value.compatible_contract_version !== "homebrain.lab.v1") {
        fail("The Homebrain Lab contract version is incompatible.");
    }
    if (!/^[a-f0-9]{40}$/.test(value.source_commit || "")) {
        fail("The descriptor is missing the deployed source commit.");
    }
    var versions = value.supported_launcher_versions;
    if (!Array.isArray(versions) || versions.indexOf(VERSION) === -1) {
        fail("This deployment does not support launcher " + VERSION + ".");
    }
    var service = value.service || {};
    origin(service.origin);
    path(service.workspace_path, "workspace path");
    path(service.health_path, "health path");
    text(service.id, "service identity", 100);
    if (!service.health_expected || service.health_expected.service_id !== service.id) {
        fail("The health response must identify the specific Homebrain Lab service.");
    }
    var auth = value.authentication || {};
    if (auth.method !== "ssh-once-form-post-v1" || auth.operation !== "handoff" || auth.field !== "ticket") {
        fail("The deployment has an unsupported browser session handoff.");
    }
    path(auth.post_path, "session handoff path");
    text(auth.resume_method, "session resume method", 1000);
    text(value.installation_instructions, "installation instructions", 4000);
    var operations = value.operations || {};
    ["status", "start", "handoff"].forEach(function (id) { command(operations[id], id); });
    if (!operations.handoff) {
        fail("The deployment has no SSH browser handoff operation.");
    }
    return value;
}

function health(actual, expected) {
    return !!actual && Object.keys(expected).every(function (key) {
        return actual[key] === expected[key];
    });
}

function localOrigin(settings) {
    return "http://127.0.0.1:" + settings.local_port;
}

function handoff(value) {
    if (!value || typeof value.ticket !== "string" || !/^[A-Za-z0-9_-]{24,256}$/.test(value.ticket)) {
        fail("The SSH handoff operation returned an invalid single-use ticket.");
    }
    if (typeof value.expires_in_s !== "number" || value.expires_in_s <= 0 || value.expires_in_s > 120) {
        fail("The SSH handoff ticket lifetime is outside the supported limit.");
    }
    return value;
}

function form(local, deployment, ticket) {
    handoff(ticket);
    var action = local + deployment.authentication.post_path;
    return '<!doctype html><meta charset="utf-8"><title>Opening Homebrain</title>' +
        '<meta name="referrer" content="no-referrer"><body><p>Opening Homebrain…</p>' +
        '<form method="post" action="' + action + '"><input type="hidden" name="ticket" value="' +
        ticket.ticket + '"><button type="submit">Open workspace</button></form>' +
        '<script>document.forms[0].submit();</script>';
}

var HomebrainCore = {VERSION: VERSION, DEFAULT_HANDOVER: DEFAULT_HANDOVER, BROWSERS: BROWSERS,
    locator: locator, descriptor: descriptor, origin: origin, command: command,
    health: health, localOrigin: localOrigin, handoff: handoff, form: form};
if (typeof module !== "undefined") {
module.exports = HomebrainCore;
}
