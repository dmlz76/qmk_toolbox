; Inno Setup script for the Windows installer of QMK Toolbox (Qt). Compiled by
; build-installer.py, which passes AppVersion, AppDir (the app PyInstaller
; built), IconFile and OutputDir; not meant to be compiled on its own.

#define AppName "QMK Toolbox (Qt)"
#define AppExeName "qmk-toolbox-qt.exe"
#define ProgId "QMKToolboxQt.Firmware"
#define Flashers "{app}\_internal\qmk_toolbox\flashers"

[Setup]
; Not the native app's AppId, so that the two install side by side.
AppId={{570A71E2-8326-4E39-B762-35C97D03C317}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=QMK
AppPublisherURL=https://qmk.fm
AppSupportURL=https://qmk.fm/toolbox
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=QMK-Toolbox-Qt-{#AppVersion}-x64-setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
; Program Files, the file types and the drivers all need administrator rights.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The oldest Windows that Qt 6 supports (10, version 1809).
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "drivers"; Description: "Install drivers for keyboard bootloaders (needed to flash most keyboards)"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An update replaces the whole app, so no files of the previous version are left behind.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Listed under "Open with" for .hex and .bin files, without becoming their default
; (the native QMK Toolbox, or whatever the user chose, stays the default).
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\SupportedTypes"; ValueType: string; ValueName: ".hex"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\SupportedTypes"; ValueType: string; ValueName: ".bin"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "Firmware file"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.hex\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.bin\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue
; qmk: links, unless another app (such as the native QMK Toolbox) already handles them.
Root: HKA; Subkey: "Software\Classes\qmk"; ValueType: string; ValueName: ""; ValueData: "URL:{#AppName}"; Flags: uninsdeletekey; Check: QmkLinksAreOurs
Root: HKA; Subkey: "Software\Classes\qmk"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Check: QmkLinksAreOurs
Root: HKA; Subkey: "Software\Classes\qmk\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Check: QmkLinksAreOurs
Root: HKA; Subkey: "Software\Classes\qmk\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Check: QmkLinksAreOurs

[Run]
; The native app's driver installer: WinUSB or libusb drivers for the bootloaders in drivers.txt.
Filename: "{#Flashers}\qmk_driver_installer.exe"; Parameters: "--all --force ""{#Flashers}\drivers.txt"""; WorkingDir: "{#Flashers}"; StatusMsg: "Installing drivers..."; Tasks: drivers; Flags: waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
var
  QmkLinksFree: Boolean;

{ Decided once, before anything is written: whether qmk: links are unhandled,
  or handled by this app (an earlier install of it). }
function InitializeSetup(): Boolean;
var
  Command: String;
begin
  if RegQueryStringValue(HKCR, 'qmk\shell\open\command', '', Command) then
    QmkLinksFree := Pos(LowerCase('{#AppExeName}'), LowerCase(Command)) > 0
  else
    QmkLinksFree := True;
  Result := True;
end;

function QmkLinksAreOurs(): Boolean;
begin
  Result := QmkLinksFree;
end;
