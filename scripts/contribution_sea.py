"""Render a self-contained animated SVG from the real GitHub contribution calendar."""
import argparse
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import urllib.request

LEVELS = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2,
          'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
COLORS = ['#182c40', '#286b72', '#32958f', '#57c8ad', '#b5efd0']

def fetch_calendar(login):
    query = '''query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{
        contributionCount contributionLevel date weekday}}}}}}'''
    req = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': query, 'variables': {'login': login}}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Content-Type': 'application/json', 'User-Agent': 'contribution-sea'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if data.get('errors'):
        raise RuntimeError('GitHub GraphQL error: ' + json.dumps(data['errors']))
    return data['data']['user']['contributionsCollection']['contributionCalendar']

def render(calendar, login):
    weeks = calendar['weeks']
    if not weeks or not any(w['contributionDays'] for w in weeks):
        raise ValueError('Empty calendar response; preserving previous artwork')
    days = [d for w in weeks for d in w['contributionDays']]
    total = sum(d['contributionCount'] for d in days)
    if total != calendar['totalContributions']:
        raise ValueError('Contribution totals do not match calendar cells')
    step = min(16.4, 880 / len(weeks))
    def pos(col, day): return (65 + col*step, 120 + day*22)
    route = [(31, 252)]
    stops = []
    for col, week in enumerate(weeks):
        active = [d for d in week['contributionDays'] if d['contributionCount'] > 0]
        if active:
            day = max(active, key=lambda d: d['contributionCount'])
            p = pos(col, day['weekday'])
            stops.append((len(route), p))
            route.append(p)
    route.append((965, 164))
    lengths = [0.0]
    for a,b in zip(route, route[1:]):
        lengths.append(lengths[-1]+math.dist(a,b))
    path = 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x,y in route)
    duration = 36
    start,end = days[0]['date'],days[-1]['date']
    s = [f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1000" height="342" viewBox="0 0 1000 342" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(login)} — Contribution Sea</title>
<desc id="desc">{total} actual GitHub contributions, {start} to {end}. Each island is a day; brighter islands mean more contributions. A pirate ship visits each active week's busiest day. Decorative foam and treasure sparkles do not represent additional contributions.</desc>
<defs>
 <linearGradient id="sea" x2="0" y2="1"><stop stop-color="#0c1528"/><stop offset="1" stop-color="#152b3d"/></linearGradient>
 <radialGradient id="glow"><stop stop-color="#f8db92" stop-opacity=".65"/><stop offset="1" stop-color="#f8db92" stop-opacity="0"/></radialGradient>
 <path id="route" d="{path}"/>
</defs>
<rect x="1" y="1" width="998" height="340" rx="20" fill="url(#sea)" stroke="#304254"/>
<g font-family="Segoe UI,DejaVu Sans,sans-serif">
 <text x="44" y="39" fill="#b5a1dc" font-size="11" font-weight="700" letter-spacing="3">THE GRAND LINE / CONTRIBUTION SEA</text>
 <text x="43" y="68" fill="#eef0fa" font-size="22" font-weight="600">Every contribution, a new discovery.</text>
 <text x="951" y="40" text-anchor="end" fill="#f2d28c" font-size="21" font-weight="700">{total}</text>
 <text x="951" y="61" text-anchor="end" fill="#90a9bb" font-size="11">contributions</text>
 <path d="M44 83 H956" stroke="#283c51"/>
''']
    months = set()
    for col,week in enumerate(weeks):
        for day in week['contributionDays']:
            date = dt.date.fromisoformat(day['date'])
            month = (date.year,date.month)
            if month not in months:
                if col < len(weeks)-2:
                    s.append(f'<text x="{pos(col,0)[0]-6:.2f}" y="101" fill="#92a9bb" font-size="10">{date.strftime("%b")}</text>')
                months.add(month)
            x,y = pos(col,day['weekday']); level=LEVELS[day['contributionLevel']]
            s.append(f'<g><title>{day["date"]}: {day["contributionCount"]} contributions</title>')
            if level:
                s.append(f'<rect x="{x-6.5:.2f}" y="{y-7}" width="13" height="14" rx="4" fill="{COLORS[level]}" stroke="{ "#e2c888" if level==4 else "#477e80"}" stroke-width=".7"/>')
                if level >= 3:
                    s.append(f'<path d="M{x-3:.2f} {y+1} q3 -5 6 0" fill="none" stroke="#d6edc9" stroke-width="1"/>')
            else:
                s.append(f'<rect x="{x-6.5:.2f}" y="{y-7}" width="13" height="14" rx="3" fill="{COLORS[0]}" opacity=".65"/>')
            s.append('</g>')
    for day,label in [(1,'M'),(3,'W'),(5,'F')]:
        s.append(f'<text x="39" y="{pos(0,day)[1]+3}" fill="#6f899d" font-size="9">{label}</text>')
    # The route is decorative; the real calendar remains visible and unchanged.
    s.append('<use xlink:href="#route" fill="none" stroke="#a5dcd1" stroke-width=".8" stroke-dasharray="2 7" opacity=".16"/>')
    for idx,(x,y) in stops:
        at=lengths[idx]/lengths[-1]
        lo=max(0,at-.018); hi=min(1,at+.045)
        if lo==0 or hi==1: continue
        timing=f'0;{lo:.6f};{at:.6f};{hi:.6f};1'
        s.append(f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{timing}" dur="{duration}s" repeatCount="indefinite"/><circle cx="{x:.2f}" cy="{y}" r="20" fill="url(#glow)"/><path d="M{x:.2f} {y-18} v8 m-4 -4 h8" stroke="#ffe5a1" stroke-width="1.7"/><rect x="{x-3:.2f}" y="{y-13}" width="6" height="4" rx="1" fill="#e8bf76"/></g>')
    # A fading chain of foam follows the same route a fraction of a second behind.
    for i in range(10,0,-1):
        s.append(f'<circle r="{1.0+i*.07:.2f}" fill="#c9eeeb" opacity="{.5-i*.035:.3f}"><animateMotion dur="{duration}s" begin="{i*.10}s" repeatCount="indefinite" calcMode="paced"><mpath xlink:href="#route"/></animateMotion></circle>')
    s.append(f'''<g>
<animateMotion dur="{duration}s" repeatCount="indefinite" calcMode="paced"><mpath xlink:href="#route"/></animateMotion>
<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.025;.97;1" dur="{duration}s" repeatCount="indefinite"/>
<g>
 <animateTransform attributeName="transform" type="rotate" values="-4;4;-4" dur="2.4s" repeatCount="indefinite"/>
 <ellipse cy="10" rx="20" ry="4" fill="#081420" opacity=".6"/>
 <path d="M-19 3 H20 L12 13 H-11Z" fill="#b6795d" stroke="#201e32" stroke-width="1.5"/>
 <path d="M-16 6 H16" stroke="#edc78c" stroke-width="2"/>
 <path d="M0 4 V-31" stroke="#dec295" stroke-width="2"/>
 <path d="M-12 -23 H11 Q17 -11 13 0 H-13 Q-9 -11 -12 -23" fill="#fbefdc" stroke="#b8a1b3" stroke-width="1"/>
 <circle cx="1" cy="-12" r="4" fill="#413449"/>
 <path d="M-5 -15 H7" stroke="#eac577" stroke-width="2.5"/>
 <path d="M1 -32 L14 -30 L9 -26 L1 -27Z" fill="#bba1e3"><animate attributeName="d" values="M1 -32 L14 -30 L9 -26 L1 -27Z;M1 -32 L14 -34 L11 -28 L1 -27Z;M1 -32 L14 -30 L9 -26 L1 -27Z" dur="1.2s" repeatCount="indefinite"/></path>
 <circle cx="19" cy="2" r="5" fill="#fae6c7" stroke="#695269"/>
 <circle cx="21" cy="1" r=".8" fill="#35283e"/>
</g></g>
<path d="M44 280 H956" stroke="#283c51"/>
<text x="44" y="306" fill="#a0b7c5" font-size="11">{start} — {end}</text>
<text x="44" y="325" fill="#738fa2" font-size="9">REAL GITHUB ACTIVITY · REFRESHED DAILY</text>
<text x="758" y="309" fill="#91aabb" font-size="10">Less</text>
''')
    for i,col in enumerate(COLORS):
        s.append(f'<rect x="{791+i*23}" y="298" width="15" height="15" rx="4" fill="{col}"/>')
    s.append('<text x="918" y="309" fill="#91aabb" font-size="10">More</text></g></svg>')
    return '\n'.join(s)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--login',default='emrezorlu1239')
    p.add_argument('--input',type=Path)
    p.add_argument('--output',type=Path,default=Path('assets/contribution-sea.svg'))
    args=p.parse_args()
    if args.input:
        data=json.loads(args.input.read_text(encoding='utf-8-sig'))
        calendar=data['data']['user']['contributionsCollection']['contributionCalendar']
    else:
        calendar=fetch_calendar(args.login)
    svg=render(calendar,args.login)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(svg,encoding='utf-8')
    print(f'Rendered {calendar["totalContributions"]} contributions to {args.output}')

if __name__=='__main__': main()
