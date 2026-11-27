/* Application entry point. The same bundle also supports the Terminal shortcut. */
function configure(argv) {
    var supplied = argv[0] || "";
    HB.resources = supplied && exists(supplied + "/homebrain.js") ? supplied : string($.NSBundle.mainBundle.resourcePath);
    HB.packageRoot = string($(HB.resources).stringByDeletingLastPathComponent.stringByDeletingLastPathComponent.stringByDeletingLastPathComponent);
    HB.state = privateDirectory(string($.NSHomeDirectory()) + "/Library/Application Support/Homebrain");
    HB.temporary = privateDirectory("/tmp/homebrain-launcher-" + uid());
}

function eventLoop(argv) {
    createWindow();
    HB.action = argv.indexOf("--settings") !== -1 ? "settings" : "open";
    while (!HB.quitting) {
        var pool = $.NSAutoreleasePool.alloc.init;
        try {
            pump(0.1);
            if (exists(HB.state + "/open-request")) {
                var requested = Number(readText(HB.state + "/open-request"));
                remove(HB.state + "/open-request");
                if (!HB.connected || requested > (HB.lastOpenCompleted || 0)) HB.action = "open";
            }
            if (HB.action) {
                performAction();
            }
            checkConnection();
            removeExpiredForm();
        } finally {
            pool.drain;
        }
    }
}

function run(argv) {
    HB.dialog = Application.currentApplication();
    HB.dialog.includeStandardAdditions = true;
    var owner = false;
    try {
        argv = argv || [];
        configure(argv);
        owner = ownInstance();
        if (owner) {
            eventLoop(argv);
        }
    } catch (error) {
        HB.dialog.displayAlert("Homebrain could not open", {
            message: String(error.message || error).slice(0, 800), as: "critical"
        });
    } finally {
        if (owner) {
            remove(HB.state + "/open-workspace.html");
            remove(HB.state + "/app.lock/pid");
            remove(HB.state + "/app.lock");
        }
    }
}
