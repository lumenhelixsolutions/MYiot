# MYiot README + Launch Page + Brand Identity Design

## Status

Brainstorming complete. Awaiting implementation planning.

## Overview

Transform the MYiot repository into an award-winning, viral-ready, professionally marketed open-source project. The deliverables are:

1. A pro-marketed `README.md` with rich tooltips, badges, diagrams, and premium copy.
2. A cinematic GitHub Pages launch site at `docs/index.html` with a Three.js connected-home constellation hero.
3. A custom logo and mascot system based on the approved brand identity.
4. An updated `LICENSE` reflecting the non-commercial Creative Commons stance with a commercial-permission clause.

## Brand Identity (Approved)

The brand identity is defined by the reference asset at `1db0574d-1620-407f-b040-65cd503875c9.png` in the project root.

### Name & Pronunciation

- **Name:** MYiot
- **Pronunciation:** "My IoT"
- **Tagline candidates:**
  - "Secure. Smart. Connected."
  - "Premium home intelligence."
  - "Smarter homes. Better lives."
  - "One home. Infinite possibilities."

### Logo System

1. **Primary Logo** — The Connected Home Totem
   - A house silhouette constructed from stacked smart-device modules:
     - Thermostat (`23°`)
     - Light bulb
     - Camera
     - Smiling screen/lock module (the face)
     - Speaker/router
     - Smart hub base
   - Two WiFi/signal antennae on the roof.
   - Wordmark: "MYiot" with the "i" dot colored cyan.
   - Subtitle: "( My IoT )".

2. **Icon Mark / App Icon**
   - Simplified line-art version of the house-node for favicons, app icons, and small UI use.
   - Delivered at 16px, 32px, 64px, 1024px.
   - Rounded-square container with gradient stroke.

3. **Mascot — Full Version**
   - "Meet MY" — the friendly home intelligence companion.
   - 3D-style render of the totem with a smiling face.
   - Personality traits: Protects, Simplifies, Cares.

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| Deep Space Slate | `#0B1021` | Page backgrounds, dark surfaces |
| Electric Indigo | `#6366F1` | Primary brand color, links, accents |
| Cyan Glow | `#06B6D4` | Interactive glows, highlights, status dots |
| Warm Amber | `#F59E0B` | Warnings, secondary accents, warmth |
| White | `#FFFFFF` | Primary text on dark |
| Light Gray | `#E5E7EB` | Secondary text, borders |

### Typography

| Role | Font | Usage |
|------|------|-------|
| Display / Hero | Playfair Display (or similar editorial serif) | Large headlines, "Elevate Everyday." |
| UI / Body | Inter | Body text, navigation, cards |
| Code | JetBrains Mono | Terminal blocks, inline code, API snippets |

### Brand Phrases

- **Secure.** — Built with privacy and protection at the core.
- **Smart.** — Intelligent automation that adapts to your life.
- **Connected.** — Everything. Working together. Seamlessly.
- **Premium home intelligence.** — Designed for the way you live.

## README.md Design

### Goals

- Stop the scroll within 3 seconds.
- Make developers want to install immediately.
- Make investors/stakeholders see premium product quality.
- Make end users understand the value without reading code.

### Structure

1. **Hero Banner**
   - Centered mascot image ( Meet MY ).
   - Wordmark SVG.
   - Primary tagline: "Secure. Smart. Connected."
   - Secondary line: "One universal hub for every smart device in your home."
   - Shields/badges: GitHub stars, license, Python version, React, last commit.

2. **Value Proposition**
   - One sentence: "MYiot unifies lights, cameras, locks, thermostats, and sensors from any manufacturer behind a single local-first API and dashboard."

3. **Feature Grid (with tooltips)**
   - 🏠 Universal Device Engine — "One abstraction for 15+ manufacturers"
   - ⚡ Real-Time Sync — "WebSocket state push, not polling"
   - 🔒 Local-First Privacy — "Your data stays in your home"
   - 📹 WebRTC + MJPEG Streaming — "Low-latency camera feeds in the browser"
   - 🔌 Plugin Driver System — "Add new manufacturers without touching core code"
   - 🛡️ Encrypted Credentials — "Fernet-secured token storage"

4. **30-Second Quickstart**
   - Copy-paste terminal block for backend.
   - Copy-paste terminal block for frontend.
   - Link to full docs.

5. **Architecture Diagram**
   - Mermaid diagram showing: Frontend → FastAPI → Universal Device Engine → Plugin Drivers → Devices.
   - WebSocket arrow for real-time sync.

6. **Supported Devices Table**
   - Manufacturer, device types, protocol, status.

7. **Screenshots / GIFs**
   - Dashboard grid view.
   - Camera monitor with live feeds.
   - Device detail panel.

8. **License Callout**
   - Clear CC BY-NC 4.0 badge.
   - "Commercial use requires written permission. Contact us."

9. **Contributors & Roadmap**
   - How to contribute.
   - Upcoming milestones.
   - Support / Discord / email links.

### Tooltip Strategy

Use HTML `<abbr>` + GitHub markdown title syntax, plus `<details>` expanders for deeper context:

