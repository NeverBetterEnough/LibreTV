#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox 配置转 LibreTV 源挖矿脚本
================================
抓取 Tvbox-QingNing README 收录的单仓/多仓配置 → 解析 JSON/txt → 分类站点
(type1 标准接口 / csp spider / live 直播) → 实测标准接口(LibreTV 搜索+详情格式)
→ 去重 → 生成可用源清单，--apply 时合并进 js/customer_site.js。

用法:
  python3 extract_tvbox_sources.py              # 只出清单
  python3 extract_tvbox_sources.py --apply      # 出清单并合并进 customer_site.js
  python3 extract_tvbox_sources.py --readme README.md --apply   # 从 README 提取 URL 再跑
兼容 Python 3.6+，仅依赖标准库 + curl。
"""
import json, os, re, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------------------------------------------------------------------
LIBRETV_DIR = '/root/LibreTV'
CUSTOMER_JS = os.path.join(LIBRETV_DIR, 'js', 'customer_site.js')
OUT_JSON = os.path.join(LIBRETV_DIR, 'tools', 'tvbox_sources.json')
TEST_KEYWORD = '庆余年'
WORKERS = 10
CFG_CONNECT, CFG_TOTAL = 8, 20      # 配置抓取超时
API_CONNECT, API_TOTAL = 6, 12      # 接口实测超时
MAX_DEPTH = 3

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
UA_OKHTTP = "okhttp/4.9.2"
UA_TV = "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0 Mobile Safari/537.36"
UA_LIST = [UA_PC, UA_OKHTTP, UA_TV]

# README 06 节 + 其他节精选(去重) —— (配置名, URL)。中文域名/路径运行时自动转换。
CONFIG_URLS = [
    ("官方单仓", "https://132130.v.nxog.top/api1.php?id=3"),
    ("星辰", "https://fmbox.cc/"),
    ("分享", "https://github.moeyy.xyz/https://raw.githubusercontent.com/maoystv/6/main/000.json"),
    ("小屋", "https://git.acwing.com/shhentu/lzxw/-/raw/main/Monster.json"),
    ("影探", "https://ghp.ci/https://raw.githubusercontent.com/vbskycn/tvbox/a244f6f5c08565a9a0e319d6a3cc2e919d05d893/MY%E6%8E%A2%E6%8E%A2.txt"),
    ("宝盒", "http://mzjk.top/禁止贩卖"),
    ("饭太硬", "http://www.xn--b0twm5cdf05p.com/tv"),
    ("小米", "https://www.mpanso.com/小米/DEMO.json"),
    ("OK", "http://ok321.top/ok"),
    ("王小二", "http://tvbox.xn--4kq62z5rby2qupq9ub.top"),
    ("摸鱼", "http://xn--i2ru63d.xn--les554a.com"),
    ("开心", "http://kxrj.site:55/天天开心"),
    ("讴歌", "https://xn--tkh-mf3g9f.v.nxog.top/m/111.php?ou=公众号欧歌app&mz=index&jar=index&123&b=欧歌tkh"),
    ("青龙", "https://gitee.com/yiwu369/6758/raw/master/青龙/1.json"),
    ("恒星", "http://yuhuahx.com/育华学堂/斧头帮.php"),
    ("巧记", "http://cdn.qiaoji8.com/tvbox.json"),
    ("喵影视", "http://meowtv.cn/tv"),
    ("挺好", "https://ztha.top/TVBox/thdjk.json"),
    ("驸马", "http://fmys.top/fmys.json"),
    ("龙一", "https://xn--qoqw77q.top/"),
    ("传说", "https://chuanshuo.77blog.cn/tv.json"),
    ("宝盒2", "https://ghp.ci/raw.githubusercontent.com/guot55/YGBH/main/vip2.json"),
    ("西夏", "https://2912.kstore.space/0506.json"),
    ("蓝天", "https://gitee.com/lukei7/lib/raw/Luck/自建.json"),
    ("非凡", "https://g.3344550.xyz/https://raw.githubusercontent.com/jigedos/1024/master/jsm.json"),
    ("海冰", "https://git.acwing.com/cisenyuan/kdsb/-/raw/main/海兵影视.json"),
    ("花生", "https://git.acwing.com/abai/tv/-/raw/main/huas.json"),
    ("刘伟", "https://git.acwing.com/lw0704/66/-/raw/master/jjzx.json"),
    ("超级", "https://git.acwing.com/203BDXC/tvboxt/-/raw/main/CJ.json"),
    ("剪影", "https://git.acwing.com/lkq0379/zjys/-/raw/main/zjys.json"),
    ("金鹰", "http://550.3vcn.work/wdjyys.json"),
    ("英雄", "https://cdn.githubraw.com/xuexuguang/tvbox_spider/main/tv/kk/heroaku_dtes.json"),
    ("短剧", "http://74.120.175.78/JK/XYQTVBox/dj.json"),
    ("白龙", "http://124.71.189.194/a.json"),
    ("星空", "https://dxawi.github.io/0/0.json"),
    ("全网影视(多仓)", "http://ww.weidonglong.com/ysc50311.json"),
    ("西夏影视(多仓)", "https://d.kstore.space/download/2912/xx888.json"),
    ("无邪(多仓)", "https://gitee.com/wxej/wxrj/raw/master/wx.json"),
    ("百川(多仓)", "http://pandown.pro/tvbox/tvbox.json"),
    ("阿修罗(多仓)", "https://download.kstore.space/download/2883/nzk/nzk0722.json"),
    ("D642(多仓)", "https://d.kstore.space/download/6474/tvbox/api.json"),
    ("小米备用", "http://xhww.fun:63/小米/DEMO.json"),
    ("星河", "http://xhztv.top/xhz"),
    ("星河4K", "http://xhztv.top/4k.json"),
    ("YS", "http://ztha.top/ys.json"),
    ("FLCK", "http://ztha.top/TVBox/FLCK.json"),
    ("PG", "http://ztha.top/PG/jsm.json"),
    ("DC", "http://mzjk.top/DC"),
    ("云星日记", "http://itvbox.cc/云星日记"),
    ("荷城茶秀", "http://rihou.cc:88/荷城茶秀"),
    ("奥利给", "http://tv.xn--les554a.com"),   # tv.奥利给.top punycode 近似
    ("锦哥哥", "http://jin.xn--kbrl3b8y.love"),  # jin.锦哥哥.love punycode
    ("Fish", "http://www.fish2018.us.kg/p/jsm.json"),
    ("老胡", "http://tv.laohu.cool/tvbox.json"),
    ("XC", "https://ghproxy.net/https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json"),
    ("YW", "https://ghproxy.net/https://raw.githubusercontent.com/yw88075/tvbox/main/yw.json"),
    ("QQ", "https://ghproxy.net/https://raw.githubusercontent.com/yyfxz/qqtv/main/qq.json"),
    ("高天流云", "https://ghproxy.net/raw.githubusercontent.com/gaotianliuyun/gao/master/js.json"),
    ("Max", "https://gh.con.sh/https://raw.githubusercontent.com/guot55/yg/main/max.json"),
    ("JSM非凡", "https://github.moeyy.xyz/https://raw.githubusercontent.com/guot55/yg/main/pg/jsm.json"),
    ("1024", "https://github.moeyy.xyz/https://raw.githubusercontent.com/jigedos/1024/master/jsm.json"),
    ("Orange", "https://git.acwing.com/iduoduo/orange/-/raw/main/jsm.json"),
    ("YB", "https://gitee.com/dongchenliu/liu/raw/master/yb.json"),
    ("OP", "https://gitee.com/okjack/okk/raw/master/op.txt"),
    ("One", "https://gitdl.cn/https://raw.githubusercontent.com/leevi0709/one/main/jsm.json"),
    ("100km", "https://100km.top/0"),
    ("iqinu", "https://box.iqinu.com/"),
    ("青龙DC", "https://chuanshuo.77blog.cn/dc.json"),
]

# ----------------------------------------------------------------------------
visited_cfg = set()          # 已处理的配置 URL(防环)
all_apis = {}                # 去重后的接口:  norm_api -> {name, api, from_cfg, spider?}
cfg_stats = []               # 每个配置的统计
results = {}                 # 全部输出

def log(msg):
    print(msg, flush=True)

def prep_url(url):
    """中文域名→punycode、中文路径→percent-encode。"""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ''
    try:
        host_ascii = host.encode('idna').decode('ascii')
    except Exception:
        host_ascii = host
    netloc = host_ascii
    if parts.port:
        netloc += ':%d' % parts.port
    path = urllib.parse.quote(parts.path, safe="/%:@_.-~")
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, parts.query, ''))

def curl_fetch(url, timeout=(CFG_CONNECT, CFG_TOTAL), ua=None):
    cmd = ["curl", "-skL", "--connect-timeout", str(timeout[0]), "--max-time", str(timeout[1]),
           "-H", "Accept: application/json,text/plain,*/*"]
    if ua:
        cmd += ["-H", "User-Agent: %s" % ua]
    cmd += ["-o", "-", url]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.stdout, r.returncode
    except Exception as e:
        return None, -1

def decode_bytes(b):
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('utf-8', errors='replace')

def clean_json_text(text):
    """去 BOM、去 // 行注释、去尾部逗号。"""
    t = text.lstrip('\ufeff \t\r\n')
    if not t:
        return None
    lines = []
    for ln in t.split('\n'):
        if ln.strip().startswith('//'):
            continue
        lines.append(ln)
    t = '\n'.join(lines)
    t = re.sub(r',(\s*[}\]])', r'\1', t)
    return t

