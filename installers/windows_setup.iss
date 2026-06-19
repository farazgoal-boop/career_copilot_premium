[Setup]
AppName=Career Copilot Premium
AppVersion=1.0.0
AppPublisher=Career Copilot
DefaultDirName={autopf}\Career Copilot Premium
DefaultGroupName=Career Copilot Premium
OutputDir=..\dist\installer
OutputBaseFilename=CareerCopilotPremium_Setup_v1.0.0
SetupIconFile=windows\assets\donkey_robot_bw.ico
UninstallDisplayIcon={app}\career-copilot.exe
Compression=lzma2
CompressionThreads=auto
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes
PrivilegesRequired=admin
UsePreviousAppDir=no
CloseApplications=yes
CloseApplicationsFilter=Career Copilot Premium.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{app}\_internal\data\cache"
Name: "{app}\_internal\data\user_profiles"

[Files]
; Exclude runtime-generated session/cache/profile artifacts to reduce long/deep paths
; and avoid extraction failures from stale or locked machine-specific files.
Source: "..\dist\windows-bundle\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "_internal\mobile_app\react_native\*,_internal\data\user_profiles\*,_internal\data\cache\session_store.db,_internal\data\cache\session_registry.json,_internal\data\cache\pairing_codes.json,_internal\data\cache\web_briefing_drafts.json,_internal\data\cache\audit_database.sqlite3,_internal\data\cache\audit_flask\*,data\user_profiles\*,data\cache\session_store.db,data\cache\session_registry.json,data\cache\pairing_codes.json,data\cache\web_briefing_drafts.json,data\cache\audit_database.sqlite3,data\cache\audit_flask\*"
Source: "windows\assets\user_manual.html"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\client_package\requirements\*"; DestDir: "{app}\docs\requirements"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\docs\USER_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\INSTALL.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "windows\assets\vc_redist.x64.exe"; DestDir: "{app}\installers"; Flags: ignoreversion; Check: VCRedistBundled

[Icons]
Name: "{group}\Career Copilot Premium"; Filename: "{app}\career-copilot.exe"
Name: "{commondesktop}\Career Copilot Premium"; Filename: "{app}\career-copilot.exe"

[Run]
Filename: "{app}\installers\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ Runtime (one-time)..."; Flags: waituntilterminated; Check: VCRedistBundled
Filename: "{app}\career-copilot.exe"; Description: "Launch Career Copilot Premium"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistBundled: Boolean;
begin
  Result := FileExists(ExpandConstant('{src}\windows\assets\vc_redist.x64.exe'));
end;
