# WeUnix Kismet7

WeUnix is a local desktop operations console for account import, identity sync, preflight checks, rehearsal runs, task execution, diagnostics, and privacy-safe summaries.

![WeUnix dashboard](docs/assets/weunix-dashboard.png)

## Highlights

- Tauri + React + TypeScript desktop shell
- Python backend API and reusable core workflow modules
- Account import, sync, preflight, rehearsal, start/stop, logs, and diagnostics
- Privacy mode for masking sensitive account fields
- Local-only configuration by default
- Built-in documentation page and desktop-style microinteractions

## Repository Notes

This repository intentionally does not track:

- `grabber_config.json` and backup configs
- built `.exe`, `.msi`, `.zip`, and `dist/` artifacts
- local smoke-test output and Playwright screenshots
- commercial/system font files such as `PingFangSC-Medium.ttf`

Release binaries should be uploaded through GitHub Releases, not committed to Git.

## License

This project is open source under the [MIT License](LICENSE).

## Development

Install frontend dependencies:

```powershell
cd desktop/gui
npm install
```

Run the backend during development:

```powershell
cd E:\Weunix
py -3 desktop\backend_api.py
```

Run the desktop frontend shell:

```powershell
cd E:\Weunix\desktop\gui
npm run dev
```

## Build

Build the frontend:

```powershell
cd E:\Weunix\desktop\gui
npm run build
```

Build the backend executable when packaging the Tauri app:

```powershell
cd E:\Weunix
pyinstaller weunix_backend.spec
Copy-Item .\dist\weunix-backend.exe .\desktop\gui\src-tauri\resources\weunix-backend.exe -Force
```

Build the Windows desktop package:

```powershell
cd E:\Weunix\desktop\gui
npm run tauri:build
```

## Tests

```powershell
cd E:\Weunix
py -3 test_all.py
```

```powershell
cd E:\Weunix\desktop\gui
npm run build
```

## Privacy Checklist Before Release

- Confirm `grabber_config.json` is empty or absent.
- Confirm no personal account IDs, names, student numbers, or tokens are committed.
- Upload installer files to GitHub Releases instead of committing them.
- Keep privacy mode enabled by default when sharing screenshots.