def parse_json(text):
    t = clean_json_text(text)
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        return None

def classify_site(site):
    """返回 (类别, api, name)。类别: http / spider / live / other"""
    if not isinstance(site, dict):
        return 'other', '', ''
    api = str(site.get('api', '') or '').strip()
    typ = str(site.get('type', '') or '').strip()
    name = str(site.get('name', '') or '?').strip()
    al = api.lower()
    if api.startswith('csp_') or 'jar:' in al or typ == '3':
        return 'spider', api, name
    if al.endswith(('.m3u', '.m3u8')) or typ == '4' or al.startswith('clan:') or al.startswith('proxy://'):
        return 'live', api, name
    if api.startswith('http'):
        return 'http', api, name
    return 'other', api, name

def normalize_api(api):
    """去掉 query(ac=...等)、尾部斜杠、折叠路径双斜杠。"""
    a = api.strip()
    if '?' in a:
        a = a.split('?', 1)[0]
    a = re.sub(r'(?<!:)/{2,}', '/', a)   # 折叠路径双斜杠(不动 ://)
    a = a.rstrip('/')
    return a

def clean_name(name):
    """去 emoji/装饰符，保留中文/字母数字。"""
    n = re.sub(r'[^\w\u4e00-\u9fff\u00c0-\u024f -]', '', name)
    n = re.sub(r'\s+', ' ', n).strip()
    return n[:24] or '未命名'

