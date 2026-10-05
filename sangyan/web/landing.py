"""Editorial Landing Page for SANGYAN Investor Safety Platform.

Visual principles derived from denmu.com (minimal, grid-based, dark charcoal #090c10,
electric purple gradients, micro-borders, generous whitespace, off-white typography)
and trustsat.mpst.me (cryptographic authority, evidence provenance, post-quantum ML-DSA-65).
"""
from __future__ import annotations

from pathlib import Path

_DIST_INDEX = Path(__file__).resolve().parent.parent.parent / "web" / "dist" / "index.html"


def render_landing_page() -> str:
    """Generate the complete self-contained HTML for the SANGYAN Landing Page."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SANGYAN — Post-Quantum Investor Safety & Evidence Intelligence</title>
    <meta name="description" content="Autonomous, evidence-grounded intelligence platform for financial protection. Claim-deconstructed, statutory registry verified, and sealed with post-quantum ML-DSA-65 cryptography.">
    
    <!-- Modern Font Stack: Inter & JetBrains Mono -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --bg-base: #07090e;
            --bg-surface: #0c0f17;
            --bg-card: #111622;
            --bg-card-hover: #161c2b;
            --border-dim: rgba(255, 255, 255, 0.06);
            --border-subtle: rgba(255, 255, 255, 0.12);
            --border-focus: rgba(139, 92, 246, 0.5);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-purple: #8b5cf6;
            --accent-purple-glow: rgba(139, 92, 246, 0.25);
            --accent-violet: #7c3aed;
            --accent-indigo: #6366f1;
            --accent-cyan: #38bdf8;
            --status-contradicted: #ef4444;
            --status-supported: #10b981;
            --status-conflicting: #f59e0b;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
        }

        *, *::before, *::after {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html {
            scroll-behavior: smooth;
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: var(--font-sans);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
            line-height: 1.6;
        }

        /* Subtle Background Grid */
        .bg-grid-pattern {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
            background-size: 64px 64px;
            pointer-events: none;
            z-index: 1;
        }

        /* Grainient Shader Canvas Container */
        #grainient-canvas-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 900px;
            overflow: hidden;
            pointer-events: none;
            z-index: 0;
            opacity: 0.65;
            mask-image: linear-gradient(to bottom, rgba(0,0,0,1) 40%, rgba(0,0,0,0) 100%);
            -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,1) 40%, rgba(0,0,0,0) 100%);
        }

        #grainient-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }

        /* Film Grain Overlay */
        .film-grain {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            opacity: 0.04;
            z-index: 2;
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
        }

        /* Layout Container */
        .container {
            max-width: 1240px;
            margin: 0 auto;
            padding: 0 24px;
            position: relative;
            z-index: 3;
        }

        /* Fixed Minimal Navigation Bar */
        .navbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 72px;
            background: rgba(7, 9, 14, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border-dim);
            z-index: 100;
            display: flex;
            align-items: center;
        }

        .nav-inner {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: var(--text-primary);
        }

        .brand-logo-mark {
            width: 34px;
            height: 34px;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-indigo));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 800;
            font-size: 15px;
            font-family: var(--font-mono);
            box-shadow: 0 0 20px var(--accent-purple-glow);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .brand-text {
            display: flex;
            flex-direction: column;
        }

        .brand-title {
            font-weight: 800;
            font-size: 17px;
            letter-spacing: 0.05em;
            color: var(--text-primary);
            font-family: var(--font-mono);
        }

        .brand-subtitle {
            font-size: 10px;
            letter-spacing: 0.12em;
            color: var(--accent-purple);
            font-weight: 600;
            text-transform: uppercase;
        }

        .nav-links {
            display: flex;
            align-items: center;
            gap: 28px;
            list-style: none;
        }

        .nav-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            letter-spacing: 0.03em;
            transition: color 0.2s ease;
        }

        .nav-link:hover {
            color: var(--text-primary);
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 20px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 6px;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: var(--font-sans);
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-indigo));
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 4px 20px rgba(124, 58, 237, 0.35);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 24px rgba(124, 58, 237, 0.5);
            border-color: rgba(255, 255, 255, 0.4);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-primary);
            border: 1px solid var(--border-subtle);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.25);
            transform: translateY(-1px);
        }

        .btn-mono {
            font-family: var(--font-mono);
            font-size: 12px;
            letter-spacing: 0.05em;
        }

        /* Hero Section */
        .hero {
            padding-top: 160px;
            padding-bottom: 80px;
            position: relative;
        }

        .hero-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(139, 92, 246, 0.1);
            border: 1px solid rgba(139, 92, 246, 0.25);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 12px;
            font-family: var(--font-mono);
            color: var(--accent-purple);
            margin-bottom: 28px;
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--accent-purple);
            box-shadow: 0 0 10px var(--accent-purple);
            animation: pulse-ring 2s infinite cubic-bezier(0.45, 0, 0.55, 1);
        }

        @keyframes pulse-ring {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        .hero-title {
            font-size: 68px;
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -0.03em;
            color: var(--text-primary);
            margin-bottom: 24px;
            max-width: 900px;
        }

        .hero-title span {
            background: linear-gradient(135deg, #ffffff 40%, var(--accent-purple) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-desc {
            font-size: 19px;
            line-height: 1.6;
            color: var(--text-secondary);
            max-width: 780px;
            margin-bottom: 40px;
            font-weight: 400;
        }

        .hero-actions {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 16px;
            margin-bottom: 60px;
        }

        /* Hero Interactive Preview Card */
        .hero-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(139, 92, 246, 0.08);
            position: relative;
            overflow: hidden;
        }

        .hero-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-dim);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }

        .card-pill {
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-dim);
            color: var(--text-secondary);
        }

        .hero-card-body {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }

        @media (max-width: 860px) {
            .hero-card-body {
                grid-template-columns: 1fr;
            }
            .hero-title {
                font-size: 44px;
            }
        }

        .content-box {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border-dim);
            border-radius: 8px;
            padding: 16px;
            font-size: 13px;
            line-height: 1.6;
            color: #cbd5e1;
            font-family: var(--font-sans);
        }

        .content-highlight {
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            padding: 2px 6px;
            border-radius: 3px;
            border-bottom: 1px dashed #ef4444;
        }

        .claims-box {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .claim-item {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-dim);
            border-radius: 6px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: border-color 0.2s;
        }

        .claim-item:hover {
            border-color: var(--border-subtle);
        }

        .claim-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .claim-text {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-primary);
        }

        .claim-source {
            font-size: 11px;
            color: var(--text-muted);
            font-family: var(--font-mono);
        }

        .badge-status {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .badge-contradicted {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.35);
        }

        .badge-supported {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }

        .badge-conflicting {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.35);
        }

        .trust-seal-strip {
            margin-top: 18px;
            padding-top: 14px;
            border-top: 1px solid var(--border-dim);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-family: var(--font-mono);
            color: var(--text-muted);
        }

        .trust-verified-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #34d399;
            background: rgba(16, 185, 129, 0.1);
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid rgba(16, 185, 129, 0.25);
            font-weight: 600;
        }

        /* Metrics Grid Strip */
        .metrics-section {
            border-top: 1px solid var(--border-dim);
            border-bottom: 1px solid var(--border-dim);
            background: rgba(12, 15, 23, 0.6);
            backdrop-filter: blur(10px);
            padding: 40px 0;
            margin: 40px 0 80px 0;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 32px;
        }

        @media (max-width: 900px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 500px) {
            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }

        .metric-card {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .metric-val {
            font-size: 32px;
            font-weight: 800;
            font-family: var(--font-mono);
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }

        .metric-val span {
            color: var(--accent-purple);
        }

        .metric-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .metric-sub {
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.5;
        }

        /* Section Headers */
        .section-header {
            margin-bottom: 48px;
        }

        .section-tag {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--accent-purple);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 10px;
            display: block;
        }

        .section-title {
            font-size: 38px;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--text-primary);
            line-height: 1.15;
            margin-bottom: 16px;
        }

        .section-desc {
            font-size: 16px;
            color: var(--text-secondary);
            max-width: 680px;
            line-height: 1.6;
        }

        /* Problem Section Cards */
        .problem-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-bottom: 80px;
        }

        @media (max-width: 900px) {
            .problem-grid {
                grid-template-columns: 1fr;
            }
        }

        .card-editorial {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 10px;
            padding: 30px;
            position: relative;
            transition: all 0.25s ease;
        }

        .card-editorial:hover {
            border-color: var(--border-subtle);
            transform: translateY(-2px);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
        }

        .card-icon {
            width: 44px;
            height: 44px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-dim);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            margin-bottom: 20px;
        }

        .card-editorial h3 {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 12px;
            color: var(--text-primary);
        }

        .card-editorial p {
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        /* Three Modes Section */
        .modes-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-bottom: 80px;
        }

        @media (max-width: 900px) {
            .modes-grid {
                grid-template-columns: 1fr;
            }
        }

        .mode-card {
            background: linear-gradient(180deg, var(--bg-card) 0%, rgba(17, 22, 34, 0.4) 100%);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 32px;
            position: relative;
            overflow: hidden;
        }

        .mode-step {
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-purple);
            margin-bottom: 16px;
            display: inline-block;
        }

        .mode-card h3 {
            font-size: 22px;
            font-weight: 800;
            margin-bottom: 12px;
            letter-spacing: -0.01em;
        }

        .mode-card p {
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 20px;
        }

        .mode-features {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 13px;
            color: var(--text-primary);
        }

        .mode-features li {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .mode-features li::before {
            content: "✓";
            color: var(--accent-purple);
            font-weight: bold;
        }

        /* 10-Stage Pipeline Visualizer */
        .pipeline-track {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 80px;
            overflow-x: auto;
        }

        .pipeline-steps {
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-width: 960px;
            position: relative;
            padding: 10px 0;
        }

        .pipeline-connector {
            position: absolute;
            top: 24px;
            left: 30px;
            right: 30px;
            height: 2px;
            background: var(--border-subtle);
            z-index: 1;
        }

        .p-step {
            position: relative;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            width: 86px;
        }

        .p-circle {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: var(--bg-surface);
            border: 2px solid var(--accent-purple);
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 12px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 8px;
            box-shadow: 0 0 12px var(--accent-purple-glow);
        }

        .p-name {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
        }

        .p-desc {
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 2px;
        }

        /* Demo Cases Showcase */
        .demo-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-bottom: 80px;
        }

        @media (max-width: 960px) {
            .demo-grid {
                grid-template-columns: 1fr;
            }
        }

        .demo-card {
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 26px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 20px;
            transition: all 0.2s ease;
        }

        .demo-card:hover {
            border-color: var(--accent-purple);
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(139, 92, 246, 0.12);
        }

        .demo-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .demo-tag {
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--accent-cyan);
            font-weight: 600;
        }

        .demo-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            margin: 8px 0;
        }

        .demo-desc {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
        }

        /* Architecture Section */
        .arch-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin-bottom: 80px;
        }

        @media (max-width: 860px) {
            .arch-grid {
                grid-template-columns: 1fr;
            }
        }

        .arch-card {
            background: var(--bg-card);
            border: 1px solid var(--border-dim);
            border-radius: 10px;
            padding: 28px;
        }

        .arch-card h4 {
            font-family: var(--font-mono);
            font-size: 15px;
            color: var(--accent-purple);
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .arch-card p {
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        /* Editorial Footer */
        .footer {
            border-top: 1px solid var(--border-dim);
            padding: 60px 0 40px 0;
            background: #05070a;
            color: var(--text-muted);
            font-size: 13px;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 40px;
            margin-bottom: 40px;
        }

        @media (max-width: 860px) {
            .footer-grid {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media (max-width: 500px) {
            .footer-grid {
                grid-template-columns: 1fr;
            }
        }

        .footer-brand {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .footer-col h5 {
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
        }

        .footer-links {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .footer-links a {
            color: var(--text-muted);
            text-decoration: none;
            transition: color 0.2s;
        }

        .footer-links a:hover {
            color: var(--text-primary);
        }

        .footer-bottom {
            border-top: 1px solid var(--border-dim);
            padding-top: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
            #grainient-canvas-container {
                display: none;
            }
            body {
                background: radial-gradient(circle at 50% 20%, rgba(124, 58, 237, 0.2), transparent 70%), var(--bg-base);
            }
        }
    </style>
</head>
<body>
    <div class="bg-grid-pattern"></div>
    <div class="film-grain"></div>

    <!-- Animated Grainient Shader Canvas -->
    <div id="grainient-canvas-container">
        <canvas id="grainient-canvas"></canvas>
    </div>

    <!-- Navigation -->
    <nav class="navbar">
        <div class="container nav-inner">
            <a href="/" class="brand">
                <div class="brand-logo-mark">S</div>
                <div class="brand-text">
                    <span class="brand-title">SANGYAN</span>
                    <span class="brand-subtitle">Post-Quantum Investor Safety</span>
                </div>
            </a>

            <ul class="nav-links">
                <li><a href="#overview" class="nav-link">01 // OVERVIEW</a></li>
                <li><a href="#pipeline" class="nav-link">02 // PIPELINE</a></li>
                <li><a href="#demos" class="nav-link">03 // LIVE DEMOS</a></li>
                <li><a href="#architecture" class="nav-link">04 // ARCHITECTURE</a></li>
            </ul>

            <div class="nav-actions">
                <a href="/workbench" class="btn btn-primary btn-mono">LAUNCH WORKBENCH →</a>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main>
        <!-- Hero Section -->
        <section class="hero" id="overview">
            <div class="container">
                <div class="hero-eyebrow">
                    <span class="pulse-dot"></span>
                    <span>ML-DSA-65 POST-QUANTUM EVIDENCE SYSTEM // V0.7.0</span>
                </div>

                <h1 class="hero-title">
                    VERIFY BEFORE<br>
                    <span>YOU TRUST.</span>
                </h1>

                <p class="hero-desc">
                    The first autonomous, evidence-grounded intelligence platform for investor protection. 
                    SANGYAN decomposes deceptive financial solicitations into verifiable atomic claims, 
                    cross-references statutory institutional registries, reconstructs scam funnels, and 
                    seals every finding with post-quantum ML-DSA-65 tamper-evident cryptography.
                </p>

                <div class="hero-actions">
                    <a href="/workbench" class="btn btn-primary" style="padding: 14px 28px; font-size: 15px;">
                        <span>OPEN INVESTIGATION WORKBENCH</span>
                        <span>→</span>
                    </a>
                    <a href="/workbench?case=case_telegram_algo" class="btn btn-secondary" style="padding: 14px 24px; font-size: 14px;">
                        <span>⚡ RUN LIVE DEMO (TELEGRAM SCAM)</span>
                    </a>
                    <a href="#architecture" class="btn btn-secondary btn-mono">
                        <span>INSPECT SPECIFICATION</span>
                    </a>
                </div>

                <!-- Hero Interactive Preview Card -->
                <div class="hero-card">
                    <div class="hero-card-header">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="card-pill">LIVE RADAR // INPUT: TELEGRAM SOLICITATION #8492</span>
                            <span class="badge-status badge-contradicted">HIGH RISK DETECTED</span>
                        </div>
                        <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">
                            LATENCY: 42ms &bull; MODEL: ML-DSA-65 (FIPS 204)
                        </div>
                    </div>

                    <div class="hero-card-body">
                        <!-- Left: Raw Decomposed Message -->
                        <div>
                            <div style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">
                                Intercepted Solicitation Text
                            </div>
                            <div class="content-box">
                                "Exclusive VIP Algo Club! <span class="content-highlight">Guaranteed 70% monthly returns</span> on your capital using proprietary AI. Partnered with <span class="content-highlight">SEBI Regd RA INH000099999</span>. Send funds immediately via UPI to <span class="content-highlight">fastprofit24@paytm</span>. 3 slots remaining!"
                            </div>
                        </div>

                        <!-- Right: Evaluated Claims -->
                        <div class="claims-box">
                            <div style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px;">
                                Statutory Epistemic Adjudication
                            </div>

                            <div class="claim-item">
                                <div class="claim-header">
                                    <span class="claim-text">Claim: "Guaranteed 70% monthly returns"</span>
                                    <span class="badge-status badge-contradicted">CONTRADICTED</span>
                                </div>
                                <div class="claim-source">Source: SEBI PFUTP Regulations (Statutory Prohibition)</div>
                            </div>

                            <div class="claim-item">
                                <div class="claim-header">
                                    <span class="claim-text">Claim: "SEBI Regd RA INH000099999"</span>
                                    <span class="badge-status badge-contradicted">CONTRADICTED</span>
                                </div>
                                <div class="claim-source">Source: SEBI Intermediaries Registry (Forged License ID)</div>
                            </div>

                            <div class="claim-item">
                                <div class="claim-header">
                                    <span class="claim-text">Routing: Personal VPA fastprofit24@paytm</span>
                                    <span class="badge-status badge-conflicting">MULE PATTERN</span>
                                </div>
                                <div class="claim-source">Source: RBI / Cybercrime 1930 Payment Heuristics</div>
                            </div>
                        </div>
                    </div>

                    <div class="trust-seal-strip">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="trust-verified-pill">✓ POST-QUANTUM SEAL AUTHENTIC</span>
                            <span>SHA3-256: 4f98...e19a</span>
                        </div>
                        <div>FIPS 204 LATTICE SIGNATURE VALIDATED</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Metrics Strip -->
        <section class="metrics-section">
            <div class="container">
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-val">T0 <span>+</span> T1</div>
                        <div class="metric-label">Institutional Sources</div>
                        <div class="metric-sub">Direct authoritative registries: SEBI, RBI, MCA, NSE, and BSE.</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-val">ML-DSA<span>-65</span></div>
                        <div class="metric-label">Post-Quantum Cryptography</div>
                        <div class="metric-sub">FIPS 204 lattice digital signatures with PKCS#11 HSM isolation.</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-val">10 <span>STAGES</span></div>
                        <div class="metric-label">LangGraph Pipeline</div>
                        <div class="metric-sub">Durable checkpointing with real-time SSE stream delivery.</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-val">0 <span>%</span></div>
                        <div class="metric-label">Hallucinated Guidance</div>
                        <div class="metric-sub">Strict epistemic stances: Supported, Contradicted, or Conflicting.</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- The Problem -->
        <section class="container" style="margin-bottom: 100px;">
            <div class="section-header">
                <span class="section-tag">01 // The Deception Crisis</span>
                <h2 class="section-title">Financial deception has industrialized.<br>Black-box AI cannot be trusted to fight it.</h2>
                <p class="section-desc">
                    Modern investment scams exploit forged certificates, closed messaging groups, and fake trading dashboards. 
                    Traditional LLMs hallucinate or issue generic advice. SANGYAN provides court-ready evidentiary proof.
                </p>
            </div>

            <div class="problem-grid">
                <div class="card-editorial">
                    <div class="card-icon">🎭</div>
                    <h3>Credential Cloning</h3>
                    <p>
                        Fraudsters scrape real SEBI registration numbers, forge official regulatory certificates, 
                        and impersonate licensed Research Analysts to establish false authority.
                    </p>
                </div>

                <div class="card-editorial">
                    <div class="card-icon">⚡</div>
                    <h3>Black-Box AI Failure</h3>
                    <p>
                        Generic AI chatbots hallucinate regulatory facts, fail to verify statutory gazettes, 
                        and cannot generate cryptographically verifiable evidence chains.
                    </p>
                </div>

                <div class="card-editorial">
                    <div class="card-icon">🛡️</div>
                    <h3>Evidentiary Adjudication</h3>
                    <p>
                        SANGYAN validates assertions against immutable institutional snapshots, 
                        producing tamper-evident receipts compliant with Section 65B of the Indian Evidence Act.
                    </p>
                </div>
            </div>
        </section>

        <!-- Three Product Modes -->
        <section class="container" style="margin-bottom: 100px;">
            <div class="section-header">
                <span class="section-tag">02 // Operational Modes</span>
                <h2 class="section-title">Engineered for the full threat lifecycle.</h2>
                <p class="section-desc">
                    Whether triaging incoming social messages, auditing regulatory compliance, or filing statutory complaints, 
                    SANGYAN provides tailored workflows.
                </p>
            </div>

            <div class="modes-grid">
                <div class="mode-card">
                    <span class="mode-step">MODE 01</span>
                    <h3>CHECK</h3>
                    <p>Instant ingestion, claim decomposition, and heuristic risk scoring for suspicious text or URLs.</p>
                    <ul class="mode-features">
                        <li>Automated entity & UPI recognition</li>
                        <li>High-yield return contradiction checks</li>
                        <li>Real-time threat posture assessment</li>
                    </ul>
                </div>

                <div class="mode-card">
                    <span class="mode-step">MODE 02</span>
                    <h3>VERIFY</h3>
                    <p>Deep multi-tier institutional cross-referencing and knowledge graph correlation.</p>
                    <ul class="mode-features">
                        <li>SEBI & RBI caution list reconciliation</li>
                        <li>Cross-source conflict detection</li>
                        <li>12-stage scam lifecycle reconstruction</li>
                    </ul>
                </div>

                <div class="mode-card">
                    <span class="mode-step">MODE 03</span>
                    <h3>RESPOND</h3>
                    <p>Automated statutory grievance drafting with tamper-evident evidentiary packages.</p>
                    <ul class="mode-features">
                        <li>Pre-filled SEBI SCORES 2.0 filings</li>
                        <li>1930 Cybercrime evidence dossiers</li>
                        <li>ML-DSA-65 post-quantum audit seals</li>
                    </ul>
                </div>
            </div>
        </section>

        <!-- 10-Stage Pipeline -->
        <section class="container" id="pipeline" style="margin-bottom: 100px;">
            <div class="section-header">
                <span class="section-tag">03 // Autonomous Execution</span>
                <h2 class="section-title">The 10-Stage Investigation Pipeline</h2>
                <p class="section-desc">
                    Every investigation executes through a deterministic, transactional LangGraph state machine 
                    with live SSE telemetry and post-quantum trust sealing.
                </p>
            </div>

            <div class="pipeline-track">
                <div class="pipeline-steps">
                    <div class="pipeline-connector"></div>

                    <div class="p-step">
                        <div class="p-circle">1</div>
                        <div class="p-name">Intake</div>
                        <div class="p-desc">Ingest & Redact</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">2</div>
                        <div class="p-name">Intelligence</div>
                        <div class="p-desc">Entity Extract</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">3</div>
                        <div class="p-name">Verification</div>
                        <div class="p-desc">Registry Queries</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">4</div>
                        <div class="p-name">Correlation</div>
                        <div class="p-desc">Graph Linkage</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">5</div>
                        <div class="p-name">Scam Chain</div>
                        <div class="p-desc">12-Stage Model</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">6</div>
                        <div class="p-name">Guidance</div>
                        <div class="p-desc">Safety Actions</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">7</div>
                        <div class="p-name">Explanation</div>
                        <div class="p-desc">Plain Evidence</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">8</div>
                        <div class="p-name">Review Gate</div>
                        <div class="p-desc">HITL Audit</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">9</div>
                        <div class="p-name">Trust Seal</div>
                        <div class="p-desc">ML-DSA-65</div>
                    </div>

                    <div class="p-step">
                        <div class="p-circle">10</div>
                        <div class="p-name">Complete</div>
                        <div class="p-desc">SSE Closure</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Interactive Demo Walkthrough Showcase -->
        <section class="container" id="demos" style="margin-bottom: 100px;">
            <div class="section-header">
                <span class="section-tag">04 // Preloaded Walkthroughs</span>
                <h2 class="section-title">Inspect Live Case Studies</h2>
                <p class="section-desc">
                    Explore real-world financial deception archetypes analyzed by SANGYAN. 
                    Click to launch the active case directly in the interactive workbench.
                </p>
            </div>

            <div class="demo-grid">
                <!-- Case 1 -->
                <div class="demo-card">
                    <div>
                        <div class="demo-header">
                            <span class="demo-tag">CASE #01 &bull; TELEGRAM</span>
                            <span class="badge-status badge-contradicted">HIGH RISK</span>
                        </div>
                        <h3 class="demo-title">Telegram 500% Algo Yield</h3>
                        <p class="demo-desc">
                            Algorithmic trading scam promising 70% monthly returns, forging SEBI RA INH000099999, 
                            and routing deposits to a personal mule Paytm VPA.
                        </p>
                    </div>
                    <a href="/workbench?case=case_telegram_algo" class="btn btn-secondary btn-mono">
                        OPEN IN WORKBENCH →
                    </a>
                </div>

                <!-- Case 2 -->
                <div class="demo-card">
                    <div>
                        <div class="demo-header">
                            <span class="demo-tag">CASE #02 &bull; WHATSAPP</span>
                            <span class="badge-status badge-contradicted">HIGH RISK</span>
                        </div>
                        <h3 class="demo-title">Counterfeit Research Analyst</h3>
                        <p class="demo-desc">
                            WhatsApp VIP advisory group operating under a forged SEBI certificate using scraped registration 
                            details of an unrelated genuine practitioner.
                        </p>
                    </div>
                    <a href="/workbench?case=case_fake_sebi_ra" class="btn btn-secondary btn-mono">
                        OPEN IN WORKBENCH →
                    </a>
                </div>

                <!-- Case 3 -->
                <div class="demo-card">
                    <div>
                        <div class="demo-header">
                            <span class="demo-tag">CASE #03 &bull; OFFSHORE</span>
                            <span class="badge-status badge-contradicted">HIGH RISK</span>
                        </div>
                        <h3 class="demo-title">Pre-IPO Offshore Escrow Trap</h3>
                        <p class="demo-desc">
                            Fake pre-IPO allotment platform on the RBI Caution List demanding a 20% advance release tax 
                            under fraudulent claims of FEMA compliance.
                        </p>
                    </div>
                    <a href="/workbench?case=case_offshore_escrow" class="btn btn-secondary btn-mono">
                        OPEN IN WORKBENCH →
                    </a>
                </div>
            </div>
        </section>

        <!-- Architecture & Credibility -->
        <section class="container" id="architecture" style="margin-bottom: 120px;">
            <div class="section-header">
                <span class="section-tag">05 // System Engineering</span>
                <h2 class="section-title">Engineered for Zero-Trust & High Availability</h2>
                <p class="section-desc">
                    Built for production resilience, cryptographic integrity, and institutional auditability.
                </p>
            </div>

            <div class="arch-grid">
                <div class="arch-card">
                    <h4><span>⚡</span> Distributed Asynchronous Core</h4>
                    <p>
                        High-throughput task queue built on Redis Streams with consumer groups, atomic leases, 
                        exponential backoff with decorrelated jitter, and dead-letter quarantine isolation.
                    </p>
                </div>

                <div class="arch-card">
                    <h4><span>🛡️</span> Post-Quantum Cryptography (FIPS 204)</h4>
                    <p>
                        ML-DSA-65 (Module-Lattice Digital Signatures) implementation with PKCS#11 HSM integration, 
                        providing quantum-resistant authentication for every investigation receipt.
                    </p>
                </div>

                <div class="arch-card">
                    <h4><span>🔄</span> Active-Passive Disaster Recovery</h4>
                    <p>
                        Multi-region topology with epoch-based split-brain fencing, stale-region write rejection, 
                        and PostgreSQL physical streaming replication tooling.
                    </p>
                </div>

                <div class="arch-card">
                    <h4><span>📊</span> End-to-End Observability</h4>
                    <p>
                        W3C distributed trace correlation, low-cardinality Prometheus metrics, OpenTelemetry exporter, 
                        and real-time Server-Sent Events (SSE) streaming with sequence replay.
                    </p>
                </div>
            </div>

            <!-- Call to Action Banner -->
            <div style="background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(99, 102, 241, 0.15)); border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 12px; padding: 48px; text-align: center; position: relative; overflow: hidden;">
                <h3 style="font-size: 28px; font-weight: 800; margin-bottom: 14px;">Ready to test SANGYAN?</h3>
                <p style="font-size: 16px; color: var(--text-secondary); max-width: 600px; margin: 0 auto 28px auto;">
                    Launch the interactive investigation workbench to analyze custom text, inspect evidence graphs, and verify cryptographic receipts.
                </p>
                <a href="/workbench" class="btn btn-primary" style="padding: 14px 32px; font-size: 15px;">
                    LAUNCH INVESTIGATION WORKBENCH →
                </a>
            </div>
        </section>
    </main>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-brand">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="brand-logo-mark" style="width: 26px; height: 26px; font-size: 12px;">S</div>
                        <span style="font-weight: 800; font-family: var(--font-mono); color: var(--text-primary); font-size: 15px;">SANGYAN</span>
                    </div>
                    <p style="font-size: 12px; line-height: 1.6; max-width: 320px;">
                        Public-good investor safety platform: authoritative claim verification, evidence provenance, post-quantum trust receipts, and security hardening.
                    </p>
                </div>

                <div class="footer-col">
                    <h5>Platform</h5>
                    <ul class="footer-links">
                        <li><a href="/workbench">Workbench</a></li>
                        <li><a href="/workbench?case=case_telegram_algo">Demo Investigations</a></li>
                        <li><a href="/health">System Health</a></li>
                        <li><a href="/metrics">Prometheus Metrics</a></li>
                    </ul>
                </div>

                <div class="footer-col">
                    <h5>Institutional</h5>
                    <ul class="footer-links">
                        <li><a href="https://scores.sebi.gov.in" target="_blank" rel="noopener">SEBI SCORES 2.0</a></li>
                        <li><a href="https://cybercrime.gov.in" target="_blank" rel="noopener">1930 Cybercrime Portal</a></li>
                        <li><a href="https://sachet.rbi.org.in" target="_blank" rel="noopener">RBI Sachet</a></li>
                        <li><a href="https://www.mca.gov.in" target="_blank" rel="noopener">MCA Company Portal</a></li>
                    </ul>
                </div>

                <div class="footer-col">
                    <h5>Cryptography</h5>
                    <ul class="footer-links">
                        <li><span>ML-DSA-65 (FIPS 204)</span></li>
                        <li><span>SHA3-256 Digests</span></li>
                        <li><span>PKCS#11 HSM Module</span></li>
                        <li><span>Sec. 65B Admissible</span></li>
                    </ul>
                </div>
            </div>

            <div class="footer-bottom">
                <div>
                    &copy; 2026 SANGYAN Foundation &bull; Authored by PrathamKapoor &bull; Version 0.7.0
                </div>
                <div style="font-size: 11px; color: var(--text-muted);">
                    Evidentiary analysis tool &bull; Does not constitute financial or investment advice.
                </div>
            </div>
        </div>
    </footer>

    <!-- WebGL / Canvas Grainient Shader Script -->
    <script>
        (function() {
            // Check for reduced motion preference
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                return;
            }

            const canvas = document.getElementById('grainient-canvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            let width, height;
            let animationFrameId;
            let time = 0;

            function resize() {
                width = canvas.width = window.innerWidth;
                height = canvas.height = Math.min(900, window.innerHeight * 1.1);
            }

            window.addEventListener('resize', resize);
            resize();

            // Colors: Deep indigo, electric violet, purple, deep cyan
            const blobs = [
                { x: 0.25, y: 0.3, r: 0.45, color: 'rgba(124, 58, 237, 0.45)', speedX: 0.0004, speedY: 0.0005 },
                { x: 0.75, y: 0.4, r: 0.5, color: 'rgba(99, 102, 241, 0.4)', speedX: -0.0003, speedY: 0.0004 },
                { x: 0.5, y: 0.7, r: 0.4, color: 'rgba(139, 92, 246, 0.35)', speedX: 0.0005, speedY: -0.0003 },
                { x: 0.85, y: 0.2, r: 0.35, color: 'rgba(56, 189, 248, 0.25)', speedX: -0.0004, speedY: 0.0006 }
            ];

            function render() {
                time += 16;
                ctx.clearRect(0, 0, width, height);

                // Render drifting radial gradients
                blobs.forEach(blob => {
                    const cx = width * (blob.x + Math.sin(time * blob.speedX) * 0.18);
                    const cy = height * (blob.y + Math.cos(time * blob.speedY) * 0.15);
                    const radius = Math.max(width, height) * blob.r;

                    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
                    grad.addColorStop(0, blob.color);
                    grad.addColorStop(1, 'rgba(7, 9, 14, 0)');

                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
                    ctx.fill();
                });

                animationFrameId = requestAnimationFrame(render);
            }

            // Pause when off screen
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        if (!animationFrameId) render();
                    } else {
                        cancelAnimationFrame(animationFrameId);
                        animationFrameId = null;
                    }
                });
            });

            observer.observe(canvas);
            render();
        })();
    </script>
</body>
</html>
"""
