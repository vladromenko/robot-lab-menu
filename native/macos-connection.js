/* SSH discovery, a single owned tunnel, and the deployment health boundary. */
function shellQuote(value) {
    return "'" + value.replace(/'/g, "'\\''") + "'";
}

function sshArgs() {
    return ["-T", "-o", "StrictHostKeyChecking=ask", "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"];
}

function remoteArgs() {
    var args = sshArgs();
    var record = HB.temporary + "/tunnel.json";
    if (exists(record)) {
        var previous = JSON.parse(jsonFile(record).identity);
        if (previous.destination === HB.settings.ssh_destination) {
            args = args.concat(["-S", HB.temporary + "/ssh.sock", "-o", "ControlMaster=no"]);
        }
    }
    return args;
}

function remote(operation) {
    var reader = readText(resources("remote.py"));
    var command = "python3 -c " + shellQuote(reader);
    var request = JSON.stringify({operation: operation, directory: HB.settings.handover_dir});
    var output = checkedProcess("/usr/bin/ssh", remoteArgs().concat([HB.settings.ssh_destination, command]), request, 55);
    return JSON.parse(output);
}

function tunnelAlive() {
    if (!exists(HB.temporary + "/tunnel.json")) {
        return false;
    }
    var saved = jsonFile(HB.temporary + "/tunnel.json");
    var identity = JSON.stringify({destination: HB.settings.ssh_destination,
        port: HB.settings.local_port, origin: HB.deployment.service.origin});
    if (saved.identity !== identity) {
        throw new Error("The saved tunnel uses other connection settings. Close it from Connection Settings first.");
    }
    var result = process("/usr/bin/ssh",
        ["-S", HB.temporary + "/ssh.sock", "-O", "check", HB.settings.ssh_destination], "", 3);
    return result.code === 0;
}

function tunnel() {
    if (tunnelAlive()) {
        return;
    }
    var service = HomebrainCore.origin(HB.deployment.service.origin);
    var forward = "127.0.0.1:" + HB.settings.local_port + ":" + service.host + ":" + service.port;
    var args = sshArgs().concat(["-M", "-S", HB.temporary + "/ssh.sock",
        "-o", "ExitOnForwardFailure=yes", "-f", "-N", "-L", forward, HB.settings.ssh_destination]);
    checkedProcess("/usr/bin/ssh", args, "", 25);
    writeText(HB.temporary + "/tunnel.json", JSON.stringify({
        identity: JSON.stringify({destination: HB.settings.ssh_destination,
            port: HB.settings.local_port, origin: HB.deployment.service.origin})
    }));
}

function disconnectTunnel() {
    var saved = HB.state + "/locator.json";
    if (exists(HB.temporary + "/tunnel.json") && exists(saved)) {
        var prior = jsonFile(saved);
        process("/usr/bin/ssh", ["-S", HB.temporary + "/ssh.sock",
            "-O", "exit", prior.ssh_destination], "", 3);
        remove(HB.temporary + "/tunnel.json");
    }
}

function serviceHealth() {
    var url = HomebrainCore.localOrigin(HB.settings) + HB.deployment.service.health_path;
    var result = process("/usr/bin/curl",
        ["--noproxy", "*", "--silent", "--show-error", "--fail", "--max-time", "3", url], "", 5);
    if (result.code !== 0) {
        return false;
    }
    var response;
    try {
        response = JSON.parse(result.output);
    } catch (error) {
        throw new Error("The tunnel port answered with an unrelated or malformed service.");
    }
    if (!HomebrainCore.health(response, HB.deployment.service.health_expected)) {
        throw new Error("The local port answered with a different service. Homebrain did not open that page.");
    }
    return true;
}

function waitForService() {
    var deadline = Date.now() + 45000;
    var ready = false;
    while (!ready && Date.now() < deadline) {
        ready = serviceHealth();
        if (!ready) {
            pump(1);
        }
    }
    if (!ready) {
        throw new Error("The Homebrain Lab process did not become ready. Check its deployment status.");
    }
}

function openWorkspace() {
    status("Connecting", "Reading the deployment descriptor from Homebrain…");
    loadSettings();
    HB.deployment = HomebrainCore.descriptor(remote("descriptor"));
    if (HB.deployment.fixture || HB.deployment.deployed === false) {
        throw new Error("A fixture descriptor cannot open the live workspace.");
    }
    browserSupport();
    tunnel();
    if (!serviceHealth()) {
        if (!HB.deployment.operations.start) {
            throw new Error("The common service is stopped. This deployment has no authorized Start operation.");
        }
        status("Starting", "Starting the common Homebrain Lab service…");
        remote("start");
        waitForService();
    }
    status("Connecting", "Opening the authenticated workspace…");
    openAuthenticatedBrowser();
    HB.connected = true;
    HB.retryDelay = 3;
    HB.nextCheck = Date.now() + 5000;
    writeText(HB.state + "/deployment.json", JSON.stringify({
        service: HB.deployment.service, source_commit: HB.deployment.source_commit,
        descriptor_version: HB.deployment.descriptor_version
    }, null, 2));
    status("Ready", "Homebrain is open. Your task is kept by the server.");
    HB.window.orderOut(null);
}

function checkConnection() {
    if (!HB.deployment || Date.now() < HB.nextCheck) {
        return;
    }
    HB.nextCheck = Date.now() + HB.retryDelay * 1000;
    try {
        tunnel();
        if (!serviceHealth()) {
            throw new Error("The common service is unavailable.");
        }
        if (!HB.connected) {
            status("Ready", "Connection restored. Viewing can resume in the existing workspace.");
        }
        HB.connected = true;
        HB.retryDelay = 5;
    } catch (error) {
        if (HB.connected) bringWindow();
        HB.connected = false;
        HB.retryDelay = Math.min(30, HB.retryDelay * 2);
        status("Reconnecting", "Waiting for Homebrain. Check Wi-Fi or open Connection Settings.");
    }
}
