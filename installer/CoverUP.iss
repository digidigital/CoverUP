; Inno Setup script for CoverUP PDF (Windows installer)
; Built in CI from the PyInstaller one-dir output (dist\CoverUP).
; The version can be overridden from the command line:
;   iscc /DMyAppVersion=0.5.0 installer\CoverUP.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.5.0"
#endif
#define MyAppName "CoverUP PDF"
#define MyAppPublisher "digidigital"
#define MyAppURL "https://coverup.digidigital.de"
#define MyAppExeName "CoverUP.exe"

[Setup]
AppId={{B7E3F1A2-5C4D-4E9B-9A1F-0C0FFEE05050}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\CoverUP
DefaultGroupName=CoverUP PDF
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
OutputDir=Output
OutputBaseFilename=CoverUP-{#MyAppVersion}-setup
SetupIconFile=..\CoverUP.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
LicenseFile=..\LICENSE
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller one-dir output: the .exe plus its _internal data folder.
Source: "..\dist\CoverUP\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\CoverUP PDF"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CoverUP PDF"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,CoverUP PDF}"; Flags: nowait postinstall skipifsilent
