# Toolshed

__merge_ts__: 多目录合并ts文件（需配合[ffmpeg](https://ffmpeg.org/)）

__filter_ads_in_m3u8__: 过滤m3u8中插入的广告后重建m3u8文件（广告与原视频帧速率不同）（需配合[ffmpeg](https://ffmpeg.org/)）

__anti_ban__: 在CDN搜索被weibo夹的图片（python antiBan.py -t {url} -i {ip_list_file} -o {output_file_name} -p 10）

__check_DNS__: 检测DNS（python checkDNS.py -t {url} -i {ip_list_file}）

__translate_arxiv__: arXiv论文的下载+翻译+编译（PDF）

__pdf(img)2markdown__: pdf-->img-->markdown by gemini-2.0-flash-exp-image-generation（python p2m.py --pdf_dir {pdf_dir}）

__gpu_scheduler__: GPU显存监控任务调度器

python gpu_scheduler.py --help

参数说明:

  --gpu-id              GPU设备ID (默认: 0)
  
  --memory              所需显存大小(MB) [必需]
  
  --config              任务配置文件路径
  
  --command             直接指定命令 (可重复)
  
  --interval            检查间隔时间(秒) (默认: 5.0)
  
  --log-dir             日志目录 (默认: ./logs)
  
  --scheduler-log-name  调度器日志文件名 (默认: scheduler)
  
  --create-sample       创建示例配置文件
