import re
from icmplib import ping
import requests
import os, argparse
import concurrent.futures


parser = argparse.ArgumentParser()
parser.add_argument('--host', '-o', type=str, help='指定测试域名', required=True)
parser.add_argument('--ip_list', '-i', type=str, help='ip查询表', default='gl')
arg = parser.parse_args()


def load_ip_list(ip_list_file):
    working_dir = os.path.dirname(os.path.realpath(__file__))
    if ip_list_file == 'cn':
        ip_list_path = os.path.join(working_dir, ip_list_file+'_ip_list.txt')
    else:
        ip_list_path = os.path.join(working_dir, ip_list_file+'_ip_list.txt')

    with open(ip_list_path, 'r', encoding='utf-8') as f:
        ip_list = f.read().splitlines()
    return ip_list

def ping_test(ip):
    result = ping(ip, count=5, privileged=False)
    delay = result.avg_rtt
    msg = ip + '\t平均延迟: ' + str(delay) + ' ms'
    if delay<100:
        print(msg)
    else:
        print(msg)
    return delay

def sanitize_folder_name(folder_name):
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized_name = re.sub(invalid_chars, '_', folder_name)
    return sanitized_name

def get_ip_location(ip_address):
    url = f"http://ipinfo.io/{ip_address}/json"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                'ip': data.get('ip'),
                'city': data.get('city'),
                'region': data.get('region'),
                'country': data.get('country'),
                'loc': data.get('loc'),
                'org': data.get('org')
            }
        else:
            return {"error": f"Unable to fetch data, status code: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def main(working_dir, ip_list_path):

    add_host=sanitize_folder_name(arg.host)
    low_delay_ip_list_path = os.path.join(working_dir, add_host+'.txt')

    if os.path.exists(ip_list_path):
            print('读取本地保存的ip列表')
            with open(ip_list_path, 'r', encoding='utf-8') as f:
                ip_list = f.read().splitlines()
    else:
        print('没有本地保存的ip列表！程序终止！')

    with open(ip_list_path, 'w', encoding='utf-8') as f:
        for ip in ip_list:
            f.write(str(ip))

    print('\n共取得 '+str(len(ip_list))+' 个 IP, 开始测试延迟\n')

    ip_info = []
    good_ips = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(ping_test, ip) for ip in ip_list]
        delays = [f.result() for f in futures]

    for delay, ip in zip(delays, ip_list):
        ip_info.append({'ip': ip, 'delay': delay})
        if delay < 100:
            good_ips.append({'ip': ip, 'delay': delay})

    if len(good_ips) > 0:
        print('\n基于当前网络环境, 以下为延迟低于100ms的IP\n')
        good_ips.sort(key=lambda x:x['delay'])
        with open(low_delay_ip_list_path, 'w', encoding='utf-8') as f:
            for ip in good_ips:
                print(ip['ip'] + '\t平均延迟: ' + str(ip['delay']) + ' ms')
                # f.write(ip['ip']+' '+arg.host+' '+str(get_ip_location(ip['ip'])))
                f.write(ip['ip'])
                f.write('\n')
    else:
        ip_info.sort(key=lambda x:x['delay'])
        num = min(len(ip_info), 3)
        print('\n本次测试未能找到延迟低于100ms的IP! 以下为延迟最低的 ' + str(num) + ' 个节点\n')
        for i in range(0,num):
            print(ip_info[i]['ip'] + '\t平均延迟: ' + str(ip_info[i]['delay']) + ' ms')


if __name__ == '__main__':

    working_dir = os.path.dirname(os.path.realpath(__file__))
    if arg.ip_list == 'cn':
        ip_list_path = os.path.join(working_dir, arg.ip_list+'_ip_list.txt')
    else:
        ip_list_path = os.path.join(working_dir, arg.ip_list+'_ip_list.txt')

    main(working_dir, ip_list_path)