```markdown
- **Universal Device Engine** — One abstraction for 15+ manufacturers <sup>[?](#glossary-universal-device-engine)</sup>
```

A glossary section at the bottom provides the tooltip-like explanations.

## GitHub Pages Launch Site (`docs/index.html`)

### Goals

- Feel like a product launch page, not a repo README.
- Showcase the Three.js hero and premium visual design.
- Drive visitors to Star, Install, and Read Docs.

### Sections

1. **Navigation**
   - Sticky glassmorphism nav with logo, links (Features, Architecture, Install, Docs, GitHub).

2. **Hero**
   - Full-viewport dark gradient background (`#0B1021` to `#172033`).
   - Three.js canvas: floating smart-home devices (camera, bulb, thermostat, plug, lock) orbiting a central glowing house-node.
   - Glowing data threads connect devices to the hub.
   - Headline: "Elevate Everyday."
   - Subheadline: "Premium home intelligence. One hub. Every device."
   - CTA buttons: "Get Started" and "View on GitHub".

3. **Stats Bar**
   - 15+ manufacturers
   - Real-time WebSocket sync
   - Local-first & encrypted
   - Open source

4. **Problem / Solution**
   - Left: "Smart homes shouldn't be a collection of apps."
   - Right: "MYiot unifies them."

5. **Feature Showcase**
   - Three cards with icons, hover glow, and brief copy:
     - Universal Control
     - Real-Time Streaming
     - Privacy by Design

6. **Interactive Architecture**
   - SVG or lightweight Three.js diagram showing data flow.
   - Hover to reveal layers.

7. **Supported Devices Wall**
   - Grid of manufacturer/device icons (Hue, Nest, Ring, Wyze, Kasa, etc.).

8. **Install + Quickstart**
   - Terminal-style code blocks with copy buttons.
   - Tabs: Docker / Python / Source.

9. **Security & Trust**
   - Icons + copy for local-first, encrypted credentials, audit logging.

10. **Roadmap / FAQ**
    - Collapsible roadmap items.
    - FAQ with animated expanders.

11. **Footer**
    - Logo + tagline.
    - Links: GitHub, Docs, License, Contact.
    - "© 2026 MYiot. CC BY-NC 4.0. Commercial use by permission."

### Technical Stack

- HTML5 semantic markup.
- CSS custom properties matching the color palette.
- Three.js via CDN for the hero constellation.
- Vanilla JavaScript for interactions, scroll animations, and copy buttons.
- No build step required.
- Responsive down to 375px.
- `prefers-reduced-motion` support.

### GitHub Pages Configuration

- Source: `/docs` folder on `main` branch.
- Custom domain: optional (user can configure later).

## Asset Deliverables

| Asset | Path | Description |
|-------|------|-------------|
| Logo SVG | `docs/assets/logo.svg` | Primary wordmark + totem |
| Icon SVG | `docs/assets/icon.svg` | Simplified app icon |
| Mascot SVG | `docs/assets/mascot.svg` | Full "Meet MY" character |
| Favicon ICO/PNG | `docs/assets/favicon.ico` | 32x32 icon |
| Launch CSS | `docs/assets/css/launch.css` | Design system + animations |
| Three.js Scene | `docs/assets/js/constellation.js` | Hero 3D scene |
| Interactions | `docs/assets/js/launch.js` | Nav, copy, FAQ, scroll |
| Social Preview | `docs/assets/social-preview.png` | 1280x640 OpenGraph image |

## LICENSE Update

Replace the current `LICENSE` with a CC BY-NC 4.0 license plus a commercial-permission clause:

```
MYiot — Creative Commons Attribution-NonCommercial 4.0 International

You are free to:
  - Share — copy and redistribute the material
  - Adapt — remix, transform, and build upon the material

Under the following terms:
  - Attribution — You must give appropriate credit.
  - NonCommercial — You may not use the material for commercial purposes.

Commercial licensing is available. Contact: [email/website]
```

## README Tooltip / Glossary

A glossary section will explain domain terms inline:

- **Universal Device Engine** — Standardized state registry + actuation dispatcher that abstracts manufacturer APIs.
- **Plugin Driver System** — Manufacturer-specific drivers loaded dynamically.
- **State Registry** — In-memory event-driven store of all device states.
- **Actuation Dispatcher** — Routes commands to the correct protocol (REST, TCP, CoAP, SOAP, MQTT).

## Success Criteria

- [ ] README renders beautifully on GitHub mobile and desktop.
- [ ] `docs/index.html` loads on GitHub Pages with Three.js hero animating.
- [ ] All new assets are SVG-based and scale crisply.
- [ ] License file clearly communicates CC BY-NC + commercial clause.
- [ ] Page passes Lighthouse accessibility and performance audits with no critical errors.
- [ ] Site supports reduced motion and keyboard navigation.

## Out of Scope

- Multi-language translations (future phase).
- Video production (will use static screenshots/GIFs).
- Custom font hosting (use Google Fonts CDN).
- Backend functionality changes (this spec is documentation/marketing only).

## References

- Brand identity mockup: `1db0574d-1620-407f-b040-65cd503875c9.png`
- Existing project spec: `SPEC.md`
- Existing integration plan: `plan-backend-integration.md`
