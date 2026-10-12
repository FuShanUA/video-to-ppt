on run
	set inputType to button returned of (display dialog "请选择输入类型" buttons {"图片文件夹", "视频文件", "取消"} default button "图片文件夹" cancel button "取消")
	if inputType is "图片文件夹" then
		set chosenItems to choose folder with prompt "请选择包含图片的文件夹" with multiple selections allowed
		open chosenItems
	else
		set chosenItems to choose file with prompt "请选择视频文件" with multiple selections allowed
		open chosenItems
	end if
end run

on open droppedItems
	set myPath to path to me
	set scriptPath to POSIX path of myPath & "Contents/Resources/make_ppt.py"
	set pythonFinderPath to POSIX path of myPath & "Contents/Resources/find_python.sh"
	set pythonPath to do shell script quoted form of pythonFinderPath
	set outputPaths to {}

	repeat with anItem in droppedItems
		set itemPath to POSIX path of anItem
		try
			set outputLine to do shell script quoted form of pythonPath & " " & quoted form of scriptPath & " " & quoted form of itemPath
			set firstLine to paragraph 1 of outputLine
			set end of outputPaths to firstLine
		on error errorMessage
			display dialog "生成失败：" & errorMessage buttons {"好"} default button 1 with icon stop
		end try
	end repeat

	if (count of outputPaths) > 0 then
		set AppleScript's text item delimiters to linefeed
		set outputText to outputPaths as text
		set AppleScript's text item delimiters to ""
		repeat with outputPath in outputPaths
			set outputFile to POSIX file outputPath
			tell application "Finder"
				activate
				reveal outputFile
			end tell
		end repeat
		display dialog "已生成：" & linefeed & outputText buttons {"好"} default button 1 with icon note
	end if
end open
