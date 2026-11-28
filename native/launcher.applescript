property openingWorkspace : false

on launchWorkspace()
    if openingWorkspace then return
    set openingWorkspace to true
    try
        set resourcesPath to POSIX path of (path to resource "headless.js")
        set resourceFolder to do shell script "/usr/bin/dirname " & quoted form of resourcesPath
        with timeout of 180 seconds
            do shell script "/usr/bin/osascript -l JavaScript " & quoted form of resourcesPath & " " & quoted form of resourceFolder
        end timeout
    on error errorMessage
        display alert "Homebrain could not open" message errorMessage as warning
    end try
    set openingWorkspace to false
end launchWorkspace

on run
    set openingWorkspace to false
    launchWorkspace()
end run

on reopen
    launchWorkspace()
end reopen

on idle
    if not openingWorkspace then
        try
            set resourcesPath to POSIX path of (path to resource "headless.js")
            set resourceFolder to do shell script "/usr/bin/dirname " & quoted form of resourcesPath
            with timeout of 45 seconds
                do shell script "/usr/bin/osascript -l JavaScript " & quoted form of resourcesPath & " " & quoted form of resourceFolder & " --reconnect"
            end timeout
        end try
    end if
    return 20
end idle
