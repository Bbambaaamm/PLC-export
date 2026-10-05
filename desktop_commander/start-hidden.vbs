Option Explicit
Dim shell, fso, root, logDir, logPath, previousPath, cmd

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
logDir = fso.BuildPath(root, "logs")
If Not fso.FolderExists(logDir) Then
    fso.CreateFolder logDir
End If

logPath = fso.BuildPath(logDir, "desktop-commander.log")
previousPath = fso.BuildPath(logDir, "desktop-commander.previous.log")

If fso.FileExists(previousPath) Then
    fso.DeleteFile previousPath, True
End If
If fso.FileExists(logPath) Then
    fso.MoveFile logPath, previousPath
End If

shell.CurrentDirectory = root
cmd = "cmd.exe /d /c call start.bat --hidden > logs\desktop-commander.log 2>&1"
shell.Run cmd, 0, False
