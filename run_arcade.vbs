Set shell = CreateObject("WScript.Shell")
scriptPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\arcade_carousel.py"
shell.Run "pythonw.exe """ & scriptPath & """", 0, False
