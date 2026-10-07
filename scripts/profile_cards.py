#!/usr/bin/env python3
"""Generate the stats and languages cards shown in the profile README.

Runs daily in GitHub Actions (.github/workflows/profile-cards.yml) with the
workflow's GITHUB_TOKEN and writes assets/stats.svg and assets/languages.svg,
so the README does not depend on third-party card services.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# Notebooks are mostly JSON and cell output, which drowns out the real code.
EXCLUDED_LANGUAGES = {"Jupyter Notebook"}
TOP_LANGUAGES = 6

FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
STYLE = f"""
    .title {{ font: 600 18px {FONT}; fill: #A78BFA; }}
    .label {{ font: 400 14px {FONT}; fill: #C9D1D9; }}
    .value {{ font: 700 14px {FONT}; fill: #FFFFFF; }}
    .small {{ font: 400 12px {FONT}; fill: #8B949E; }}
    .big {{ font: 800 26px {FONT}; fill: #FFFFFF; }}
    .row {{ animation: fadeIn .6s ease-out both; }}
    .ring {{ animation: draw 1.4s ease-out both; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateX(-8px); }} to {{ opacity: 1; transform: translateX(0); }} }}
    @keyframes draw {{ from {{ stroke-dashoffset: 301.6; }} to {{ stroke-dashoffset: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .row, .ring {{ animation: none; }} }}
"""

QUERY = """
query ($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
    pullRequests { totalCount }
    issues { totalCount }
  }
}
"""


def fetch(login, token):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    for error in body.get("errors", []):
        print(f"warning: {error.get('message')}", file=sys.stderr)
    user = (body.get("data") or {}).get("user")
    if not user:
        sys.exit("GitHub API returned no user data")
    return user


def short(number):
    if number is None:
        return "—"
    if number >= 1000:
        return f"{number / 1000:.1f}k".replace(".0k", "k")
    return str(number)


def card(width, height, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <style>{STYLE}  </style>
  <defs>
    <linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1A1B2E"/>
      <stop offset="1" stop-color="#14152A"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7F52FF"/>
      <stop offset="1" stop-color="#3178C6"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="url(#cardBg)" stroke="#7F52FF" stroke-opacity=".35"/>
{body}</svg>
"""


def stats_svg(rows, contributions):
    colors = ["#FBBF24", "#A78BFA", "#34D399", "#F472B6", "#60A5FA"]
    body = '  <text class="title" x="25" y="38">GitHub stats</text>\n'
    for i, (label, value) in enumerate(rows):
        y = 72 + i * 25
        body += (
            f'  <g class="row" style="animation-delay: {0.15 * (i + 1):.2f}s">'
            f'<circle cx="31" cy="{y - 5}" r="5" fill="{colors[i % len(colors)]}"/>'
            f'<text class="label" x="45" y="{y}">{escape(label)}:</text>'
            f'<text class="value" x="250" y="{y}">{escape(value)}</text></g>\n'
        )
    length = 301.6  # 2 * pi * r, matches the draw keyframes
    body += (
        f'  <circle cx="395" cy="112" r="48" fill="none" stroke="#FFFFFF" stroke-opacity=".08" stroke-width="9"/>\n'
        f'  <circle class="ring" cx="395" cy="112" r="48" fill="none" stroke="url(#accent)" stroke-width="9" '
        f'stroke-linecap="round" stroke-dasharray="{length}" transform="rotate(-90 395 112)"/>\n'
        f'  <text class="big" x="395" y="118" text-anchor="middle">{escape(contributions)}</text>\n'
        f'  <text class="small" x="395" y="182" text-anchor="middle">contributions in the last year</text>\n'
    )
    return card(495, 195, body)


def languages_svg(languages):
    body = '  <text class="title" x="25" y="38">Most used languages</text>\n'
    if not languages:
        body += '  <text class="small" x="25" y="80">Updating…</text>\n'
        return card(350, 195, body)
    body += '  <clipPath id="bar"><rect x="25" y="56" width="300" height="10" rx="5"/></clipPath>\n  <g clip-path="url(#bar)">'
    x = 25.0
    for _, color, share in languages:
        body += f'<rect x="{x:.2f}" y="56" width="{300 * share + 0.5:.2f}" height="10" fill="{color}"/>'
        x += 300 * share
    body += "</g>\n"
    for i, (name, color, share) in enumerate(languages):
        col, row = i % 2, i // 2
        cx, y = 25 + col * 155, 100 + row * 32
        body += (
            f'  <g class="row" style="animation-delay: {0.12 * (i + 1):.2f}s">'
            f'<circle cx="{cx + 5}" cy="{y - 5}" r="5" fill="{color}"/>'
            f'<text class="label" x="{cx + 16}" y="{y}">{escape(name)}</text>'
            f'<text class="small" x="{cx + 16}" y="{y + 15}">{share * 100:.1f}%</text></g>\n'
        )
    return card(350, 195, body)


def top_languages(repositories):
    sizes, colors = {}, {}
    for repo in repositories:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDED_LANGUAGES:
                continue
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8B949E"
    total = sum(sizes.values())
    ranked = sorted(sizes.items(), key=lambda item: item[1], reverse=True)[:TOP_LANGUAGES]
    shown = sum(size for _, size in ranked)
    # Shares are relative to the languages shown, so the bar is always full.
    return [(name, colors[name], size / shown) for name, size in ranked] if total else []


def main():
    user = fetch(os.environ.get("GITHUB_USER", "Fen1x678"), os.environ["GITHUB_TOKEN"])
    repositories = user["repositories"]["nodes"]
    contributions = user.get("contributionsCollection") or {}
    rows = [
        ("Total stars", short(sum(repo["stargazerCount"] for repo in repositories))),
        ("Commits (last year)", short(contributions.get("totalCommitContributions"))),
        ("Pull requests", short((user.get("pullRequests") or {}).get("totalCount"))),
        ("Issues", short((user.get("issues") or {}).get("totalCount"))),
        ("Public repositories", short(user["repositories"]["totalCount"])),
    ]
    total = (contributions.get("contributionCalendar") or {}).get("totalContributions")
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "stats.svg").write_text(stats_svg(rows, short(total)), encoding="utf-8")
    (ASSETS / "languages.svg").write_text(languages_svg(top_languages(repositories)), encoding="utf-8")
    print("cards updated")


if __name__ == "__main__":
    main()
