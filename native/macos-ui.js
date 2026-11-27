/* A small native connection window, with no laboratory controls. */
function label(value, frame, size) {
    var view = $.NSTextField.labelWithString($(value));
    view.frame = frame;
    view.font = $.NSFont.systemFontOfSize(size);
    view.lineBreakMode = $.NSLineBreakByWordWrapping;
    return view;
}

function button(title, frame, selector) {
    var view = $.NSButton.buttonWithTitleTargetAction($(title), HB.delegate, $(selector));
    view.frame = frame;
    view.bezelStyle = $.NSBezelStyleRounded;
    HB.window.contentView.addSubview(view);
    return view;
}

function status(title, detail) {
    HB.title.stringValue = $(title);
    HB.detail.stringValue = $(detail);
    if (title === "Ready" || title === "Connection needs attention") {
        HB.spinner.stopAnimation(null);
    } else {
        HB.spinner.startAnimation(null);
    }
    pump(0.03);
}

function bringWindow() {
    HB.window.makeKeyAndOrderFront(null);
    HB.app.activateIgnoringOtherApps(true);
}

function delegates() {
    ObjC.registerSubclass({
        name: "HomebrainWindowDelegate",
        superclass: "NSObject",
        protocols: ["NSApplicationDelegate", "NSWindowDelegate"],
        methods: {
            "openWorkspace:": {types: ["void", ["id"]], implementation: function () { if (!HB.busy) HB.action = "open"; }},
            "connectionSettings:": {types: ["void", ["id"]], implementation: function () { HB.action = "settings"; }},
            "recoveryMenu:": {types: ["void", ["id"]], implementation: function () { HB.action = "recovery"; }},
            "quitLauncher:": {types: ["void", ["id"]], implementation: function () { HB.quitting = true; }},
            "applicationShouldHandleReopen:hasVisibleWindows:": {
                types: ["bool", ["id", "bool"]], implementation: function () {
                    if (!HB.busy) HB.action = "open";
                    bringWindow();
                    return true;
                }
            },
            "windowShouldClose:": {types: ["bool", ["id"]], implementation: function () {
                HB.window.orderOut(null);
                return false;
            }},
            "applicationShouldTerminate:": {types: ["long", ["id"]], implementation: function () {
                HB.quitting = true;
                return $.NSTerminateNow;
            }}
        }
    });
    HB.delegate = $.HomebrainWindowDelegate.alloc.init;
}

function mainMenu() {
    var menu = $.NSMenu.alloc.init;
    var entry = $.NSMenuItem.alloc.init;
    menu.addItem(entry);
    var application = $.NSMenu.alloc.initWithTitle($("Homebrain"));
    var show = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent($("Open Homebrain"), $("openWorkspace:"), $("o"));
    show.target = HB.delegate;
    application.addItem(show);
    var quit = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent($("Quit Homebrain"), $("quitLauncher:"), $("q"));
    quit.target = HB.delegate;
    application.addItem(quit);
    entry.submenu = application;
    HB.app.mainMenu = menu;
}

function createWindow() {
    HB.app = $.NSApplication.sharedApplication;
    HB.app.setActivationPolicy($.NSApplicationActivationPolicyRegular);
    delegates();
    HB.app.delegate = HB.delegate;
    HB.window = $.NSWindow.alloc.initWithContentRectStyleMaskBackingDefer(
        $.NSMakeRect(0, 0, 560, 310), $.NSWindowStyleMaskTitled | $.NSWindowStyleMaskClosable |
        $.NSWindowStyleMaskMiniaturizable, $.NSBackingStoreBuffered, false);
    HB.window.title = $("Homebrain");
    HB.window.delegate = HB.delegate;
    HB.window.center;
    var icon = $.NSImage.alloc.initWithContentsOfFile($(resources("Homebrain.icns")));
    HB.app.applicationIconImage = icon;
    HB.title = label("Connecting", $.NSMakeRect(88, 223, 440, 35), 26);
    HB.detail = label("Opening the common laboratory workspace…", $.NSMakeRect(88, 143, 432, 74), 14);
    HB.window.contentView.addSubview(HB.title);
    HB.window.contentView.addSubview(HB.detail);
    HB.spinner = $.NSProgressIndicator.alloc.initWithFrame($.NSMakeRect(32, 230, 32, 32));
    HB.spinner.style = $.NSProgressIndicatorStyleSpinning;
    HB.window.contentView.addSubview(HB.spinner);
    button("Open workspace", $.NSMakeRect(25, 91, 165, 32), "openWorkspace:");
    button("Connection settings", $.NSMakeRect(194, 91, 175, 32), "connectionSettings:");
    button("Recovery menu", $.NSMakeRect(373, 91, 160, 32), "recoveryMenu:");
    HB.window.contentView.addSubview(label("Server owns tasks and native control sessions.",
        $.NSMakeRect(32, 35, 480, 36), 12));
    mainMenu();
    HB.app.finishLaunching;
    bringWindow();
}

function existingInstance(pid, folder) {
    if (/^[1-9][0-9]*$/.test(pid)) {
        var result = process("/bin/ps", ["-p", pid, "-o", "command="], "", 3);
        return result.code === 0 && (result.output.indexOf("Homebrain.app/Contents/MacOS/") !== -1 ||
            result.output.indexOf(HB.resources + "/homebrain.js") !== -1);
    }
    var information = FS.attributesOfItemAtPathError($(folder), null);
    var changed = information.objectForKey("NSFileModificationDate");
    return Math.abs(changed.timeIntervalSinceNow) < 10;
}

function ownInstance() {
    var folder = HB.state + "/app.lock";
    var result = process("/bin/mkdir", [folder], "", 3);
    if (result.code !== 0) {
        var pidFile = folder + "/pid";
        var pid = exists(pidFile) ? readText(pidFile).trim() : "";
        if (!pid) {
            pump(0.5);
            pid = exists(pidFile) ? readText(pidFile).trim() : "";
        }
        if (existingInstance(pid, folder)) {
            writeText(HB.state + "/open-request", String(Date.now()));
            return false;
        }
        remove(pidFile);
        remove(folder);
        checkedProcess("/bin/mkdir", [folder], "", 3);
    }
    writeText(folder + "/pid", String($.NSProcessInfo.processInfo.processIdentifier));
    return true;
}

function performAction() {
    var action = HB.action;
    HB.action = "";
    HB.busy = true;
    try {
        if (action === "settings") {
            settingsDialog();
            HB.deployment = null;
            HB.connected = false;
            action = "open";
        }
        if (action === "open") {
            bringWindow();
            openWorkspace();
        }
        if (action === "recovery") {
            checkedProcess("/usr/bin/open", ["-a", "Terminal", HB.packageRoot + "/Robot_Lab.command"], "", 5);
        }
    } catch (error) {
        HB.connected = false;
        status("Connection needs attention", String(error.message || error).slice(0, 800));
        bringWindow();
    } finally {
        HB.busy = false;
    }
}
