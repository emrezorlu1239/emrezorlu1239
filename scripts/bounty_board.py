"""Render the wanted poster and captain's log SVGs from live GitHub data.

Edit ALIAS, ABILITIES and VOYAGES below to change what the cards say.
Run with --demo to render locally without a token.

The bounty
----------
    B = 1,000 x sum over public repos r of  commits(r) x (1 + stars(r))

Every commit you author is worth 1,000 doubloons, multiplied by the number of
people who found that ship worth noticing: you, plus each stargazer. A project
with real users pulls the price up faster than a pile of unwatched commits.
"""
import argparse
import base64
import collections
import datetime as dt
import html
import json
import os
import random
from pathlib import Path
import urllib.request

LOGIN = 'emrezorlu1239'
NAME = 'EMRE ZORLU'
ALIAS = '"The AI Engineer"'
CRIME = 'Shipping models from notebook to production'
LAST_SEEN = 'Last sighted near Sakarya'
RATE = 1_000  # doubloons per commit, before the star multiplier

# Shown on the poster as "Known abilities" (10 fit nicely).
ABILITIES = ['Python', 'PyTorch', 'Transformers', 'FastAPI', 'PostgreSQL',
             'React', 'React Native', 'TypeScript', 'C++', 'C#']

# Captain's log: (title, description, status, repo name or None).
# When repo is set, the card shows how much of the bounty that ship earned.
# status: sailing | charting | refitting | docked
VOYAGES = [
    ('flywire-brain-sim', 'Simulating a fruit-fly brain from the FlyWire connectome', 'sailing', 'flywire-brain-sim'),
    ('mindful-support', 'Local support chatbot: Qwen3.5 + QLoRA + RAG', 'refitting', 'mindful-support'),
    ('HF Audio Course', 'Hunting the certificate of excellence, Units 4-7', 'sailing', None),
    ('Mycel', "Self-hosted chat where a friend's PC is the server", 'charting', None),
    ('Syllable tokenizer', 'A Turkish GPT that reads by syllable, not BPE', 'charting', None),
]
STATUS = {'sailing': ('#57c8ad', 'SAILING'), 'charting': ('#b5a1dc', 'CHARTING'),
          'refitting': ('#f2d28c', 'REFITTING'), 'docked': ('#90a9bb', 'DOCKED')}

ROOT = Path(__file__).resolve().parent.parent
SERIF = "Georgia,'Times New Roman',serif"
SANS = "'Segoe UI','DejaVu Sans',sans-serif"
MONO = "'Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
e = html.escape


# ---------------------------------------------------------------- data

def graphql(query, variables):
    req = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': query, 'variables': variables}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Content-Type': 'application/json', 'User-Agent': 'bounty-board'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get('errors'):
        raise RuntimeError('GitHub GraphQL error: ' + json.dumps(data['errors']))
    return data['data']['user']


def fetch_avatar(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'bounty-board'}), timeout=30) as r:
            mime = r.headers.get_content_type() or 'image/png'
            return f'data:{mime};base64,' + base64.b64encode(r.read()).decode()
    except Exception as exc:  # the poster still works with the silhouette
        print('Avatar unavailable, using silhouette:', exc)
        return None


def fetch(login):
    user = graphql('''query($login:String!){user(login:$login){id avatarUrl(size:400)
      contributionsCollection{contributionCalendar{totalContributions}}}}''', {'login': login})
    repos = graphql('''query($login:String!,$id:ID!){user(login:$login){
      repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
        totalCount nodes{name stargazerCount primaryLanguage{name color}
          defaultBranchRef{target{... on Commit{history(author:{id:$id}){totalCount}}}}}}}}''',
        {'login': login, 'id': user['id']})['repositories']
    ships = []
    for n in repos['nodes']:
        ref = n['defaultBranchRef']
        commits = ref['target']['history']['totalCount'] if ref and ref.get('target') else 0
        lang = n['primaryLanguage']
        ships.append({'name': n['name'], 'stars': n['stargazerCount'], 'commits': commits,
                      'lang': lang['name'] if lang else None,
                      'color': (lang['color'] if lang else None) or '#90a9bb'})
    return {'contributions': user['contributionsCollection']['contributionCalendar']['totalContributions'],
            'repos': repos['totalCount'], 'ships': ships, 'avatar': fetch_avatar(user['avatarUrl'])}


