"""YouTube publishing for Data in Motion (YouTube Data API v3, stdlib only).

Credentials come from env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.

  python3 youtube.py auth-url                       # print consent URL
  python3 youtube.py exchange '<redirected url or code>'   # -> prints refresh token
  python3 youtube.py whoami                         # channel name/id
  python3 youtube.py playlist "<title>" "<description>"     # create (or find) playlist -> id
  python3 youtube.py publish out/ep01 <playlist_id> [--privacy public|private|unlisted] [--at 2026-11-01T14:30:00Z]
  python3 youtube.py set-privacy <video_id> public|private|unlisted [--dry-run]   # change an uploaded video's privacy
  python3 youtube.py playlist-privacy <playlist_id> public|private|unlisted [--dry-run]   # e.g. open a new series' playlist
  python3 youtube.py delete <video_id> --confirm    # PERMANENT. Only with Naveen's explicit OK. Refuses public videos.
"""
import os, sys, json, urllib.request, urllib.parse, re

SCOPE = 'https://www.googleapis.com/auth/youtube.force-ssl'
REDIRECT = 'http://localhost'
API = 'https://www.googleapis.com/youtube/v3'
UP = 'https://www.googleapis.com/upload/youtube/v3'

def _req(url, data=None, headers=None, method=None):
    h = dict(headers or {})
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode(); h.setdefault('Content-Type', 'application/json')
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code} {url}\n{e.read().decode()[:2000]}')

def token():
    d = urllib.parse.urlencode(dict(client_id=os.environ['YT_CLIENT_ID'], client_secret=os.environ['YT_CLIENT_SECRET'],
                                    refresh_token=os.environ['YT_REFRESH_TOKEN'], grant_type='refresh_token')).encode()
    return _req('https://oauth2.googleapis.com/token', d)[2]['access_token']

def auth(): return {'Authorization': f'Bearer {token()}'}

def auth_url():
    q = dict(client_id=os.environ['YT_CLIENT_ID'], redirect_uri=REDIRECT, response_type='code', scope=SCOPE,
             access_type='offline', prompt='consent')
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(q)

def exchange(s):
    m = re.search(r'[?&]code=([^&\s]+)', s)
    code = urllib.parse.unquote(m.group(1)) if m else s.strip()
    d = urllib.parse.urlencode(dict(code=code, client_id=os.environ['YT_CLIENT_ID'], client_secret=os.environ['YT_CLIENT_SECRET'],
                                    redirect_uri=REDIRECT, grant_type='authorization_code')).encode()
    return _req('https://oauth2.googleapis.com/token', d)[2]

def whoami(h=None):
    j = _req(f'{API}/channels?part=snippet,status&mine=true', headers=h or auth())[2]
    it = j['items'][0]
    return dict(id=it['id'], title=it['snippet']['title'])

def playlist(title, desc, h=None):
    h = h or auth()
    page = ''
    while True:
        j = _req(f'{API}/playlists?part=snippet&mine=true&maxResults=50{page}', headers=h)[2]
        for it in j.get('items', []):
            if it['snippet']['title'] == title: return it['id']
        if 'nextPageToken' not in j: break
        page = '&pageToken=' + j['nextPageToken']
    body = dict(snippet=dict(title=title, description=desc), status=dict(privacyStatus='public'))
    return _req(f'{API}/playlists?part=snippet,status', body, h)[2]['id']

def parse_youtube_txt(path):
    s = open(path).read()
    sec = lambda name: re.search(rf'{name}:\n(.*?)(?:\n\n[A-Z]+:\n|\Z)', s, re.S).group(1).strip()
    title, desc, chapters, tags = sec('TITLE'), sec('DESCRIPTION'), sec('CHAPTERS'), sec('TAGS')
    return title[:100], (desc + '\n\nChapters:\n' + chapters)[:4900], [t.strip() for t in tags.split(',')][:30]

