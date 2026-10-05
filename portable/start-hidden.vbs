Option Explicit
Dim shell, fso, root, varDir, cmd

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
varDir = fso.BuildPath(root, "var")
If Not fso.FolderExists(varDir) Then
    fso.CreateFolder varDir
End If

shell.CurrentDirectory = root
cmd = "cmd.exe /d /c call start.bat --hidden >> var\startup.log 2>&1"
shell.Run cmd, 0, False