def demo(avatar_path=None):
    rows = [('flywire-brain-sim', 41, 0, 'Python', '#3572A5'), ('mindful-support', 63, 1, 'TypeScript', '#3178c6'),
            ('credit-score-app', 22, 0, 'Python', '#3572A5'), ('course-projects', 35, 0, 'Jupyter Notebook', '#DA5B0B'),
            ('SqlBus_Project', 9, 0, 'C#', '#178600'), ('CSharp-Calculator', 6, 0, 'C#', '#178600'),
            ('DeterminantCalculator', 4, 0, 'C++', '#f34b7d'), ('restorant-prototip2', 14, 0, 'JavaScript', '#f1e05a')]
    avatar = None
    if avatar_path:
        avatar = 'data:image/png;base64,' + base64.b64encode(Path(avatar_path).read_bytes()).decode()
    return {'contributions': 412, 'repos': 38, 'avatar': avatar,
            'ships': [{'name': n, 'commits': c, 'stars': s, 'lang': l, 'color': col} for n, c, s, l, col in rows]}


def appraise(stats):
    for ship in stats['ships']:
        ship['bounty'] = RATE * ship['commits'] * (1 + ship['stars'])
    total = sum(s['bounty'] for s in stats['ships'])
    langs = collections.Counter(s['lang'] for s in stats['ships'] if s['lang'])
    colors = {s['lang']: s['color'] for s in stats['ships'] if s['lang']}
    stats['bounty'] = total
    stats['commits'] = sum(s['commits'] for s in stats['ships'])
    stats['stars'] = sum(s['stars'] for s in stats['ships'])
    stats['top_ship'] = max(stats['ships'], key=lambda s: s['bounty'], default=None)
    stats['languages'] = [(n, c, colors[n]) for n, c in langs.most_common(6)]
    stats['by_name'] = {s['name']: s for s in stats['ships']}
    return stats


def short(n):
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'.replace('.0M', 'M')
    if n >= 1_000:
        return f'{n/1_000:.0f}K'
    return str(n)


# ---------------------------------------------------------------- art

def torn_edge(x0, y0, x1, y1, seed=7):
    rnd = random.Random(seed)
    pts = []
    def side(ax, ay, bx, by, n):
        for i in range(n):
            t = i / n
            jx = rnd.uniform(-2.5, 2.5) if ax == bx else 0
            jy = rnd.uniform(-2.5, 2.5) if ay == by else 0
            pts.append((ax + (bx - ax) * t + jx, ay + (by - ay) * t + jy))
    side(x0, y0, x1, y0, 40); side(x1, y0, x1, y1, 60)
    side(x1, y1, x0, y1, 40); side(x0, y1, x0, y0, 60)
    return 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts) + 'Z'


def reveal(begin, dur=.4):
    """Animate in after `begin` seconds, but stay visible where animation is unsupported."""
    total = begin + dur
    return f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{begin/total:.3f};1" dur="{total:.2f}s" fill="freeze"/>'


