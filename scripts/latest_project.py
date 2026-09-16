"""Keep the profile linked to the user's latest indexed public commit."""
import html
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

START='<!-- latest-project:start -->'
END='<!-- latest-project:end -->'

def render(data):
    if data.get('incomplete_results'):
        raise ValueError('Incomplete GitHub search; retaining existing project')
    items=data.get('items',[])
    if not items:
        return '<p align="center">My next adventure is on the horizon.</p>'
    item=items[0]
    repo=item['repository']
    if repo.get('private') or repo['full_name'].lower()=='emrezorlu1239/emrezorlu1239':
        raise ValueError('Excluded repository returned by search')
    esc=html.escape
    return ('<h3 align="center">Currently sailing in ⚓</h3>\n'
      f'<p align="center"><a href="{esc(repo["html_url"],quote=True)}"><strong>{esc(repo["name"])}</strong></a><br />\n'
      f'<sub>Latest public commit · <a href="{esc(item["html_url"],quote=True)}">{esc(item["sha"][:7])}</a> · {esc(item["commit"]["committer"]["date"][:10])}</sub></p>')

def main():
    query=urllib.parse.urlencode({'q':'author:emrezorlu1239 is:public -repo:emrezorlu1239/emrezorlu1239',
                                'sort':'committer-date','order':'desc','per_page':1})
    headers={'Accept':'application/vnd.github+json','User-Agent':'profile-latest-project'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    req=urllib.request.Request('https://api.github.com/search/commits?'+query,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as response:
        data=json.load(response)
    block=render(data)
    p=Path('README.md'); text=p.read_text(encoding='utf-8')
    if text.count(START)!=1 or text.count(END)!=1:
        raise ValueError('Expected one pair of latest-project markers')
    before,rest=text.split(START); _,after=rest.split(END)
    p.write_text(before+START+'\n'+block+'\n'+END+after,encoding='utf-8')
    print('Latest project:',data['items'][0]['repository']['full_name'] if data['items'] else 'none')

if __name__=='__main__': main()
