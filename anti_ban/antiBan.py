import os
import requests
import subprocess
import argparse
from tqdm import tqdm
import concurrent.futures


parser = argparse.ArgumentParser()
parser.add_argument('--target', '-t', type=str, help='目标地址', required=True)
parser.add_argument('--ip_list', '-i', type=str, help='ip查询表', default='cn')
parser.add_argument('--process', '-p', type=int, help='最大线程数', default='1')
arg = parser.parse_args()


def init_header():
    host = 'wx2.sinaimg.cn'
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0'
    ref = 'https://' + host + '/'
    lang = 'zh-TW,zh;q=0.8,zh-HK;q=0.6,en-US;q=0.4,en;q=0.2'
    accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    accept_encoding = 'gzip, deflate'
    cache_control = 'no-cache'
    header = {
        "Host": host,
        "User-Agent": ua,
        "referer": ref,
        "Accept": accept,
        "Accept-Language": lang,
        "Accept-Encoding": accept_encoding,
        # "Connection": "keep-alive",
        'Connection':'close',
        "Upgrade-Insecure-Requests": "1",
        "Pragma": cache_control,
        "Cache-Control": cache_control,
        "TE": "Trailers"
    }
    return header

def check_server_download_size(server, target_url, headers):
    try:
        response = requests.head(target_url, headers=headers, timeout=10, allow_redirects=True)
        if 'Content-Range' in response.headers:
            size = int(response.headers['Content-Range'].split('/')[-1])
        elif 'Content-Length' in response.headers:
            size = int(response.headers['Content-Length'])
        else:
            size = 0
        return server, size
    except Exception as e:
        print(f"Error checking {server} for {target_url}: {e}")
        return server, None

def check_download_sizes(cdn_servers, target_url, headers, max_workers):
    download_sizes = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_server_download_size, server, target_url, headers): server for server in cdn_servers}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(cdn_servers), desc="Checking download sizes"):
            server, size = future.result()
            download_sizes[server] = size
    return download_sizes

def get_largest_download_ip(download_sizes):
    if not download_sizes:
        return None, None
    max_ip = max(download_sizes, key=lambda k: download_sizes[k] if download_sizes[k] is not None else -1)
    return max_ip, download_sizes[max_ip]

def download(max_ip, target_url):
    if not max_ip:
        print("No valid IP address found for downloading.")
        return
    curl_command = [
        'curl', '-v', '-L', '-m', '30', '--resolve', f'wx4.sinaimg.cn:443:{max_ip}', target_url,
        '-H', 'authority: wx4.sinaimg.cn',
        '-H', 'accept: image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        '-H', 'accept-language: en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,en-US;q=0.6',
        '-H', 'cache-control: no-cache',
        '-H', 'pragma: no-cache',
        '-H', 'referer: https://weibo.com/',
        '-H', 'sec-ch-ua: "Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        '-H', 'sec-ch-ua-mobile: ?0',
        '-H', 'sec-ch-ua-platform: "Windows"',
        '-H', 'sec-fetch-dest: image',
        '-H', 'sec-fetch-mode: no-cors',
        '-H', 'sec-fetch-site: cross-site',
        '-H', 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        '--compressed', '-o', 'f.jpg'
    ]
    subprocess.run(curl_command)

def load_ip_list(ip_list_file):
    working_dir = os.path.dirname(os.path.realpath(__file__))
    if ip_list_file == 'cn':
        ip_list_path = os.path.join(working_dir, ip_list_file+'_ip_list.txt')
    else:
        ip_list_path = os.path.join(working_dir, ip_list_file+'_ip_list.txt')
    with open(ip_list_path, 'r', encoding='utf-8') as f:
        ip_list = f.read().splitlines()
    return ip_list

def main(target_url, ip_list_file, max_workers):
    ip_list = load_ip_list(ip_list_file)
    headers = init_header()
    download_sizes = check_download_sizes(ip_list, target_url, headers, max_workers)
    print("Download Sizes:", download_sizes)
    max_ip, max_size = get_largest_download_ip(download_sizes)
    print(f"Largest Download IP: {max_ip}, Size: {max_size}")
    download(max_ip, target_url)


if __name__ == '__main__':

    target_url = arg.target
    ip_list_file = arg.ip_list
    max_workers = arg.process
    
    main(target_url, ip_list_file, max_workers)
