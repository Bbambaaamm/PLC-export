Option Explicit
Dim shell, fso, root, logDir, cmd

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
logDir = fso.BuildPath(root, "logs")
If Not fso.FolderExists(logDir) Then
    fso.CreateFolder logDir
End If

shell.CurrentDirectory = root
cmd = "cmd.exe /d /c call start.bat --hidden >> logs\desktop-commander.log 2>&1"
shell.Run cmd, 0, False