def collect_sites(sites, cfg_name, url):
    """把站点列表分类收集进 all_apis。"""
    for site in sites:
        cat, api, name = classify_site(site)
        if cat == 'http':
            norm = normalize_api(api)
            if not norm or len(norm) < 12:
                continue
            rec = all_apis.setdefault(norm, {
                'api': norm, 'name': clean_name(name) or cfg_name,
                'from': cfg_name, 'source_url': url, 'search_ok': None,
                'search_n': 0, 'latency': None, 'detail_ok': None, 'play_url': False,
            })
            if not rec.get('name'):
                rec['name'] = clean_name(name)

def process_txt_lines(text, cfg_name, url, depth):
    """txt 多仓: 每行一个配置 URL。返回解析出的 http 接口数。"""
    n = 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith(('#', '//')):
            continue
        if ln.lower().endswith(('.m3u', '.m3u8')):
            continue
        if ln.startswith(('http://', 'https://')):
            n += process_config(cfg_name + '>子仓', ln, depth + 1)
    return n

def process_json_config(d, cfg_name, url, depth):
    """解析配置 JSON。返回 http 接口数。"""
    n = 0
    if isinstance(d, dict) and 'sites' in d and isinstance(d['sites'], list):
        collect_sites(d['sites'], cfg_name, url)
        n += len([1 for s in d['sites'] if classify_site(s)[0] == 'http'])
        # 多仓: urls 字段递归
        urls = d.get('urls')
        if isinstance(urls, list) and depth < MAX_DEPTH:
            for u in urls:
                if isinstance(u, dict):
                    uu = str(u.get('url', '') or '').strip()
                elif isinstance(u, str):
                    uu = u.strip()
                else:
                    continue
                if uu.startswith('http'):
                    n += process_config(cfg_name + '>子仓', uu, depth + 1)
        return n
    if isinstance(d, list):
        # 可能是多仓列表 [{key,name,url}, ...] 或 sites 列表
        if d and isinstance(d[0], dict) and ('url' in d[0] or 'urls' in d[0]):
            if depth < MAX_DEPTH:
                for item in d:
                    if isinstance(item, dict):
                        uu = str(item.get('url', '') or '').strip()
                        if uu.startswith('http'):
                            n += process_config(cfg_name + '>子仓', uu, depth + 1)
            return n
        if d and isinstance(d[0], dict) and 'api' in d[0]:
            collect_sites(d, cfg_name, url)
            n += len([1 for s in d if classify_site(s)[0] == 'http'])
            return n
    return n

