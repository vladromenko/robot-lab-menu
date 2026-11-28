/* A thin applet uses the validated connection helpers without a custom Cocoa window. */
function status(title, detail) {
    writeText(HB.state + "/connection-status.json", JSON.stringify({
        state: title, detail: detail, updated_at: new Date().toISOString()
    }, null, 2));
}

function workspaceConfirmation() {
    var expected = HomebrainCore.localOrigin(HB.settings) + HB.deployment.service.workspace_path;
    if (HB.settings.browser_open_mode === "standard") {
        writeText(HB.state + "/browser-launch.json", JSON.stringify({
            workspace_url: expected, browser_bundle_id: HB.settings.browser_bundle_id,
            method: "macOS Launch Services", requested_at: new Date().toISOString(),
            capability_validation: "Viewer, gamepad and audio require separate browser acceptance."
        }, null, 2));
        status("Opened", "Homebrain was sent to the selected browser.");
        while (Date.now() < HB.deleteFormAt) pump(0.25);
        return;
    }
    var application = Application(HB.settings.browser_bundle_id);
    var deadline = Date.now() + 25000;
    var ready = false;
    var title = "";
    while (!ready && Date.now() < deadline) {
        var found = existingTab(application, HomebrainCore.localOrigin(HB.settings), "");
        if (found && found.tab.url() === expected) {
            title = HB.settings.browser_bundle_id === "com.apple.Safari" ? found.tab.name() : found.tab.title();
            ready = /homebrain/i.test(title || "");
        }
        if (!ready) pump(0.25);
    }
    if (!ready) {
        throw new Error("The browser has not reached the Homebrain workspace. Open Homebrain again to retry.");
    }
    writeText(HB.state + "/browser-confirmation.json", JSON.stringify({
        workspace_url: expected, title: title, browser_bundle_id: HB.settings.browser_bundle_id,
        verified_at: new Date().toISOString()
    }, null, 2));
}

function launchWorkspace() {
    loadSettings();
    status("Connecting", "Reading the deployed Homebrain Lab connection…");
    HB.deployment = HomebrainCore.descriptor(remote("descriptor"));
    if (HB.deployment.fixture || HB.deployment.deployed !== true) {
        throw new Error("The common Homebrain workspace has not been deployed yet.");
    }
    browserSupport();
    tunnel();
    if (!serviceHealth()) {
        if (!HB.deployment.operations.start) {
            throw new Error("The common service is unavailable and has no authorized Start operation.");
        }
        status("Starting", "Starting the declared common Homebrain service…");
        remote("start");
        waitForService();
    }
    status("Connecting", "Opening the authenticated workspace in the selected browser…");
    openAuthenticatedBrowser();
    workspaceConfirmation();
    writeText(HB.state + "/deployment.json", JSON.stringify({
        service: HB.deployment.service, source_commit: HB.deployment.source_commit,
        descriptor_version: HB.deployment.descriptor_version
    }, null, 2));
    status(HB.settings.browser_open_mode === "standard" ? "Opened" : "Ready", "Homebrain was sent to the selected browser.");
}

function restoreViewingConnection() {
    if (!exists(HB.state + "/deployment.json") || exists(HB.state + "/app.lock")) return;
    loadSettings();
    HB.deployment = jsonFile(HB.state + "/deployment.json");
    tunnel();
    if (!serviceHealth()) throw new Error("The common Homebrain service is unavailable.");
    status("Ready", "The viewing connection is available.");
}

function editConnection() {
    var file = HB.state + "/locator.json";
    HB.settings = exists(file) ? HomebrainCore.locator(jsonFile(file)) : null;
    settingsDialog();
}

function run(argv) {
    var owner = false;
    var reconnect = (argv || []).indexOf("--reconnect") !== -1;
    HB.dialog = Application.currentApplication();
    HB.dialog.includeStandardAdditions = true;
    try {
        configure(argv || []);
        if (reconnect) {
            restoreViewingConnection();
        } else {
            owner = ownInstance();
            if (owner) {
                if (argv.indexOf("--settings") !== -1) editConnection();
                launchWorkspace();
            }
        }
    } catch (error) {
        if (HB.state) status("Connection needs attention", String(error.message || error).slice(0, 800));
        throw error;
    } finally {
        if (owner) {
            remove(HB.state + "/open-workspace.html");
            remove(HB.state + "/open-request");
            remove(HB.state + "/app.lock/pid");
            remove(HB.state + "/app.lock");
        }
    }
}
