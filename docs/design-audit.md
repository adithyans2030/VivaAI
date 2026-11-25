# VivaIQ Reference Design Audit & Implementation Summary

## 1. Executive Summary & Design DNA

This audit formalizes the design system captured from the reference implementation of **VivaIQ** in both Light and Dark themes, as well as the implementation details applied across the entire VivaIQ frontend application.

The reference design moves away from generic developer-dashboard aesthetics in favor of a **calm, prestigious editorial academic identity** (combining the warmth and timeless elegance of an elite publishing house with modern SaaS precision).

### Key Stylistic Hallmarks
- **Split-Screen Editorial Layout**: The left half functions as an intellectual anchor—featuring high-contrast serif display typography (`Newsreader`), editorial italics, and an ambient concentric-ring wave motif. The right half is an unhurried, purposeful form and interaction surface.
- **Bi-Thematic Palette**:
  - **Light Mode**: Sage Mist (`#EAEFEB`), Warm Linen (`#FBFBF9`), and Deep Forest Pine (`#2D4F44`).
  - **Dark Mode**: Midnight Spruce (`#11211E`), Dark Forest Charcoal (`#182220`), and Luminous Mint Sage (`#6EA291`).
- **Typography Pairing**: High-contrast, literary display serif (`Newsreader` normal & italic) paired with a neutral, highly readable geometric sans (`Inter`).
- **Advisory & Ethical Micro-copy**: Grounded badges emphasizing *"Teacher-reviewed, always"* and *"Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement."*

---

## 2. Design Tokens

### 2.1 Color Palette

| Token Name | Light Theme Hex | Dark Theme Hex | Semantic Usage |
| :--- | :--- | :--- | :--- |
| `--bg-hero` | `#EAEFEB` | `#11211E` | Left branding/hero panel background |
| `--bg-surface` | `#FBFBF9` | `#182220` | Right pane & primary canvas |
| `--bg-card` | `#FFFFFF` | `#1F2B28` | Cards, input fields, container elevations |
| `--bg-card-subtle` | `#F3F6F3` | `#152220` | Subtle wells, table headers, hover surfaces |
| `--border-default` | `#E2E7E2` | `#283633` | Card borders, dividers, subtle separators |
| `--border-focus` | `#2D4F44` | `#6EA291` | Focused inputs, active borders |
| `--text-primary` | `#1A2421` | `#EDF3F0` | Main headlines, body copy, active labels |
| `--text-secondary` | `#52605B` | `#A3B5AE` | Subheadings, descriptors, form labels |
| `--text-muted` | `#7C8B85` | `#6C8078` | Placeholders, timestamps, disclaimers |
| `--accent-primary` | `#2D4F44` | `#6EA291` | Primary CTA buttons, active accents |
| `--accent-hover` | `#233E35` | `#7EB0A0` | Button hover states |
| `--accent-contrast` | `#FFFFFF` | `#0D1C18` | Text on top of accent primary |
| `--ring-stroke` | `rgba(45, 79, 68, 0.12)` | `rgba(110, 162, 145, 0.18)` | Ambient concentric circles motif |
| `--ring-fill` | `rgba(45, 79, 68, 0.05)` | `rgba(110, 162, 145, 0.07)` | Concentric circle shaded ring |
| `--logo-bg` | `#2D4F44` | `#6EA291` | Brand icon background |
| `--logo-fg` | `#FFFFFF` | `#11211E` | Brand icon letter "v" |
| `--error-bg` | `#FDF2F2` | `#261818` | Alert / error containers |
| `--error-text` | `#B91C1C` | `#F87171` | Alert / error messages (e.g. 502 Bad Gateway) |
| `--error-border` | `#FCA5A5` | `#4D2424` | Alert container borders |

---

## 3. Typography Scale & Families

### 3.1 Families
- **Display Serif**: `Newsreader` (weights 300, 400, 500, 600, styles normal & italic).
- **Body & Interface Sans**: `Inter` (weights 400, 500, 600, 700).

### 3.2 Hierarchy Scale

| Role | Font Family | Size | Weight | Line Height | Letter Spacing | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Eyebrow / Tracked** | Sans | 11px / 0.6875rem | 600 (Semibold) | 1.2 | +0.15em (Wide) | `FOR THE MOMENTS THAT MATTER` |
| **Hero Title** | Serif | 48px – 56px | 400 (Regular) | 1.08 | -0.02em | `Make room for what they...` |
| **Hero Title Italic**| Serif | 48px – 56px | 400 (Italic) | 1.08 | -0.02em | `understand.` |
| **Form Heading** | Serif | 30px – 34px | 400 (Regular) | 1.15 | -0.015em | `Sign in to VivaIQ` |
| **Card / Section Title**| Serif | 20px – 24px | 400 (Regular) | 1.25 | -0.01em | `Examiner Review & Oversight` |
| **Body Primary** | Sans | 14px – 15px | 400 (Regular) | 1.55 | Normal | `A thoughtful viva experience...` |
| **Labels & Form Titles**| Sans | 13px – 14px | 500 (Medium) | 1.3 | Normal | `Email address`, `Password` |
| **Footnote / Meta** | Sans | 12px – 13px | 400 (Regular) | 1.45 | Normal | `Teacher-reviewed, always` |