def process_config(cfg_name, raw_url, depth=0):
    url = prep_url(raw_url)
    if url in visited_cfg or depth > MAX_DEPTH:
        return 0
    visited_cfg.add(url)
    stat = {'name': cfg_name, 'url': url, 'status': 'FETCH_FAIL', 'http': 0,
            'spider': 0, 'live': 0, 'other': 0, 'detail': ''}
    last_err = 'fetch_fail'
    content = None
    for ua in UA_LIST:
        b, rc = curl_fetch(url, timeout=(CFG_CONNECT, CFG_TOTAL), ua=ua)
        if b is None or len(b) == 0:
            continue
        content = decode_bytes(b)
        t = content.lstrip('\ufeff \t\r\n')
        if t.startswith('<'):
            last_err = 'html(ua_gate?)'
            continue  # HTML 门禁/跳转页，换 UA 再试
        last_err = 'content'
        break
    if content is None:
        stat['status'] = 'FAIL:' + last_err
        cfg_stats.append(stat)
        return 0
    t = content.lstrip('\ufeff \t\r\n')
    if t.startswith('<'):
        title = re.search(r'<title>([^<]*)</title>', t, re.I)
        stat['status'] = 'HTML_GATE:' + (title.group(1).strip()[:20] if title else '')
        stat['detail'] = t[:120].replace('\n', ' ')
        cfg_stats.append(stat)
        return 0
    # JSON?
    d = parse_json(t)
    if d is not None:
        n = process_json_config(d, cfg_name, url, depth)
        st = 'JSON'
        if isinstance(d, dict) and 'sites' in d:
            sites = d['sites']
            for s in sites:
                cat, _, _ = classify_site(s)
                if cat == 'spider': stat['spider'] += 1
                elif cat == 'live': stat['live'] += 1
                elif cat == 'other': stat['other'] += 1
            st = 'JSON(sites=%d)' % len(sites)
        elif isinstance(d, dict) and 'urls' in d:
            st = 'JSON(urls=%d)' % len(d['urls'])
        elif isinstance(d, list) and d and 'url' in d[0]:
            st = 'JSON(多仓list=%d)' % len(d)
        stat['status'] = st
        stat['http'] = n
        cfg_stats.append(stat)
        return n
    # txt 多仓列表?
    lines = [ln.strip() for ln in t.splitlines() if ln.strip() and not ln.strip().startswith(('#', '//'))]
    if lines and all(ln.startswith('http') for ln in lines[:5]):
        n = process_txt_lines(t, cfg_name, url, depth)
        stat['status'] = 'TXT_LIST(%d行)' % len(lines)
        stat['http'] = n
        cfg_stats.append(stat)
        return n
    stat['status'] = 'UNKNOWN:' + repr(t[:60])
    cfg_stats.append(stat)
    return 0

# ----------------------------------------------------------------------------
def test_api(norm, api):
    """LibreTV 格式实测: search + detail。"""
    q = urllib.parse.quote(TEST_KEYWORD)
    search_url = '%s?ac=videolist&wd=%s' % (api, q)
    t0 = time.time()
    try:
        b, rc = curl_fetch(search_url, timeout=(API_CONNECT, API_TOTAL), ua=UA_PC)
    except Exception:
        return False, None, 0, False, False
    lat = round(time.time() - t0, 1)
    if b is None or len(b) == 0:
        return False, lat, 0, False, False
    try:
        d = json.loads(b.decode('utf-8'))
    except Exception:
        try:
            d = json.loads(decode_bytes(b))
        except Exception:
            return False, lat, 0, False, False
    lst = d.get('list') if isinstance(d, dict) else None
    if d.get('code') != 1 or not isinstance(lst, list) or len(lst) == 0:
        return False, lat, 0, False, False
    n = len(lst)
    vid = str(lst[0].get('vod_id', ''))
    detail_ok, play = False, False
    if vid:
        du = '%s?ac=videolist&ids=%s' % (api, urllib.parse.quote(vid))
        try:
            b2, _ = curl_fetch(du, timeout=(API_CONNECT, API_TOTAL), ua=UA_PC)
            if b2 and len(b2) > 0:
                try:
                    dd = json.loads(decode_bytes(b2))
                    dl = dd.get('list') if isinstance(dd, dict) else None
                    if dd.get('code') == 1 and isinstance(dl, list) and dl:
                        detail_ok = True
                        play = bool(dl[0].get('vod_play_url'))
                except Exception:
                    pass
        except Exception:
            pass
    return True, lat, n, detail_ok, play

