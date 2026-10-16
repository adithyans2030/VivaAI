"use client";

import React, { useState } from "react";
import BrandLogo from "@/components/BrandLogo";
import ThemeToggle from "@/components/ThemeToggle";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import {
  ArrowRight,
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
} from "lucide-react";

export default function DesignSystemPage() {
  const [testInput, setTestInput] = useState("student@university.edu");

  return (
    <div className="min-h-screen bg-[var(--bg-surface)] text-[var(--text-primary)] px-6 py-12 transition-colors">
      <div className="max-w-6xl mx-auto space-y-16">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-8 border-b border-[var(--border-default)] gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-5 h-[1.5px] bg-[var(--text-secondary)]" />
              <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-secondary)]">
                Design System Specification
              </span>
            </div>
            <h1 className="font-editorial text-4xl sm:text-5xl font-normal mt-2 tracking-tight">
              VivaIQ Design Language
            </h1>
            <p className="text-sm text-[var(--text-secondary)] mt-2">
              Bespoke academic editorial identity adapted to voice examination and authenticity auditing.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-muted)]">Toggle Active Theme:</span>
            <ThemeToggle />
          </div>
        </div>

        {/* 1. Color Palette Tokens */}
        <section className="space-y-6">
          <div>
            <h2 className="font-editorial text-2xl font-normal">1. Color Palette & Surfaces</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Dual-theme tokens matching the calm celadon / midnight spruce reference aesthetic.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="p-4 rounded-2xl bg-[var(--bg-hero)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--bg-hero)] border border-[var(--border-default)] shadow-xs" />
              <div className="text-xs font-semibold">--bg-hero</div>
              <div className="text-[10px] text-[var(--text-muted)]">Left Brand Canvas</div>
            </div>

            <div className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-xs" />
              <div className="text-xs font-semibold">--bg-surface</div>
              <div className="text-[10px] text-[var(--text-muted)]">Right Page Canvas</div>
            </div>

            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-xs" />
              <div className="text-xs font-semibold">--bg-card</div>
              <div className="text-[10px] text-[var(--text-muted)]">Cards & Inputs</div>
            </div>

            <div className="p-4 rounded-2xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--bg-card-subtle)] border border-[var(--border-default)] shadow-xs" />
              <div className="text-xs font-semibold">--bg-card-subtle</div>
              <div className="text-[10px] text-[var(--text-muted)]">Hover & Wells</div>
            </div>

            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--accent-primary)] shadow-xs" />
              <div className="text-xs font-semibold">--accent-primary</div>
              <div className="text-[10px] text-[var(--text-muted)]">Pine / Mint Accent</div>
            </div>

            <div className="p-4 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-2">
              <div className="w-full h-12 rounded-xl bg-[var(--border-default)] shadow-xs" />
              <div className="text-xs font-semibold">--border-default</div>
              <div className="text-[10px] text-[var(--text-muted)]">Divider Rules</div>
            </div>
          </div>
        </section>

        {/* 2. Typography Scale */}
        <section className="space-y-6">
          <div>
            <h2 className="font-editorial text-2xl font-normal">2. Typography & Editorial Hierarchy</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              `Newsreader` serif paired with clean `Inter` sans.
            </p>
          </div>

          <div className="p-8 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-8">
            <div className="space-y-2 border-b border-[var(--border-default)] pb-6">
              <span className="text-[10px] uppercase font-semibold tracking-[0.18em] text-[var(--text-muted)] block">
                Display Headline (Serif + Italic)
              </span>
              <p className="font-editorial text-4xl sm:text-5xl font-normal leading-[1.1]">
                Make room for what they <em className="italic font-normal">understand.</em>
              </p>
            </div>

            <div className="space-y-2 border-b border-[var(--border-default)] pb-6">
              <span className="text-[10px] uppercase font-semibold tracking-[0.18em] text-[var(--text-muted)] block">
                Form Heading (Serif 34px)
              </span>
              <p className="font-editorial text-3xl font-normal">
                Sign in to VivaIQ
              </p>
            </div>

            <div className="space-y-2 border-b border-[var(--border-default)] pb-6">
              <span className="text-[10px] uppercase font-semibold tracking-[0.18em] text-[var(--text-muted)] block">
                Tracked Eyebrow (Sans 11px +0.18em tracking)
              </span>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
                FOR THE MOMENTS THAT MATTER
              </p>
            </div>

            <div className="space-y-2">
              <span className="text-[10px] uppercase font-semibold tracking-[0.18em] text-[var(--text-muted)] block">
                Body & Interface Copy (Sans 14px)
              </span>
              <p className="text-sm text-[var(--text-secondary)] max-w-xl leading-relaxed">
                A thoughtful viva experience for students, with a clear and reviewable record for teachers.
                Your assessment supports a conversation. It is advisory only, never a cheating detector or a final judgement.
              </p>
            </div>
          </div>
        </section>

        {/* 3. Component Library Showcase */}
        <section className="space-y-6">
          <div>
            <h2 className="font-editorial text-2xl font-normal">3. Core Component Library</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Reusable buttons, input fields, badges, and brand emblems.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Buttons Showcase */}
            <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-6">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Button Variants & States</h3>
              
              <div className="space-y-3">
                <Button variant="primary" className="w-full justify-between">
                  <span>Primary CTA (Continue)</span>
                  <ArrowRight className="w-4 h-4 ml-auto" />
                </Button>

                <Button variant="outline" className="w-full">
                  Fill teacher demo account (Outline)
                </Button>

                <Button variant="ghost" className="w-full">
                  Ghost Action (Cancel / Return)
                </Button>

                <div className="flex gap-3">
                  <Button variant="primary" size="sm">Small</Button>
                  <Button variant="primary" size="md">Medium</Button>
                  <Button variant="primary" size="lg">Large</Button>
                </div>

                <div className="flex gap-3">
                  <Button variant="primary" isLoading>Loading State</Button>
                  <Button variant="primary" disabled>Disabled State</Button>
                </div>
              </div>
            </div>

            {/* Inputs & Form States */}
            <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] space-y-6">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Input Fields</h3>

              <div className="space-y-4">
                <Input
                  label="Email address (Default State)"
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  placeholder="you@school.edu"
                />

                <Input
                  label="Password (With helper text)"
                  type="password"
                  value="••••••••••••"
                  placeholder="Enter your password"
                  helperText="Must be at least 8 characters."
                />

                <Input
                  label="Authentication Server Status (Error State)"
                  value="proxy-auth.school.edu"
                  error="HTTP 502 Bad Gateway"
                  readOnly
                />
              </div>
            </div>
          </div>
        </section>

        {/* 4. Badges & Advisory Indicators */}
        <section className="space-y-6">
          <div>
            <h2 className="font-editorial text-2xl font-normal">4. Badges & Advisory Indicators</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Ethical guardrails and status tags.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] flex flex-wrap gap-4 items-center">
            <Badge variant="default">Default Neutral</Badge>
            <Badge variant="success" icon={<CheckCircle2 className="w-3 h-3" />}>Authentic Spontaneous</Badge>
            <Badge variant="warning" icon={<AlertTriangle className="w-3 h-3" />}>Advisory Review</Badge>
            <Badge variant="error">High Overlap Flagged</Badge>
            <Badge variant="eyebrow">WELCOME BACK</Badge>
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4" />
              <span>Teacher-reviewed, always</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <Activity className="w-4 h-4" />
              <span>Service status operational</span>
            </div>
          </div>
        </section>

        {/* 5. Brand Logos in Different Sizes */}
        <section className="space-y-6">
          <div>
            <h2 className="font-editorial text-2xl font-normal">5. Brand Marks</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Unified logo emblem scaling across mobile, desktop, and headers.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-default)] flex flex-wrap gap-12 items-center">
            <div className="space-y-1">
              <span className="text-[10px] text-[var(--text-muted)] uppercase">Small</span>
              <BrandLogo size="sm" href="" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-[var(--text-muted)] uppercase">Medium</span>
              <BrandLogo size="md" href="" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-[var(--text-muted)] uppercase">Large</span>
              <BrandLogo size="lg" href="" />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