def silhouette(fx, fy, fw, fh):
    """Fallback portrait: a captain at a glowing laptop at sunset."""
    cx = fx + fw / 2
    return f'''  <rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="url(#sky)"/>
  <circle cx="{fx+fw-60}" cy="{fy+fh-80}" r="24" fill="#ffd38a" opacity=".9"/>
  <rect x="{fx}" y="{fy+fh-74}" width="{fw}" height="74" fill="url(#sea)"/>
  <g transform="translate({cx-210} {fy+fh-340})" fill="#1b1730">
   <path d="M132 350 Q142 316 178 300 L242 300 Q274 316 288 350 Z"/>
   <rect x="199" y="266" width="22" height="38"/><ellipse cx="210" cy="246" rx="23" ry="27"/>
   <g transform="translate(0 -12)"><path d="M186 238 Q186 210 210 208 Q234 210 234 238Z"/>
   <path d="M156 246 Q210 260 264 246 Q258 234 246 228 Q238 242 210 240 Q182 242 174 228 Q162 234 156 246Z"/></g>
   <path d="M174 316 L246 316 L252 330 L168 330Z" fill="#2a2440"/>
   <path d="M180 318 L240 318 L244 328 L176 328Z" fill="#f2d28c"><animate attributeName="opacity" values=".7;1;.75;1;.7" dur="2.6s" repeatCount="indefinite"/></path>
  </g>'''


def poster(stats, today):
    W, H = 420, 680
    FX, FY, FW, FH = 76, 124, 268, 256
    total = stats['bounty']
    top = stats['top_ship']
    fav = stats['languages'][0][0] if stats['languages'] else 'Python'
    paper = torn_edge(24, 26, 396, 658)
    if stats.get('avatar'):
        portrait = f'''  <image href="{stats['avatar']}" x="{FX}" y="{FY + (FH - FW) / 2 - 6}" width="{FW}" height="{FW + 12}" preserveAspectRatio="xMidYMid slice" filter="url(#aged)"/>
  <rect x="{FX}" y="{FY}" width="{FW}" height="{FH}" fill="url(#vignette)"/>'''
    else:
        portrait = silhouette(FX, FY, FW, FH)
    haul = (f'Biggest haul: {e(top["name"])} · {round(100 * top["bounty"] / total)}% of the bounty'
            if top and total else 'No haul yet. Set sail!')
    s = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Wanted: Emre Zorlu, The AI Engineer</title>
<desc id="d">Wanted poster. Bounty {total:,} doubloons = 1,000 x the sum over {len(stats['ships'])} public repositories of commits x (1 + stars); {stats['commits']} commits, {stats['stars']} stars. {haul}. Known abilities: {e(', '.join(ABILITIES))}.</desc>
<defs>
 <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4e3ba"/><stop offset="1" stop-color="#e1c38b"/></linearGradient>
 <radialGradient id="burn" cx=".5" cy=".5" r=".72"><stop offset=".62" stop-color="#7a4b22" stop-opacity="0"/><stop offset="1" stop-color="#6b3d17" stop-opacity=".55"/></radialGradient>
 <filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3"/><feColorMatrix values="0 0 0 0 .35  0 0 0 0 .22  0 0 0 0 .1  0 0 0 .22 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>
 <filter id="aged"><feColorMatrix type="matrix" values=".62 .42 .12 0 .02  .5 .5 .1 0 .01  .36 .34 .2 0 0  0 0 0 1 0"/></filter>
 <radialGradient id="vignette" cx=".5" cy=".45" r=".75"><stop offset=".55" stop-color="#3b2416" stop-opacity="0"/><stop offset="1" stop-color="#3b2416" stop-opacity=".5"/></radialGradient>
 <linearGradient id="sky" x2="0" y2="1"><stop offset="0" stop-color="#2b2350"/><stop offset=".55" stop-color="#8a5a8c"/><stop offset=".78" stop-color="#f2b46b"/></linearGradient>
 <linearGradient id="sea" x2="0" y2="1"><stop offset="0" stop-color="#2c5b6d"/><stop offset="1" stop-color="#132a3d"/></linearGradient>
 <radialGradient id="lantern" cx=".5" cy="0" r=".9"><stop offset="0" stop-color="#f2d28c" stop-opacity=".22"/><stop offset="1" stop-color="#f2d28c" stop-opacity="0"/></radialGradient>
 <clipPath id="frame"><rect x="{FX}" y="{FY}" width="{FW}" height="{FH}"/></clipPath>
 <linearGradient id="gleam" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff6d8" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
 <clipPath id="bountyclip"><text x="210" y="494" text-anchor="middle" font-family="{SERIF}" font-size="34" font-weight="700">{total:,}</text></clipPath>
