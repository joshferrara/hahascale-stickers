# Haha Scale — iMessage Sticker Pack

This repository contains an iMessage sticker pack app and host Messages app target.

## Submission readiness (Feb 2026 modernization)

The project has been modernized for current App Store submission expectations:

- Deprecated `armv7` requirement removed from host `Info.plist`.
- Legacy `"iPhone Developer"` signing override removed from build settings.
- Host and extension versions aligned:
  - `MARKETING_VERSION = 1.3.0`
  - `CURRENT_PROJECT_VERSION = 2`
- Sticker assets normalized to a 300x300 canvas and kept below 500 KB.
- 1024x1024 marketing icon re-encoded without alpha channel.
- User-specific Xcode workspace data (`xcuserdata`) removed from version control.

> Note: App Store uploads beginning April 28, 2026 require current Apple toolchains
> (Xcode 26+ / SDK 26 family) in App Store Connect.

## Local validation

Run:

```bash
./scripts/validate_sticker_pack.py
```

The validator checks:

- JSON/plist parseability
- Deprecated project/plist settings
- Sticker existence, dimensions (300x300), and file size (<500 KB)
- Icon existence and dimension mapping from `Contents.json`
- No alpha channel in `main-1024.png`

## Final pre-submit checklist (in Xcode on macOS)

1. Open project with latest Xcode.
2. Confirm automatic signing / team for both targets.
3. Build and archive `StickerPackExtension` scheme.
4. Validate archive in Organizer.
5. Upload to App Store Connect and complete iMessage metadata/screenshots.
