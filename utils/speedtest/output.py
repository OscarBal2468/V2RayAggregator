import json
import base64
import os
import time

out_json = './out.json'

sub_all_base64 = "./sub/sub_merge_base64.txt"
sub_all = "./sub/sub_merge.txt"
Eternity_file_base64 = "./Eternity"
Eternity_file = "./Eternity.txt"
Eternity_Base = "./EternityBase"

splitted_output = "./sub/splitted/"

# --- Fork customization: per-country low-latency selection ---
import re
import socket

TARGET_COUNTRIES = ['US', 'JP', 'SG', 'TW', 'KR']
PER_COUNTRY = 20
FLAG_TO_CC = {
    '🇺🇸': 'US',
    '🇯🇵': 'JP',
    '🇸🇬': 'SG',
    '🇹🇼': 'TW',
    '🇰🇷': 'KR',
}
_geo_reader = None


def _geoip_cc(ip):
    global _geo_reader
    try:
        import geoip2.database
        if _geo_reader is None:
            _geo_reader = geoip2.database.Reader('./utils/Country.mmdb')
        return _geo_reader.country(ip).country.iso_code
    except Exception:
        return None


def _host_of(link):
    try:
        if link.startswith('vmess://'):
            data = json.loads(base64.b64decode(
                link[8:]).decode('utf-8', 'ignore'))
            return str(data.get('add', ''))
        m = re.search(r'@([^/:?#]+)', link)
        if m:
            return m.group(1)
        m = re.search(r'://([^/:?#]+)', link)
        return m.group(1) if m else ''
    except Exception:
        return ''


def detect_country(item):
    remarks = str(item.get('remarks', ''))
    for flag, cc in FLAG_TO_CC.items():
        if flag in remarks:
            return cc
    m = re.search(r'\b(US|JP|SG|TW|KR)\b', remarks.upper())
    if m:
        return m.group(1)
    host = _host_of(str(item.get('link', '')))
    if host:
        ip = host
        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
            try:
                socket.setdefaulttimeout(3)
                ip = socket.gethostbyname(host)
            except Exception:
                return None
        return _geoip_cc(ip)
    return None


def _ping_of(x):
    try:
        return float(x.get('ping'))
    except Exception:
        return -1


def _speed_of(x):
    try:
        return float(x.get('avg_speed') or 0)
    except Exception:
        return 0


def select_by_country(nodes):
    alive = [x for x in nodes if _ping_of(x) > 0 and _speed_of(x) > 0]
    tagged = [(detect_country(x), x) for x in alive]
    selected = []
    for cc in TARGET_COUNTRIES:
        group = [x for c, x in tagged if c == cc]
        group.sort(key=lambda x: (_ping_of(x), -_speed_of(x)))
        print('Country %s: %d alive, taking %d' % (
            cc, group.__len__(), min(PER_COUNTRY, group.__len__())))
        selected.extend(group[:PER_COUNTRY])
    # Top-up rule (Oscar, 2026-11-04): if the total falls short of the
    # combined quota, fill from the remaining alive nodes of the other
    # target countries, lowest ping first.
    quota = PER_COUNTRY * len(TARGET_COUNTRIES)
    if len(selected) < quota:
        chosen = set(id(x) for x in selected)
        rest = [x for c, x in tagged
                if c in TARGET_COUNTRIES and id(x) not in chosen]
        rest.sort(key=lambda x: (_ping_of(x), -_speed_of(x)))
        add = rest[:quota - len(selected)]
        print('Fill: topping up %d nodes from other target countries'
              % len(add))
        selected.extend(add)
    return [x['link'] for x in selected]



def read_json(file):  # 将 out.json 内容读取为列表
    while os.path.isfile(file) == False:
        # log
        #file_list = os.listdir("./")
        #print(file_list)
        print('Awaiting speedtest complete')
        time.sleep(30)
    with open(file, 'r', encoding='utf-8') as f:
        print('Reading out.json')
        proxies_all = json.load(f)["nodes"]
        f.close()
    return proxies_all


def output(list, num):
    # sort base their avg speed rather than max speed which is default option
    list = sorted(list, key=lambda x: x['avg_speed'], reverse=True)
    selected_links = select_by_country(list)

    # log
    print(list[0])
    print(list[-1])

    def arred(x, n): return x*(10**n)//1/(10**n)
    print(str(list[0]))
    output_list = []
    for item in list:
        info = "id: %s | remarks: %s | protocol: %s | ping: %s MS | avg_speed: %s MB | max_speed: %s MB | Link: %s\n" % (str(item["id"]), item["remarks"], item["protocol"], str(
            item["ping"]), str(arred(item["avg_speed"] * 0.00000095367432, 3)), str(arred(item["max_speed"] * 0.00000095367432, 3)), item["link"])
        output_list.append(info)
    with open('./LogInfo.txt', 'w') as f1:
        f1.writelines(output_list)
        f1.close()
        print('Write Log Success!')

    output_list = []
    for index in range(list.__len__()):
        proxy = list[index]['link']
        output_list.append(proxy)

    # writing content as mixed and base64
    content = '\n'.join(output_list)
    content_base64 = base64.b64encode(
        '\n'.join(output_list).encode('utf-8')).decode('ascii')
    content_base64_part = base64.b64encode(
        '\n'.join(selected_links).encode('utf-8')).decode('ascii')

    # spliting different protocols
    os.makedirs(splitted_output, exist_ok=True)
    vmess_outputs = []
    trojan_outputs = []
    ssr_outputs = []
    ss_outputs = []

    for output in output_list:
        if str(output).startswith("vmess://"):
            vmess_outputs.append(output)
        if str(output).startswith("trojan://"):
            trojan_outputs.append(output)
        if str(output).startswith("ssr://"):
            ssr_outputs.append(output)
        if str(output).startswith("ss://"):
            ss_outputs.append(output)

    with open(splitted_output.__add__("vmess.txt"), 'w') as f:
        vmess_content = "\n".join(vmess_outputs)
        f.write(vmess_content)
        print('Write vmess splitted Success!')
        f.close()

    with open(splitted_output.__add__("trojan.txt"), 'w') as f:
        trojan_content = "\n".join(trojan_outputs)
        f.write(trojan_content)
        print('Write trojan splitted Success!')
        f.close()

    with open(splitted_output.__add__("ssr.txt"), 'w') as f:
        ssr_content = "\n".join(ssr_outputs)
        f.write(ssr_content)
        print('Write ssr splitted Success!')
        f.close()

    with open(splitted_output.__add__("ss.txt"), 'w') as f:
        ss_content = "\n".join(ss_outputs)
        f.write(ss_content)
        print('Write ss splitted Success!')
        f.close()

    ##################

    with open(sub_all_base64, 'w+', encoding='utf-8') as f:
        f.write(content_base64)
        print('Write All Base64 Success!')
        f.close()
    with open(Eternity_file_base64, 'w+', encoding='utf-8') as f:
        f.write(content_base64_part)
        print('Write Part Base64 Success!')
        f.close()

    with open(sub_all, 'w') as f:
        f.write(content)
        print('Write All Success!')
        f.close()
    with open(Eternity_Base, 'w') as f:
        f.write(content)
        print('Write Base Success!')
        f.close()
    with open(Eternity_file, 'w') as f:
        f.write('\n'.join(selected_links))
        print('Write Part Base Success!')
        f.close()
    return content


if __name__ == '__main__':
    num = 200
    value = read_json(out_json)
    output(value, value.__len__() if value.__len__() <= num else num)