---

## 4. Spacing, Radii & Layout Structure

- **Split-Screen Ratio**: 50% left hero / 50% right interface on desktop (`lg:grid-cols-2`), full width stacked on mobile.
- **Card Radii**:
  - Inputs & Buttons: `rounded-xl` (`12px` / `0.75rem`).
  - Cards & Floating Panels: `rounded-2xl` (`16px` / `1rem`) and `rounded-3xl` (`24px` / `1.5rem`).
  - Brand Avatar: `rounded-xl` (`12px`) with letter centered.
- **Form Container**: Centered column, max width `420px`, padded with `space-y-4` and `space-y-6`.
- **Dividers**: Thin `1px` subtle rules (`border-default`).
- **Rings / Wave Ambient Graphic**: Positioned in the bottom right of the left hero pane via `.ambient-rings` CSS class, rendering 3 nested concentric stroke circles with an inner circular medallion.

---

## 5. Component Inventory & States

### 5.1 Buttons (`components/ui/Button.tsx`)
- **Primary CTA (`Button variant="primary"`)**:
  - Light: Solid Forest Pine (`#2D4F44`), white text, bold, right arrow `→`.
  - Dark: Solid Mint Sage (`#6EA291`), dark spruce text (`#0D1C18`), bold.
  - States: default, hover (slight brightness shift), active (scale 0.99), disabled (opacity 50%), loading (spinner).
- **Secondary / Demo Pill (`Button variant="outline"`)**:
  - Light: White surface with `#E2E7E2` border, dark text.
  - Dark: Charcoal pine surface (`#1F2B28`) with `#283633` border, white text.
  - Label: *"Fill teacher demo account"*, *"Fill student demo account"*.

### 5.2 Inputs (`components/ui/Input.tsx`)
- High-profile rounded rectangle inputs with subtle border, soft transition on focus (`ring-1 ring-[var(--border-focus)] border-[var(--border-focus)]`).
- Label and error state support.

### 5.3 Badges & Advisory Indicators (`components/ui/Badge.tsx`)
- Variants: `default`, `success`, `warning`, `error`, `eyebrow`, `advisory`.
- Explicit ethical guardrails rendered across all views.

---

## 6. Page Inventory & VivaIQ Screen Mapping

| Page Route | Description | Implementation Status |
| :--- | :--- | :--- |
| `/login` | **Exact 1:1 match** to reference screenshots: 50/50 split-screen layout, Newsreader serif headline with italicized *"understand."*, ambient wave rings, live one-click demo credentials autofill, theme toggle, and ethical advisory footer. | Completed & Verified |
| `/` | Landing page featuring editorial hero, ambient wave motif, interactive Audio Orb showcase, 3 feature pillars, and links to student/teacher workflows. | Completed & Verified |
| `/student` | Student Viva portal with course selection, interactive microphone check modal (with audio meter and consent recording), live viva room with Audio Orb, turn-by-turn question cards, and transcript feeds. | Completed & Verified |
| `/teacher` | Teacher dashboard featuring oral viva session roster, candidate search & authenticity filtering, 6-signal acoustic & textual diagnostic breakdown, spoken transcripts, teacher notes editor, grade/flag override modal, course material (RAG) manager, and cohort analytics. | Completed & Verified |
| `/design-system` | Interactive living design system showcase displaying palette swatches, typography hierarchy, button states, inputs, badges, and brand marks side-by-side in both Light and Dark themes. | Completed & Verified |

---

## 7. Verification & Visual Parity Checklist

- [x] **Light Mode & Dark Mode Themes**: Supported seamlessly via `ThemeProvider` and CSS variables (`:root` and `.dark`), persistent across page refreshes.
- [x] **Typography Fidelity**: Google Font `Newsreader` (weights 300-600, roman and italic) and `Inter` loaded from Google Fonts in `frontend/index.html`.
- [x] **Ambient Concentric Rings**: Implemented via `.ambient-rings` CSS utility on the hero section.
- [x] **Advisory Guardrails**: All pages explicitly display the non-punitive notice: *"Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement."*
- [x] **Responsive Breakpoints**: Desktop 50/50 split cleanly collapses into vertical stacked views on tablet and mobile viewports.