</defs>
<rect width="{W}" height="{H}" rx="18" fill="#0f1b2b"/>
<rect width="{W}" height="{H}" rx="18" fill="url(#lantern)"/>
<g><animateTransform attributeName="transform" type="rotate" values="-0.7 210 14;0.7 210 14;-0.7 210 14" dur="7s" repeatCount="indefinite"/>
 <path d="{paper}" fill="#000" opacity=".35" transform="translate(4 6)"/>
 <path d="{paper}" fill="url(#paper)"/>
 <path d="{paper}" fill="url(#paper)" filter="url(#grain)"/>
 <path d="{paper}" fill="url(#burn)"/>
 <circle cx="210" cy="14" r="6" fill="#8b8f98" stroke="#2b2f38" stroke-width="2"/>
 <text x="210" y="102" text-anchor="middle" font-family="{SERIF}" font-size="68" font-weight="700" letter-spacing="5" fill="#3b2416">WANTED</text>
 <g clip-path="url(#frame)">
{portrait}
 </g>
 <rect x="{FX}" y="{FY}" width="{FW}" height="{FH}" fill="none" stroke="#3b2416" stroke-width="3"/>
 <rect x="{FX-6}" y="{FY-6}" width="{FW+12}" height="{FH+12}" fill="none" stroke="#3b2416" stroke-width="1" opacity=".6"/>
 <text x="210" y="424" text-anchor="middle" font-family="{SERIF}" font-size="34" font-weight="700" letter-spacing="3" fill="#3b2416">{e(NAME)}</text>
 <text x="210" y="447" text-anchor="middle" font-family="{SERIF}" font-size="15" font-style="italic" fill="#5c3b22">{e(ALIAS)}</text>
 <g transform="translate({210 - (len(f'{total:,}') * 10 + 26)} 482)"><circle r="11" fill="#d9a441" stroke="#7a5310" stroke-width="2"/><circle r="6" fill="none" stroke="#7a5310" stroke-width="1.2"/></g>
 <text x="210" y="494" text-anchor="middle" font-family="{SERIF}" font-size="34" font-weight="700" fill="#3b2416">{total:,}</text>
 <g clip-path="url(#bountyclip)"><rect x="0" y="462" width="60" height="40" fill="url(#gleam)" transform="skewX(-20)"><animate attributeName="x" values="0;0;600" keyTimes="0;.7;1" dur="5s" repeatCount="indefinite"/></rect></g>
 <text x="210" y="514" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="#5c3b22">B = 1,000 · Σ<tspan font-size="7.5" dy="2">repos</tspan><tspan dy="-2"> commits × (1 + ★)</tspan></text>
 <text x="210" y="530" text-anchor="middle" font-family="{SERIF}" font-size="10" font-style="italic" fill="#6b4a2c">{haul}</text>
 <line x1="60" y1="541" x2="360" y2="541" stroke="#3b2416" stroke-opacity=".35"/>
 <text x="210" y="558" text-anchor="middle" font-family="{SANS}" font-size="9.5" font-weight="700" letter-spacing="2.5" fill="#3b2416">KNOWN ABILITIES</text>''']
    cw, gap = 68, 4
    for i, name in enumerate(ABILITIES[:10]):
        row, col = divmod(i, 5)
        x = 210 - (5 * cw + 4 * gap) / 2 + col * (cw + gap)
        y = 567 + row * 26
        fs = 10 if len(name) <= 8 else 8.8
        s.append(f''' <g>{reveal(.3 + i * .12)}<rect x="{x:.1f}" y="{y}" width="{cw}" height="20" rx="4" fill="#3b2416" fill-opacity=".1" stroke="#3b2416" stroke-opacity=".45"/><text x="{x + cw/2:.1f}" y="{y + 13.6}" text-anchor="middle" font-family="{SANS}" font-size="{fs}" font-weight="600" fill="#3b2416">{e(name)}</text></g>''')
    s.append(f''' <text x="210" y="632" text-anchor="middle" font-family="{SANS}" font-size="9.5" fill="#5c3b22">{stats['contributions']} contributions · {stats['repos']} voyages · favourite weapon: {e(fav)}</text>
 <text x="210" y="646" text-anchor="middle" font-family="{SERIF}" font-size="9" font-style="italic" fill="#6b4a2c">Wanted for: {e(CRIME)} · {e(LAST_SEEN)}</text>
 <g transform="translate({FX+FW-4} {FY+18}) rotate(-14)" opacity=".9">
  <animate attributeName="opacity" values="0;0;.9" keyTimes="0;.86;1" dur="1.85s" fill="freeze"/>
  <animateTransform attributeName="transform" type="scale" values="1.8;1.8;1" keyTimes="0;.86;1" dur="1.85s" fill="freeze" additive="sum"/>
  <circle r="25" fill="#9b2c2c"/><circle r="20" fill="none" stroke="#e7b0a0" stroke-width="1.2" stroke-dasharray="3 2"/>
  <text y="5" text-anchor="middle" font-family="{SERIF}" font-size="15" font-weight="700" fill="#f6dccf">EZ</text></g>
