[Setup]
AppName=Professional Car AI Failure Prediction System
AppVersion=1.0.0
AppPublisher=Car AI Solutions
AppPublisherURL=https://example.com
DefaultDirName={{commonpf}}\CarAISystem
DefaultGroupName=Car AI System
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=CarAISystem_Setup
SetupIconFile=car_icon.ico
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "quicklaunchicon"; Description: "Create a &quick launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "CarAI_Installer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Car AI System"; Filename: "python"; Parameters: "{app}\main.py"; WorkingDir: "{app}"
Name: "{group}\Run Car AI System"; Filename: "{app}\run.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Car AI System"; Filename: "python"; Parameters: "{app}\main.py"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Uninstall Car AI System"; Filename: "{uninstallexe}"

[Run]
Filename: "python"; Parameters: "{app}\main.py"; Description: "Run Car AI System"; Flags: nowait postinstall skipifsilent
Filename: "cmd.exe"; Parameters: "/k pip install -r {app}\requirements.txt"; Description: "Install Python Dependencies"; Flags: waituntilterminated

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check if Python is installed
  if not RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.8\InstallPath') and
     not RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.9\InstallPath') and
     not RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.10\InstallPath') and
     not RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.11\InstallPath') then
  begin
    if MsgBox('Python 3.8 or newer is not detected. The application requires Python to be installed. Do you want to continue installation?', mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
