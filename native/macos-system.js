/* Native macOS I/O. All process arguments are passed as arrays. */
ObjC.import("Cocoa");
var HB = {quitting: false, action: "", connected: false, nextCheck: 0, retryDelay: 3};
var FS = $.NSFileManager.defaultManager;

function string(value) {
    return ObjC.unwrap(value);
}

function exists(path) {
    return FS.fileExistsAtPath($(path));
}

function readText(path) {
    var error = Ref();
    var value = $.NSString.stringWithContentsOfFileEncodingError($(path), $.NSUTF8StringEncoding, error);
    if (!value || value.isNil()) {
        throw new Error("Cannot read " + path + ".");
    }
    return string(value);
}

function writeText(path, contents) {
    var error = Ref();
    var okay = $(contents).writeToFileAtomicallyEncodingError($(path), true, $.NSUTF8StringEncoding, error);
    if (!okay) {
        throw new Error("Cannot save Homebrain settings or temporary session data.");
    }
    FS.setAttributesOfItemAtPathError($({NSFilePosixPermissions: 384}), $(path), null);
}

function remove(path) {
    if (exists(path)) {
        FS.removeItemAtPathError($(path), null);
    }
}

function privateDirectory(path) {
    var error = Ref();
    FS.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(
        $(path), true, $({NSFilePosixPermissions: 448}), error);
    var info = FS.attributesOfItemAtPathError($(path), error);
    var available = info && !info.isNil();
    var owner = available ? string(info.objectForKey("NSFileOwnerAccountName")) : "";
    if (!available || owner !== string($.NSUserName()) || string(info.objectForKey("NSFileType")) !== "NSFileTypeDirectory") {
        throw new Error("Homebrain's private state directory has an unexpected owner or file type.");
    }
    FS.setAttributesOfItemAtPathError($({NSFilePosixPermissions: 448}), $(path), error);
    return path;
}

function pump(seconds) {
    var deadline = $.NSDate.dateWithTimeIntervalSinceNow(seconds);
    if (HB.app) {
        var event = HB.app.nextEventMatchingMaskUntilDateInModeDequeue(
            $.NSEventMaskAny, deadline, $.NSDefaultRunLoopMode, true);
        if (event && !event.isNil()) {
            HB.app.sendEvent(event);
        }
        HB.app.updateWindows;
    } else {
        $.NSRunLoop.currentRunLoop.runUntilDate(deadline);
    }
}

function uid() {
    return String(string($.NSUserName())).replace(/[^A-Za-z0-9_-]/g, "_");
}

function resources(filename) {
    return HB.resources + "/" + filename;
}

function taskResult(task, out, err, limit) {
    var deadline = Date.now() + limit * 1000;
    while (task.running && Date.now() < deadline) {
        pump(0.05);
    }
    if (task.running) {
        task.terminate;
        throw new Error("Homebrain connection timed out. Check Wi-Fi, SSH destination and host authentication.");
    }
    var data = readText(out);
    if (data.length > 65536) {
        throw new Error("The Homebrain operation returned too much data.");
    }
    return {code: task.terminationStatus, output: data, error: readText(err).slice(0, 2000)};
}

function process(program, argv, input, timeout) {
    var prefix = HB.temporary + "/io-" + string($.NSUUID.UUID.UUIDString);
    var out = prefix + ".out";
    var err = prefix + ".err";
    writeText(out, "");
    writeText(err, "");
    var child = $.NSTask.alloc.init;
    var source = $.NSPipe.pipe;
    child.launchPath = $(program);
    child.arguments = $(argv);
    child.standardInput = source;
    child.standardOutput = $.NSFileHandle.fileHandleForWritingAtPath($(out));
    child.standardError = $.NSFileHandle.fileHandleForWritingAtPath($(err));
    var environment = ObjC.deepUnwrap($.NSProcessInfo.processInfo.environment);
    environment.SSH_ASKPASS = resources("ssh-askpass");
    environment.SSH_ASKPASS_REQUIRE = "prefer";
    environment.DISPLAY = environment.DISPLAY || "homebrain:0";
    child.environment = $(environment);
    try {
        child.launch;
        source.fileHandleForWriting.writeData($(input || "").dataUsingEncoding($.NSUTF8StringEncoding));
        source.fileHandleForWriting.closeFile;
        return taskResult(child, out, err, timeout || 15);
    } finally {
        child.standardOutput.closeFile;
        child.standardError.closeFile;
        remove(out);
        remove(err);
    }
}

function checkedProcess(program, argv, input, timeout) {
    var result = process(program, argv, input, timeout);
    if (result.code !== 0) {
        var detail = result.error.trim() || "The requested program exited with status " + result.code + ".";
        throw new Error(detail);
    }
    return result.output;
}

function jsonFile(path) {
    return JSON.parse(readText(path));
}