</g>
<text x="{W-14}" y="{H-8}" text-anchor="end" font-family="{SANS}" font-size="8" fill="#6f899d">updated {today}</text>
</svg>''')
    return '\n'.join(s)


def log(stats, today):
    W, H = 560, 680
    s = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Captain's log</title>
<desc id="d">Current projects: {e('; '.join(f'{v[0]} ({v[2]})' for v in VOYAGES))}. Cargo manifest of primary languages across {stats['repos']} public repositories.</desc>
<defs><radialGradient id="glow" cx=".85" cy=".1" r=".8"><stop offset="0" stop-color="#b5a1dc" stop-opacity=".16"/><stop offset="1" stop-color="#b5a1dc" stop-opacity="0"/></radialGradient></defs>
<rect width="{W}" height="{H}" rx="18" fill="#0f1b2b"/><rect width="{W}" height="{H}" rx="18" fill="url(#glow)"/>
<g font-family="{SANS}">
 <text x="36" y="44" fill="#b5a1dc" font-size="11" font-weight="700" letter-spacing="3">CAPTAIN'S LOG</text>
 <text x="36" y="72" fill="#eef0fa" font-size="22" font-weight="600">Current voyages</text>
 <g transform="translate(500 56)">
  <circle r="26" fill="none" stroke="#2d4257" stroke-width="1.5"/><circle r="19" fill="none" stroke="#2d4257" stroke-dasharray="2 3"/>
  <g><animateTransform attributeName="transform" type="rotate" values="-25;20;-8;12;-25" dur="9s" repeatCount="indefinite"/>
   <path d="M0 -22 L5 0 L0 22 L-5 0Z" fill="#2d4257"/><path d="M0 -22 L5 0 L-5 0Z" fill="#e45455"/><circle r="2.5" fill="#f2d28c"/></g>
  <text y="-30" text-anchor="middle" fill="#6f899d" font-size="8">N</text></g>''']
    y0, step, ch = 104, 72, 60
    for i, (name, desc, status, repo) in enumerate(VOYAGES):
        y = y0 + i * step
        color, label = STATUS.get(status, STATUS['docked'])
        b = .3 + i * .45
        k = f'{b/(b+.5):.3f}'
        pw = len(label) * 7.2 + 16
        ship = stats['by_name'].get(repo) if repo else None
        loot = ''
        if ship and stats['bounty']:
            loot = (f'<text x="518" y="49" text-anchor="end" fill="#f2d28c" font-size="10.5" font-weight="600">'
                    f'{short(ship["bounty"])} <tspan fill="#90a9bb" font-weight="400">of the bounty</tspan></text>')
        s.append(f''' <g transform="translate(0 {y})">
  <animate attributeName="opacity" values="0;0;1" keyTimes="0;{k};1" dur="{b+.5:.2f}s" fill="freeze"/>
  <animateTransform attributeName="transform" type="translate" values="-12 {y};-12 {y};0 {y}" keyTimes="0;{k};1" dur="{b+.5:.2f}s" fill="freeze"/>
  <rect x="28" y="0" width="504" height="{ch}" rx="10" fill="#162638" stroke="#22374d"/>
  <rect x="28" y="0" width="4" height="{ch}" rx="2" fill="{color}"/>
  <text x="48" y="25" fill="#eef0fa" font-size="14.5" font-weight="600">{e(name)}</text>
  <text x="48" y="44" fill="#90a9bb" font-size="11.5">{e(desc)}</text>
  <rect x="{518-pw:.1f}" y="{12 if loot else 20}" width="{pw:.1f}" height="20" rx="10" fill="{color}" fill-opacity=".14" stroke="{color}" stroke-opacity=".5"/>
  <text x="{518-pw/2:.1f}" y="{25.5 if loot else 33.5}" text-anchor="middle" fill="{color}" font-size="9.5" font-weight="700" letter-spacing="1.2">{label}</text>
  {loot}
 </g>''')
    yc = y0 + len(VOYAGES) * step + 18
    total = sum(c for _, c, _ in stats['languages']) or 1
    s.append(f''' <line x1="36" y1="{yc-8}" x2="524" y2="{yc-8}" stroke="#22374d"/>
 <text x="36" y="{yc+14}" fill="#b5a1dc" font-size="11" font-weight="700" letter-spacing="3">CARGO MANIFEST</text>
 <text x="524" y="{yc+14}" text-anchor="end" fill="#6f899d" font-size="10.5">primary language across {stats['repos']} public repos</text>''')
    bar_y = yc + 28
    x = 36.0
    for i, (lang, count, color) in enumerate(stats['languages']):
        w = 488 * count / total
        b = 2.6 + i * .15
        s.append(f''' <rect x="{x:.1f}" y="{bar_y}" width="{max(w-2,1):.1f}" height="12" fill="{color}"><animate attributeName="width" values="0;0;{max(w-2,1):.1f}" keyTimes="0;{b/(b+.5):.3f};1" dur="{b+.5:.2f}s" fill="freeze"/></rect>''')
        x += w
    for i, (lang, count, color) in enumerate(stats['languages']):
        col, row = i % 3, i // 3
        lx, ly = 36 + col * 166, bar_y + 34 + row * 20
        s.append(f''' <circle cx="{lx+5}" cy="{ly-4}" r="4.5" fill="{color}"/><text x="{lx+16}" y="{ly}" fill="#c9d4e3" font-size="11.5">{e(lang)} <tspan fill="#6f899d">{count}</tspan></text>''')
    s.append(f''' <text x="36" y="{H-22}" fill="#6f899d" font-size="10">Course plotted {today} · fair winds <tspan fill="#b5a1dc">▌<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></tspan></text>
</g>
</svg>''')
    return '\n'.join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', action='store_true', help='render with sample data, no token needed')
    ap.add_argument('--avatar', help='with --demo: local image to use as the portrait')
    args = ap.parse_args()
    stats = appraise(demo(args.avatar) if args.demo else fetch(LOGIN))
    today = dt.date.today().isoformat()
    out = ROOT / 'assets'
    out.mkdir(exist_ok=True)
    (out / 'wanted-poster.svg').write_text(poster(stats, today), encoding='utf-8')
    (out / 'captains-log.svg').write_text(log(stats, today), encoding='utf-8')
    top = stats['top_ship']
    print(f"Bounty {stats['bounty']:,} from {stats['commits']} commits and {stats['stars']} stars; "
          f"top ship {top['name'] if top else '-'}")


if __name__ == '__main__':
    main()
