Option Explicit
Dim fso, wshShell, currentDir, exePath
Set fso = CreateObject("Scripting.FileSystemObject")
Set wshShell = CreateObject("WScript.Shell")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = fso.BuildPath(currentDir, "dist\PDF TOOL\PDF TOOL.exe")

' Change working directory to where the exe is so it finds its DLLs properly if it needs to
wshShell.CurrentDirectory = fso.GetParentFolderName(exePath)

If fso.FileExists(exePath) Then
    ' Run the application normally (1) since it's already a windowed exe with no console
    wshShell.Run """" & exePath & """", 1, False
Else
    MsgBox "Could not find the compiled application at: " & exePath & vbCrLf & "Please run the PyInstaller build first.", 16, "Error"
    WScript.Quit 1
End If
