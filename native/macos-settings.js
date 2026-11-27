/* Saved bootstrap settings belong to the Mac, independently of the remote descriptor. */
function installedBrowsers() {
    return HomebrainCore.BROWSERS.filter(function (id) {
        var url = $.NSWorkspace.sharedWorkspace.URLForApplicationWithBundleIdentifier($(id));
        return url && !url.isNil();
    });
}

function initialDestination() {
    var environment = ObjC.deepUnwrap($.NSProcessInfo.processInfo.environment);
    var configured = environment.HOMEBRAIN_SSH_DESTINATION || environment.ROBOT_LAB_HOMEBRAIN_SSH;
    if (!configured && environment.HOMEBRAIN_HOST && environment.HOMEBRAIN_USER) {
        configured = environment.HOMEBRAIN_USER + "@" + environment.HOMEBRAIN_HOST;
    }
    if (configured) {
        return configured;
    }
    var recovery = HB.packageRoot + "/configs/local.json";
    if (exists(recovery)) {
        var value = jsonFile(recovery);
        if (value.homebrain_ssh) {
            return value.homebrain_ssh;
        }
    }
    var sshConfig = string($.NSHomeDirectory()) + "/.ssh/config";
    if (exists(sshConfig) && /^Host[ \t]+homebrain(?:[ \t]|$)/im.test(readText(sshConfig))) {
        return "homebrain";
    }
    return "";
}

function answer(prompt, defaultValue) {
    var response = HB.dialog.displayDialog(prompt, {
        withTitle: "Homebrain connection", defaultAnswer: defaultValue || "",
        buttons: ["Cancel", "Save"], defaultButton: "Save", cancelButton: "Cancel"
    });
    return response.textReturned.trim();
}

function settingsDialog() {
    var current = HB.settings || {};
    var destination = answer("Existing SSH host alias or user@host for Homebrain", current.ssh_destination || initialDestination());
    var directory = answer("Deployment handover directory on Homebrain", current.handover_dir || HomebrainCore.DEFAULT_HANDOVER);
    var port = Number(answer("Local tunnel port on this Mac", String(current.local_port || 18490)));
    var installed = installedBrowsers();
    var names = {"com.google.Chrome": "Google Chrome", "com.microsoft.edgemac": "Microsoft Edge", "com.apple.Safari": "Safari"};
    var choices = installed.map(function (id) { return names[id]; });
    if (!choices.length) {
        throw new Error("Install Google Chrome, Microsoft Edge or Safari to open the workspace.");
    }
    var selected = HB.dialog.chooseFromList(choices, {
        withTitle: "Homebrain browser", withPrompt: "Choose the installed browser for the common workspace.",
        defaultItems: [names[current.browser_bundle_id] || choices[0]]
    });
    if (!selected) {
        throw new Error("Connection setup was canceled.");
    }
    var index = choices.indexOf(selected[0]);
    var value = {version: 1, ssh_destination: destination, handover_dir: directory,
        local_port: port, browser_bundle_id: installed[index]};
    HomebrainCore.locator(value);
    if (HB.settings) {
        disconnectTunnel();
    }
    HB.settings = value;
    writeText(HB.state + "/locator.json", JSON.stringify(value, null, 2));
    return value;
}

function loadSettings() {
    var path = HB.state + "/locator.json";
    HB.settings = exists(path) ? HomebrainCore.locator(jsonFile(path)) : null;
    if (!HB.settings) {
        settingsDialog();
    }
    var environment = ObjC.deepUnwrap($.NSProcessInfo.processInfo.environment);
    if (environment.HOMEBRAIN_LAB_HANDOVER_DIR) {
        HB.settings.handover_dir = environment.HOMEBRAIN_LAB_HANDOVER_DIR;
    }
    return HomebrainCore.locator(HB.settings);
}
