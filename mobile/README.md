# AI-Enumerator Assistant — Mobile Client (Expo React Native)

This is the mobile application for the **AI-Enumerator Assistant**, built with **React Native with Expo** (Expo React Native), TypeScript, and React Navigation.

---

## 📱 Technology Stack

- **Framework:** React Native with Expo (`expo`)
- **Language:** TypeScript
- **Navigation:** React Navigation (Role-based: Authenticated User → Role Resolver → Deputy / Supervisor / Enumerator Navigators)
- **Local Database:** `expo-sqlite` (Offline-first repository model)
- **State Management:** Zustand
- **Secure Storage:** `expo-secure-store`
- **Location & Boundaries:** `expo-location`
- **Maps:** `react-native-maps`
- **Testing:** Jest + React Native Testing Library

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Start the Expo Development Server

To launch the Metro bundler with Expo:

```bash
npx expo start
```

### 3. Running the App

From the Expo CLI interface:
- **Physical Device:** Scan the displayed QR code with the **Expo Go** app on your Android device.
- **Android Emulator:** Press `a` in the terminal to launch on a running Android Virtual Device (AVD).
- **Web Preview:** Press `w` or run `npm run web` to preview the app in your desktop browser.

---

## 🧪 Testing

Run unit and component tests with Jest:

```bash
npm test
```

---

## 🏗️ Project Architecture

```text
mobile/
├── src/
│   ├── app/                      # Application entry & providers
│   ├── navigation/               # Role-based React Navigation
│   │   ├── AppNavigator.tsx      # Session subscriber & role router
│   │   └── dashboards.tsx        # Deputy, Supervisor, Enumerator layouts
│   ├── core/                     # Reusable services
│   │   ├── apiClient.ts          # REST client with auth headers
│   │   ├── secureStore.ts        # expo-secure-store wrapper
│   │   ├── sessionService.ts     # User session & state management
│   │   └── healthService.ts      # Backend connectivity check
│   ├── components/               # Reusable UI components
│   └── features/                 # Feature-specific modules
│       ├── authentication/       # LoginScreen & auth flow
│       ├── deputy/               # Village/Ward layout planning
│       ├── supervisor/           # Block assignment & monitoring
│       ├── enumerator/           # Household data entry & mapping
│       ├── maps/                 # react-native-maps integration
│       ├── gps/                  # expo-location boundary checks
│       ├── offline/              # expo-sqlite offline storage
│       └── sync/                 # Sync queue handlers
├── app.json                      # Expo manifest configuration
├── package.json                  # Dependencies & scripts
└── __tests__/                    # Test suites
```

---

## 🔒 Offline & Security Rules

1. **Role Resolution**: UI navigation is role-aware, while the backend FastAPI server acts as the authoritative security boundary.
2. **Offline-First**: All fieldwork operations are committed to `expo-sqlite` first, queued in a sync queue, and uploaded when connectivity is established.
3. **Secure Tokens**: Session tokens are encrypted in hardware-backed storage via `expo-secure-store`.

---

## 👥 Seeded Demo Accounts (for Fieldwork & Testing)

The backend database contains seeded roles ready for end-to-end testing with password `password123`:

| Username | Role | Assigned Scope / Test Scenario |
| :--- | :--- | :--- |
| `deputy` | Deputy Tahsildar | Administrative area review, layout generation, & approval for Arasur & Kaniyur |
| `supervisor` | Supervisor | Assigned to Arasur Village Layout (`HLB-001`, `HLB-002`, `HLB-003`) |
| `supervisor2` | Supervisor | Secondary supervisor account |
| `enumerator` | Primary Enumerator | Assigned to `HLB-001` (Arasur Block 1) — 18 completed, 3 revisits, pending |
| `enumerator2` | Primary Enumerator | Assigned to `HLB-002` (Arasur Block 2) — 35 completed |
| `enumerator3` | Available Enumerator | Unassigned (available for allocation to `HLB-003`) |
| `enumerator4` | Available Enumerator | Unassigned |

### API Configuration
By default, the mobile app dynamically auto-detects the backend IP from Expo's Metro host URI. You can explicitly override this by setting `EXPO_PUBLIC_API_URL=http://<YOUR_LAN_IP>:8000/api/v1` in `mobile/.env`.
