/* Browser handoff uses a private, short-lived POST form and an existing tab. */
function browserMatches(url, local, file) {
    return typeof url === "string" && (url.indexOf(local + "/") === 0 || url === file);
}

function existingTab(application, local, file) {
    var found = null;
    application.windows().forEach(function (window) {
        window.tabs().forEach(function (tab, index) {
            if (!found && browserMatches(tab.url(), local, file)) {
                found = {window: window, tab: tab, index: index};
            }
        });
    });
    return found;
}

function openBrowser(fileURL, local) {
    var id = HB.settings.browser_bundle_id;
    var application = Application(id);
    try {
        var existing = existingTab(application, local, fileURL);
        if (existing) {
            existing.tab.url = fileURL;
            if (id === "com.apple.Safari") {
                existing.window.currentTab = existing.tab;
            } else {
                existing.window.activeTabIndex = existing.index + 1;
            }
            existing.window.index = 1;
            application.activate();
        } else {
            checkedProcess("/usr/bin/open", ["-b", id, fileURL], "", 5);
        }
    } catch (error) {
        throw browserFailure(error);
    }
}

function openAuthenticatedBrowser() {
    prepareBrowser();
    var ticket = HomebrainCore.handoff(remote("handoff"));
    var origin = HomebrainCore.localOrigin(HB.settings);
    var file = HB.state + "/open-workspace.html";
    writeText(file, HomebrainCore.form(origin, HB.deployment, ticket));
    HB.deleteFormAt = Date.now() + Math.min(ticket.expires_in_s, 30) * 1000;
    var url = string($.NSURL.fileURLWithPath($(file)).absoluteString);
    openBrowser(url, origin);
}

function removeExpiredForm() {
    if (HB.deleteFormAt && Date.now() > HB.deleteFormAt) {
        remove(HB.state + "/open-workspace.html");
        HB.deleteFormAt = 0;
    }
}

function browserSupport() {
    if (installedBrowsers().indexOf(HB.settings.browser_bundle_id) === -1) {
        throw new Error("The saved browser is not installed. Choose an installed browser in Connection Settings.");
    }
    var supported = HB.deployment.browsers || [];
    var found = supported.some(function (browser) {
        return browser.bundle_id === HB.settings.browser_bundle_id;
    });
    if (!found) {
        throw new Error("This deployment has not declared your selected browser as supported. Choose a declared browser in Connection Settings.");
    }
}

function browserFailure(error) {
    var detail = String(error.message || error);
    if (error.errorNumber === -1743 || /not authorized|not permitted/i.test(detail)) {
        return new Error("Allow Homebrain to automate your chosen browser in macOS Privacy & Security > Automation, then open Homebrain again.");
    }
    return new Error("The chosen browser could not open Homebrain. " + detail.slice(0, 500));
}

function prepareBrowser() {
    try {
        Application(HB.settings.browser_bundle_id).windows();
    } catch (error) {
        throw browserFailure(error);
    }
}