def gen_key(api, used):
    host = urllib.parse.urlsplit(api).hostname or 'src'
    host = host.lower()
    # 去掉常见前缀标签
    for pref in ('www.', 'api.', 'inc.', 'play.', 'cj.', 'cdn.', 'zy.'):
        if host.startswith(pref):
            host = host[len(pref):]
    parts = host.split('.')
    key = parts[-2] if len(parts) >= 2 and parts[-2] else parts[0]
    key = re.sub(r'[^a-z0-9]', '', key)
    if not key:
        key = re.sub(r'[^a-z0-9]', '_', host)[:20] or 'src'
    base, i = key, 2
    while key in used:
        key = '%s_%d' % (base, i)
        i += 1
    used.add(key)
    return key

def read_existing_apis():
    """返回 {key: norm_api} 现有 customer_site.js 里的源。"""
    out = {}
    if os.path.exists(CUSTOMER_JS):
        m = re.search(r'const CUSTOMER_SITES\s*=\s*\{(.*?)\};', open(CUSTOMER_JS, encoding='utf-8').read(), re.S)
        if m:
            for km in re.finditer(r'^\s*([A-Za-z0-9_]+)\s*:\s*\{\s*api:\s*[\'"]([^\'"]+)', m.group(1), re.M):
                out[km.group(1)] = normalize_api(km.group(2))
    return out

def emit_customer_site(cands):
    """生成合并后的 customer_site.js 内容(保留现有 + 新增)，返回 (text, added)。"""
    old = ''
    if os.path.exists(CUSTOMER_JS):
        old = open(CUSTOMER_JS, encoding='utf-8').read()
    m = re.search(r'const CUSTOMER_SITES\s*=\s*\{(.*?)\};', old, re.S)
    body = m.group(1).rstrip() if m else ''
    # 收集现有条目文本(保留)
    existing_blocks = [mo.group(0).strip() for mo in re.finditer(r'([A-Za-z0-9_]+)\s*:\s*\{[^}]*\},?', body, re.S)]
    existing = read_existing_apis()          # {key: norm_api}
    used = set(existing.keys())
    added = []
    lines = []
    if existing_blocks:
        lines.append('    // ---- 原有源 ----')
        for blk in existing_blocks:
            lines.append('    ' + blk.strip().rstrip(',') + ',')
    if cands:
        lines.append('    // ---- 2026-08-11 TVBox配置挖矿新增 ----')
    existing_norms = set(existing.values())
    for c in cands:
        if normalize_api(c['api']) in existing_norms:
            continue                          # 与现有源重复, 跳过
        key = gen_key(c['api'], used)
        lines.append('    %s: { api: %r, name: %r },' % (key, c['api'], c['name']))
        added.append((key, c['api'], c['name']))
    new_body = '\n'.join(lines)
    m = re.search(r'const CUSTOMER_SITES\s*=\s*\{(.*?)\};', old, re.S)
    if m:
        new_js = old[:m.start()] + 'const CUSTOMER_SITES = {\n' + new_body + '\n};\n' + old[m.end():]
    else:
        new_js = 'const CUSTOMER_SITES = {\n' + new_body + '\n};\n\nif (window.extendAPISites) {\n    window.extendAPISites(CUSTOMER_SITES);\n}\n'
    return new_js, added

