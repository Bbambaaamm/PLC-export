Option Explicit
Dim shell, fso, root, varDir, cmd, rc

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
varDir = fso.BuildPath(root, "var")
If Not fso.FolderExists(varDir) Then
    fso.CreateFolder varDir
End If

shell.CurrentDirectory = root
cmd = "cmd.exe /d /c call start.bat --hidden --boot >> var\boot-startup.log 2>&1"
rc = shell.Run(cmd, 0, True)
WScript.Quit rc
