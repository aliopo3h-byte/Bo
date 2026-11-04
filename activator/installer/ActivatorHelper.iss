#ifndef AppVersion
  #define AppVersion "1.3"
#endif
#define AppTitle "مساعد التفعيل"
#define ExeName "ActivatorHelper.exe"

[Setup]
AppId={{B7C2D1AA-4E1F-4B7B-9A55-3F0C9D6E2A11}
AppName=ActivatorHelper
AppVersion={#AppVersion}
AppPublisher=ActivatorHelper
DefaultDirName={localappdata}\Programs\ActivatorHelper
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..
OutputBaseFilename=ActivatorHelper-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#ExeName}
UninstallDisplayName={#AppTitle}
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut / إنشاء اختصار على سطح المكتب"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist_dir\ActivatorHelper\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppTitle}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppTitle}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Windows\SendTo\{#AppTitle}"; Filename: "{app}\{#ExeName}"

[Registry]
; ---- قائمة (فتح باستخدام) ----
Root: HKCU; Subkey: "Software\Classes\Applications\{#ExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppTitle}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\{#ExeName}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#ExeName},0"
Root: HKCU; Subkey: "Software\Classes\Applications\{#ExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#ExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Applications\{#ExeName}\SupportedTypes"; ValueType: string; ValueName: ".xlsx"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\{#ExeName}\SupportedTypes"; ValueType: string; ValueName: ".xlsm"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.xlsx\OpenWithList\{#ExeName}"; ValueType: none; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\.xlsm\OpenWithList\{#ExeName}"; ValueType: none; Flags: uninsdeletekey
; ---- بند مباشر في قائمة الزر الأيمن لملفات إكسل ----
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsx\shell\ActivatorHelper"; ValueType: string; ValueData: "فتح في {#AppTitle}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsx\shell\ActivatorHelper"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#ExeName}"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsx\shell\ActivatorHelper\command"; ValueType: string; ValueData: """{app}\{#ExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsm\shell\ActivatorHelper"; ValueType: string; ValueData: "فتح في {#AppTitle}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsm\shell\ActivatorHelper"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#ExeName}"
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.xlsm\shell\ActivatorHelper\command"; ValueType: string; ValueData: """{app}\{#ExeName}"" ""%1"""

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppTitle}"; Flags: nowait postinstall skipifsilent