# ----------------------------------------------------------------------------
def main():
    apply = '--apply' in sys.argv
    readme_path = None
    if '--readme' in sys.argv:
        i = sys.argv.index('--readme')
        if i + 1 < len(sys.argv):
            readme_path = sys.argv[i + 1]
    urls = CONFIG_URLS
    if readme_path:
        txt = open(readme_path, encoding='utf-8', errors='replace').read()
        seen = set()
        extra = []
        for u in re.findall(r'https?://[^\s<>"()]+', txt):
            u = u.rstrip('.,;:)]}').strip()
            if u.lower().endswith(('.png', '.jpg', '.gif', '.svg', '.webp', '.m3u', '.m3u8', '.apk', '.zip')):
                continue
            if u in seen:
                continue
            seen.add(u)
            extra.append((u[:30], u))
        urls = extra
        log('从 README 提取 %d 个 URL' % len(urls))

    t_start = time.time()
    log('=' * 60)
    log('TVBox 配置转源: %d 个配置, 并发 %d, 测试词 "%s"' % (len(urls), WORKERS, TEST_KEYWORD))
    log('=' * 60)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_config, n, u): (n, u) for n, u in urls}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                log('配置异常: %s' % e)

    # 实测候选
    cands = sorted(all_apis.values(), key=lambda r: r['api'])
    log('\n候选标准接口 %d 个, 开始实测(LibreTV 格式)...' % len(cands))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(test_api, r['api'], r['api']): r for r in cands}
        for f in as_completed(futs):
            r = futs[f]
            try:
                ok, lat, n, d_ok, play = f.result()
            except Exception as e:
                ok, lat, n, d_ok, play = False, None, 0, False, False
            r['search_ok'] = ok
            r['latency'] = lat
            r['search_n'] = n
            r['detail_ok'] = d_ok
            r['play_url'] = play

    # 汇总
    good = [r for r in cands if r['search_ok'] and r['detail_ok']]
    good.sort(key=lambda r: (r['latency'] or 99, r['api']))
    search_only = [r for r in cands if r['search_ok'] and not r['detail_ok']]
    bad = [r for r in cands if not r['search_ok']]

    cfg_map = {}
    for st in cfg_stats:
        cfg_map[st['url']] = st
    for r in cands:
        st = cfg_map.get(r['source_url'])
        if st:
            st['http'] = st.get('http', 0)

    print('\n' + '=' * 70)
    print('配置抓取统计 (%d 个, 耗时 %.0fs)' % (len(cfg_stats), time.time() - t_start))
    print('=' * 70)
    ok_cfg = [s for s in cfg_stats if s['status'].startswith(('JSON', 'TXT'))]
    print('  成功解析: %d | 门禁/HTML: %d | 失败: %d' % (
        len(ok_cfg),
        len([s for s in cfg_stats if s['status'].startswith('HTML')]),
        len([s for s in cfg_stats if s['status'].startswith(('FAIL', 'UNKNOWN'))])))
    for s in sorted(cfg_stats, key=lambda x: -x['http']):
        print('  %-24s %-22s http=%-3d spider=%-3d live=%-3d' % (
            s['name'][:24], s['status'][:22], s['http'], s['spider'], s['live']))

    print('\n' + '=' * 70)
    print('可用接口 (search+detail 都通过): %d 个' % len(good))
    print('=' * 70)
    for i, r in enumerate(good, 1):
        print('  %2d. [%5.1fs] %-20s %s' % (i, r['latency'] or 0, r['name'][:20], r['api']))

    if search_only:
        print('\n仅搜索可用(详情不通, 未加入): %d 个' % len(search_only))
        for r in search_only:
            print('  - %s %s' % (r['name'][:18], r['api']))
    if bad:
        print('\n不可用: %d 个' % len(bad))

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'keyword': TEST_KEYWORD,
        'cfg_stats': cfg_stats,
        'apis': cands,
        'good': [r['api'] for r in good],
        'search_only': [r['api'] for r in search_only],
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log('\n结果已存: %s' % OUT_JSON)

    if apply and good:
        new_js, added = emit_customer_site(good)
        bak = CUSTOMER_JS + '.bak'
        with open(bak, 'w', encoding='utf-8') as f:
            f.write(open(CUSTOMER_JS, encoding='utf-8').read())
        with open(CUSTOMER_JS, 'w', encoding='utf-8') as f:
            f.write(new_js)
        log('已合并 %d 个新源 -> %s (备份 %s)' % (len(added), CUSTOMER_JS, bak))
        for k, api, name in added:
            log('    %s = %s (%s)' % (k, name, api))
    elif apply:
        log('无可用接口, 未修改 %s' % CUSTOMER_JS)

if __name__ == '__main__':
    main()
