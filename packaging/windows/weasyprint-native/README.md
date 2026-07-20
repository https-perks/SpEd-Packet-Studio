# WeasyPrint Native Runtime

This folder contains the Windows native DLL runtime needed by WeasyPrint
inside the frozen backend sidecar. Release builds prefer
`packaging/windows/weasyprint-native/bin` before checking `WEASYPRINT_NATIVE_BIN`
or the system `PATH`.

Refresh this folder on a Windows build machine with:

```powershell
pnpm native:prepare
```

The prepare script copies DLLs from the installed GTK3 runtime while excluding
unused Cairo/TIFF DLLs that introduce missing optional image-codec dependencies.
The frozen sidecar self-test verifies that PDF generation works without a
system GTK install on the target machine.