def publish(outdir, playlist_id, privacy='public', publish_at=None):
    h = auth()
    epid = os.path.basename(outdir.rstrip('/'))
    title, desc, tags = parse_youtube_txt(f'{outdir}/youtube.txt')
    status = dict(privacyStatus='private' if publish_at else privacy, selfDeclaredMadeForKids=False,
                  embeddable=True, license='youtube')
    if publish_at: status['publishAt'] = publish_at
    meta = dict(snippet=dict(title=title, description=desc, tags=tags, categoryId='28',  # Science & Technology
                             defaultLanguage='en', defaultAudioLanguage='en'), status=status)
    # resumable upload
    video = f'{outdir}/{epid}.mp4'; size = os.path.getsize(video)
    _, hd, _ = _req(f'{UP}/videos?uploadType=resumable&part=snippet,status', meta,
                    {**h, 'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(size)})
    loc = hd.get('Location') or hd.get('location')
    with open(video, 'rb') as f:
        vid = _req(loc, f.read(), {**h, 'Content-Type': 'video/mp4'}, 'PUT')[2]
    vid_id = vid['id']; print('uploaded', vid_id, vid['status'].get('privacyStatus'), flush=True)
    res = dict(video_id=vid_id, url=f'https://youtu.be/{vid_id}', privacy=vid['status'].get('privacyStatus'))
    # thumbnail (needs a phone-verified channel)
    try:
        with open(f'{outdir}/thumbnail.png', 'rb') as f:
            _req(f'{UP}/thumbnails/set?videoId={vid_id}', f.read(), {**h, 'Content-Type': 'image/png'}, 'POST')
        res['thumbnail'] = 'set'
    except SystemExit as e:
        res['thumbnail'] = f'failed: {str(e)[:200]}'
    # captions
    try:
        boundary = 'simcapt'
        cap_meta = json.dumps(dict(snippet=dict(videoId=vid_id, language='en', name='English', isDraft=False)))
        srt = open(f'{outdir}/{epid}.srt', 'rb').read()
        body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{cap_meta}\r\n'
                f'--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + srt + f'\r\n--{boundary}--'.encode()
        _req(f'{UP}/captions?uploadType=multipart&part=snippet', body,
             {**h, 'Content-Type': f'multipart/related; boundary={boundary}'}, 'POST')
        res['captions'] = 'added'
    except SystemExit as e:
        res['captions'] = f'failed: {str(e)[:200]}'
    # playlist
    if playlist_id:
        _req(f'{API}/playlistItems?part=snippet', dict(snippet=dict(playlistId=playlist_id,
             resourceId=dict(kind='youtube#video', videoId=vid_id))), h)
        res['playlist'] = 'added'
    return res

_STATUS_RW = ('privacyStatus', 'license', 'embeddable', 'publicStatsViewable', 'selfDeclaredMadeForKids',
              'containsSyntheticMedia')

def set_privacy(video_id, privacy, dry_run=False, h=None):
    """videos.update(part=status). Reads the current status first and sends back every writable field,
    because omitted status fields are reset to their defaults. Drops publishAt (a scheduled time would
    keep the video private)."""
    assert privacy in ('public', 'private', 'unlisted'), privacy
    h = h or auth()
    items = _req(f'{API}/videos?part=status&id={video_id}', headers=h)[2].get('items', [])
    if not items: raise SystemExit(f'video {video_id} not found on this channel')
    cur = items[0]['status']
    status = {k: cur[k] for k in _STATUS_RW if k in cur}
    status['privacyStatus'] = privacy
    body = dict(id=video_id, status=status)
    if dry_run:
        return dict(dry_run=True, current=cur.get('privacyStatus'), would_send=body)
    new = _req(f'{API}/videos?part=status', body, h, 'PUT')[2]['status']
    return dict(video_id=video_id, url=f'https://youtu.be/{video_id}', privacy=new.get('privacyStatus'))

def playlist_privacy(playlist_id, privacy, dry_run=False, h=None):
    """playlists.update(part=snippet,status). Sends back the existing title/description (required by the API)."""
    assert privacy in ('public', 'private', 'unlisted'), privacy
    h = h or auth()
    items = _req(f'{API}/playlists?part=snippet,status&id={playlist_id}', headers=h)[2].get('items', [])
    if not items: raise SystemExit(f'playlist {playlist_id} not found on this channel')
    sn = items[0]['snippet']
    body = dict(id=playlist_id, snippet=dict(title=sn['title'], description=sn.get('description', '')),
                status=dict(privacyStatus=privacy))
    if dry_run: return dict(dry_run=True, current=items[0]['status']['privacyStatus'], would_send=body)
    new = _req(f'{API}/playlists?part=snippet,status', body, h, 'PUT')[2]
    return dict(playlist_id=playlist_id, title=new['snippet']['title'], privacy=new['status']['privacyStatus'])

def delete(video_id, confirm=False, h=None):
    """Permanently delete a video. Refuses unless --confirm is given and the video is not public."""
    h = h or auth()
    items = _req(f'{API}/videos?part=status,snippet&id={video_id}', headers=h)[2].get('items', [])
    if not items: raise SystemExit(f'video {video_id} not found on this channel')
    st, title = items[0]['status'].get('privacyStatus'), items[0]['snippet']['title']
    if st == 'public': raise SystemExit(f'refusing to delete PUBLIC video {video_id} ({title})')
    if not confirm: return dict(dry_run=True, video_id=video_id, title=title, privacy=st)
    code = _req(f'{API}/videos?id={video_id}', headers=h, method='DELETE')[0]
    return dict(deleted=video_id, title=title, http=code)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'auth-url': print(auth_url())
    elif cmd == 'exchange': print(json.dumps(exchange(sys.argv[2]), indent=1))
    elif cmd == 'whoami': print(whoami())
    elif cmd == 'playlist': print(playlist(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''))
    elif cmd == 'publish':
        a = sys.argv
        priv = a[a.index('--privacy') + 1] if '--privacy' in a else 'public'
        at = a[a.index('--at') + 1] if '--at' in a else None
        print(json.dumps(publish(a[2], a[3] if len(a) > 3 and not a[3].startswith('--') else None, priv, at), indent=1))
    elif cmd == 'set-privacy':
        print(json.dumps(set_privacy(sys.argv[2], sys.argv[3], '--dry-run' in sys.argv), indent=1))
    elif cmd == 'playlist-privacy':
        print(json.dumps(playlist_privacy(sys.argv[2], sys.argv[3], '--dry-run' in sys.argv), indent=1))
    elif cmd == 'delete':
        print(json.dumps(delete(sys.argv[2], '--confirm' in sys.argv), indent=1))
