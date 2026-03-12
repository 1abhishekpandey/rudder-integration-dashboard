Firebase — Version Mismatch Between Default Branch and CocoaPods

# The Issue

- Firebase iOS SDK (`firebase/firebase-ios-sdk`) frequently has a newer version on its `main` branch than the latest published CocoaPods release
- For example: `main` branch has `12.11.0` in `FirebaseAnalytics.podspec` line 3, but the latest CocoaPods release is `12.10.0`
- This causes a problem when generating vendor version links: if we always use the default branch (`blob/main/`), the `#L3` anchor points to a line showing `12.11.0` while the report text says `12.10.0`

# How the Tool Handles It

- The tool first tries to find the latest published version in the default branch file
- If the version isn't found (because `main` has moved ahead), it falls back to fetching the file at the version's git tag (e.g. `v12.10.0` or `12.10.0`)
- When a tag-based URL is used instead of the default branch, the report marks it with a `†` symbol for visibility
- This ensures the `#L` anchor always points to the correct line showing the actual published version

# Why Firebase Is Especially Affected

- Firebase uses a monorepo (`firebase-ios-sdk`) with frequent commits to `main`
- Version bumps happen on `main` before the CocoaPods release is published
- Other vendors (e.g. Braze, Adjust) typically keep their default branch in sync with the latest release, so this mismatch is less common
