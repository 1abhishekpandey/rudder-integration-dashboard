Firebase — Legacy SDK Research

Data collected: 2026-03-12

# Native Integration

| Platform | Rudder Integration | Rudder Integration Version | Build File | Vendor Version Range | Latest Vendor Version |
| --- | --- | --- | --- | --- | --- |
| Android | [rudder-integration-firebase-android](https://github.com/rudderlabs/rudder-integration-firebase-android) | [3.5.0](https://github.com/rudderlabs/rudder-integration-firebase-android/blob/master/package.json#L2) | [Gradle](https://mvnrepository.com/artifact/com.rudderstack.android.integration/firebase/3.5.0) | [33.16.0](https://github.com/rudderlabs/rudder-integration-firebase-android/blob/master/firebase/build.gradle#L35) | [🔴 34.10.0](https://firebase.google.com/support/release-notes/android) |
| iOS | [rudder-integration-firebase-ios](https://github.com/rudderlabs/rudder-integration-firebase-ios) | [3.8.1](https://github.com/rudderlabs/rudder-integration-firebase-ios/blob/master/package.json#L2) | [Podspec](https://github.com/CocoaPods/Specs/blob/master/Specs/6/6/5/Rudder-Firebase/3.8.1/Rudder-Firebase.podspec.json) | [\~&gt; 11.15.0](https://github.com/rudderlabs/rudder-integration-firebase-ios/blob/master/Rudder-Firebase.podspec#L6) | [🔴 12.10.0 †](https://github.com/firebase/firebase-ios-sdk/blob/12.10.0/FirebaseAnalytics.podspec#L3) |

† Version link points to a specific git tag because the default branch has a newer unreleased version.Run anthropics/claude-code-action@v1

Run oven-sh/setup-bun@3d267786b128fe76c2f16a390aa2448b815359f3

Downloading a new version of Bun: <https://github.com/oven-sh/bun/releases/download/bun-v1.3.6/bun-linux-x64.zip>

/usr/bin/unzip -o -q /home/runner/work/\_temp/[7f62aaed-b089-4780-9926-593e81e79d90.zip](http://7f62aaed-b089-4780-9926-593e81e79d90.zip)

/home/runner/.bun/bin/bun --revision

1.3.6+d530ed993

Run cd ${GITHUB_ACTION_PATH}

bun install v1.3.6 (d530ed99)

\+ @actions/core@1.11.1

\+ @actions/github@6.0.1

\+ @anthropic-ai/claude-agent-sdk@0.2.73

\+ @modelcontextprotocol/sdk@1.16.0

\+ @octokit/graphql@8.2.2

\+ @octokit/rest@21.1.1

\+ @octokit/webhooks-types@7.6.1

\+ node-fetch@3.3.2

\+ shell-quote@1.8.3

\+ zod@3.25.76

138 packages installed \[623.00ms\]

Run bun run ${GITHUB_ACTION_PATH}/src/entrypoints/run.ts

**Error:** Action failed with error: Unsupported event type: push

**Error:** Process completed with exit code 1.

Run bun run ${GITHUB_ACTION_PATH}/src/entrypoints/post-buffered-inline-comments.ts

No buffered inline comments

Run curl -L \\

  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current

                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0

{

  "message": "Bad credentials",

  "documentation_url": "<https://docs.github.com/rest>",

  "status": "401"

100   112    0   112    0     0   2873      0 --:--:-- --:--:-- --:--:--  2947

}

---

# React Native SDK

| Rudder RN Integration SDK | npm | Version | Underlying Android SDK Range | Underlying iOS SDK Range | Vendor RN SDK | npm | Version | Vendor Underlying Android SDK Range | Vendor Underlying iOS SDK Range |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [@rudderstack/rudder-integration-firebase-react-native](https://github.com/rudderlabs/rudder-sdk-react-native) | [npm](https://www.npmjs.com/package/@rudderstack/rudder-integration-firebase-react-native/v/2.2.0) | [2.2.0](https://github.com/rudderlabs/rudder-sdk-react-native/blob/master/libs/rudder-integration-firebase-react-native/package.json#L4) | [🟢 \[3.5.0,4.0)](https://github.com/rudderlabs/rudder-sdk-react-native/blob/master/libs/rudder-integration-firebase-react-native/android/build.gradle#L83) | [🟢 \~&gt; 3.8](https://github.com/rudderlabs/rudder-sdk-react-native/blob/master/libs/rudder-integration-firebase-react-native/rudder-integration-firebase-react-native.podspec#L23) | [@react-native-firebase/analytics](https://github.com/invertase/react-native-firebase) | [npm](https://www.npmjs.com/package/@react-native-firebase/analytics/v/23.8.6) | [23.8.6](https://github.com/invertase/react-native-firebase/blob/main/packages/analytics/package.json#L3) | [34.10.0](https://github.com/invertase/react-native-firebase/blob/main/packages/app/package.json#L117) | [12.10.0](https://github.com/invertase/react-native-firebase/blob/main/packages/app/package.json#L90) |

---