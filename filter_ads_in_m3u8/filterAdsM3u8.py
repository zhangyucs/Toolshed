import os
import shutil
from collections import defaultdict
import subprocess
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm


def get_frame_rate(file_path):
    try:
        result = subprocess.run(
            ['ffprobe.exe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        frame_rate = result.stdout.decode().split('/')
        return int(frame_rate[0])
    except Exception as e:
        return f"Error: {str(e)}"


def check_frame_rates(folder_path, parallelism=4):
    ts_files = [f for f in os.listdir(folder_path) if f.endswith('.ts')]
    frame_rates = {}
    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        results = list(tqdm(executor.map(lambda f: (f, get_frame_rate(os.path.join(folder_path, f))), ts_files), total=len(ts_files)))
    for file, rate in results:
        frame_rates[file] = rate
    return frame_rates


def analyses(data):
    fps_dict = defaultdict(list)
    for file, fps in data.items():
        fps_dict[fps].append(file)
    if fps_dict:
        min_key = min(fps_dict, key=lambda k: len(fps_dict[k]))
        return fps_dict[min_key]
    else:
        return None
    

def rebuild_m3u8(file_list):
    m3u8_path = file_list[0]
    ts_files = set(file_list[1:])
    if not os.path.exists(m3u8_path + '.bak'):
        backup_path = m3u8_path + '.bak'
        shutil.copy(m3u8_path, backup_path)
        print(f"Backed up {m3u8_path} to {backup_path}")
    print(f"{m3u8_path}.bak already exist")
    with open(m3u8_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    indices_to_remove = set()
    i = 0
    while i < len(lines):
        if any(ts_file in lines[i] for ts_file in ts_files):
            indices_to_remove.add(i - 1)
            indices_to_remove.add(i)
            i += 1  
        i += 1
    new_lines = [line for i, line in enumerate(lines) if i not in indices_to_remove]
    with open(m3u8_path, 'w', encoding='utf-8') as file:
        file.writelines(new_lines)


def main(paths, max_workers):
    for path in paths:
        print(f"{path}")
        ts_path = path + '/index/'
        frame_rates = check_frame_rates(ts_path, max_workers)
        result = analyses(frame_rates)
        m3u8_path = path + '/index.m3u8'
        result.insert(0, m3u8_path)
        rebuild_m3u8(result)
        print(f"{result}")


if __name__ == '__main__':
    max_workers = 50
    paths = ['1.m3u8', '2.m3u8', '3.m3u8', '4.m3u8', 
            '5.m3u8', '6.m3u8', '7.m3u8', '8.m3u8', 
            '9.m3u8', '10.m3u8', '11.m3u8', '12.m3u8']
    main(paths, max_workers)
