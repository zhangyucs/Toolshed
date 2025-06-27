import os
import argparse
import fitz
import base64
import requests
import time
import mimetypes
from PIL import Image
from dotenv import load_dotenv
import glob
import math

# --- 配置 ---
# 从.env文件加载API密钥
load_dotenv(dotenv_path="./API.env")
API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_NAME = "gemini-2.5-flash"
# MODEL_NAME = "gemini-2.5-flash-lite-preview-06-17"
# MODEL_NAME = "gemini-2.0-flash"
# MODEL_NAME = "gemini-2.0-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

def get_image_mime_type(file_path):
    """获取图像文件的MIME类型。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith('image/'):
        try:
            with Image.open(file_path) as img:
                format_to_mime = {
                    'JPEG': 'image/jpeg',
                    'PNG': 'image/png',
                    'GIF': 'image/gif',
                    'WEBP': 'image/webp',
                    'BMP': 'image/bmp'
                }
                pillow_mime = format_to_mime.get(img.format)
                if pillow_mime:
                    return pillow_mime
                else:
                    return mime_type if mime_type else None
        except Exception:
            return mime_type if mime_type else None
    return None

def encode_image(image_path):
    """将图像文件编码为base64。"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"错误：未找到图像文件 {image_path}")
        return None
    except Exception as e:
        print(f"读取或编码图像时出错: {e}")
        return None

def extract_text_from_images_batch(image_paths, start_page_num=1, max_retries=3, api_delay=10):
    """
    批量将多张图像发送到Gemini API并请求提取文本并格式化为LaTeX。
    支持重试机制。
    
    Args:
        image_paths: 图片路径列表
        start_page_num: 起始页码，用于生成正确的页面标题
        max_retries: 最大重试次数，默认为3次
        api_delay: API调用间隔时间（秒），重试时也会使用此延迟
    
    Returns:
        成功时返回提取的文本内容列表，失败时返回None
    """
    if not API_KEY:
        print("错误：在环境变量或.env文件中未找到GOOGLE_API_KEY。")
        return None

    if not image_paths:
        print("错误：没有提供图像路径。")
        return None

    print(f"批量处理 {len(image_paths)} 张图片 (页面 {start_page_num}-{start_page_num + len(image_paths) - 1})...")

    # 准备API请求的parts
    parts = []
    
    # 构建详细的提示文本
    if len(image_paths) == 1:
        prompt_text = f"Extract all the visible text from this image (page {start_page_num}) and output the result as ordinary markdown text. For formulas, output them in LaTeX format using $ for inline math and $ for block math."
    else:
        page_numbers = [str(start_page_num + i) for i in range(len(image_paths))]
        end_page_num = start_page_num + len(image_paths) - 1
        prompt_text = f"""Extract all the visible text from these {len(image_paths)} consecutive document pages (pages {', '.join(page_numbers)}) and output the result as ordinary markdown text. 

For each page, please:
1. Start with a header like "## Page X" where X is the actual page number
2. Extract all visible text content
3. Format formulas in LaTeX using $ for inline math and $ for block math
4. Maintain the original document structure and formatting
5. Separate each page with a clear delimiter

Process the pages in order from page {start_page_num} to page {end_page_num}."""

    parts.append({"text": prompt_text})

    # 为每张图片添加inline_data部分
    encoded_images = []
    for i, image_path in enumerate(image_paths):
        mime_type = get_image_mime_type(image_path)
        if not mime_type:
            print(f"错误：无法确定{image_path}的支持图像MIME类型。")
            print("支持的类型：JPEG, PNG, GIF, WEBP, BMP")
            continue

        encoded_image = encode_image(image_path)
        if not encoded_image:
            print(f"警告：跳过无法编码的图像 {image_path}")
            continue

        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": encoded_image
            }
        })
        encoded_images.append((image_path, mime_type))
        print(f"  已编码图片 {i+1}/{len(image_paths)}: {os.path.basename(image_path)} ({mime_type})")

    if not encoded_images:
        print("错误：没有成功编码任何图像。")
        return None

    payload = {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192  # 增加输出token限制以处理多页内容
        }
    }

    headers = {
        'Content-Type': 'application/json'
    }

    params = {
        'key': API_KEY
    }

    # 重试机制
    for attempt in range(max_retries + 1):  # +1 因为包含初始尝试
        try:
            if attempt > 0:
                print(f"🔄 重试第 {attempt} 次 (共 {max_retries} 次重试机会)...")
                if api_delay > 0:
                    print(f"⏳ 重试前等待 {api_delay} 秒...")
                    time.sleep(api_delay)
            else:
                print(f"正在发送API请求 (包含 {len(encoded_images)} 张图片)...")
            
            response = requests.post(API_URL, headers=headers, json=payload, params=params, timeout=60)
            response.raise_for_status()

            result = response.json()

            if 'candidates' in result and result['candidates']:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                    if 'text' in candidate['content']['parts'][0]:
                        extracted_text = candidate['content']['parts'][0]['text']
                        if attempt > 0:
                            print(f"✅ 重试成功！在第 {attempt} 次重试后成功提取 {len(encoded_images)} 张图片的内容")
                        else:
                            print(f"✅ 成功提取 {len(encoded_images)} 张图片的内容")
                        return extracted_text.strip()
                    else:
                        error_msg = "API响应部分不包含文本"
                        if attempt < max_retries:
                            print(f"❌ 错误：{error_msg}，准备重试...")
                            continue
                        else:
                            print(f"❌ 错误：{error_msg}，已达到最大重试次数")
                            return None
                else:
                    error_msg = "意外的API响应结构（缺少content或parts）"
                    if attempt < max_retries:
                        print(f"❌ 错误：{error_msg}，准备重试...")
                        continue
                    else:
                        print(f"❌ 错误：{error_msg}，已达到最大重试次数")
                        return None
            elif 'error' in result:
                error_msg = f"API错误：{result['error'].get('message', '未知错误')}"
                if 'code' in result['error']:
                    error_msg += f"，错误代码：{result['error']['code']}"
                
                if attempt < max_retries:
                    print(f"❌ {error_msg}，准备重试...")
                    continue
                else:
                    print(f"❌ {error_msg}，已达到最大重试次数")
                    return None
            else:
                error_msg = "意外的API响应结构（缺少candidates）"
                if attempt < max_retries:
                    print(f"❌ 错误：{error_msg}，准备重试...")
                    continue
                else:
                    print(f"❌ 错误：{error_msg}，已达到最大重试次数")
                    return None

        except requests.exceptions.RequestException as e:
            error_msg = f"发出API请求时出错: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_msg += f"，响应状态码: {e.response.status_code}"
                    error_msg += f"，响应文本: {e.response.text[:200]}..."  # 限制错误信息长度
                except Exception as inner_e:
                    error_msg += f"，无法获取错误响应详情: {inner_e}"
            
            if attempt < max_retries:
                print(f"❌ {error_msg}，准备重试...")
                continue
            else:
                print(f"❌ {error_msg}，已达到最大重试次数")
                return None
                
        except Exception as e:
            error_msg = f"发生意外错误: {e}"
            if attempt < max_retries:
                print(f"❌ {error_msg}，准备重试...")
                continue
            else:
                print(f"❌ {error_msg}，已达到最大重试次数")
                return None

    # 这里不应该到达，但为了完整性
    print("❌ 所有重试均失败")
    return None

def extract_text_from_image(image_path):
    """
    单张图像处理的兼容性函数，内部调用批量处理函数。
    保持向后兼容性。
    """
    result = extract_text_from_images_batch([image_path], 1)
    return result

def convert_pdf_to_images(pdf_path, output_folder=None, dpi=200):
    """
    使用PyMuPDF(fitz)将PDF转换为图片并保存到指定文件夹
    """
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    if output_folder is None:
        output_folder = pdf_name
    
    os.makedirs(output_folder, exist_ok=True)
    
    print(f"正在将PDF '{pdf_path}' 转换为图片...")
    
    pdf_document = fitz.open(pdf_path)
    
    image_paths = []
    zoom = dpi / 72
    
    for page_num in range(len(pdf_document)):
        print(f"处理第 {page_num+1}/{len(pdf_document)} 页...")
        
        page = pdf_document.load_page(page_num)
        
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        
        image_path = os.path.join(output_folder, f"page_{page_num+1}.png")
        pix.save(image_path)
        image_paths.append(image_path)
        
        print(f"保存第 {page_num+1} 页到 {image_path}")
    
    pdf_document.close()
    print(f"PDF已成功转换为图片并保存到 '{output_folder}' 文件夹")
    return image_paths, output_folder

def process_pdf_file(pdf_path, output_folder=None, dpi=200, batch_size=1, api_delay=10, max_retries=3):
    """
    处理单个PDF文件，转换为LaTeX并保存为与PDF同名的MD文件
    
    Args:
        pdf_path: PDF文件路径
        output_folder: 输出文件夹
        dpi: 图像分辨率
        batch_size: 每次API调用处理的图片数量
        api_delay: API调用间隔时间（秒）
        max_retries: 最大重试次数
    """
    image_paths, folder = convert_pdf_to_images(pdf_path, output_folder, dpi)
    
    # 计算批次数量
    total_batches = math.ceil(len(image_paths) / batch_size)
    print(f"\n📋 处理计划：{len(image_paths)} 张图片，分 {total_batches} 个批次处理（每批 {batch_size} 张，最多重试 {max_retries} 次）")
    
    all_contents = []
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(image_paths))
        batch_image_paths = image_paths[start_idx:end_idx]
        start_page_num = start_idx + 1
        
        print(f"\n🔄 处理批次 {batch_idx + 1}/{total_batches} (页面 {start_page_num}-{start_page_num + len(batch_image_paths) - 1})...")
        
        # API调用间隔控制
        if batch_idx > 0 and api_delay > 0:
            print(f"⏳ 等待 {api_delay} 秒...")
            time.sleep(api_delay)
        
        # 批量处理图片（带重试机制）
        batch_content = extract_text_from_images_batch(batch_image_paths, start_page_num, max_retries, api_delay)
        
        if batch_content:
            all_contents.append(batch_content)
            
            # 保存批次临时文件
            batch_temp_file = os.path.join(folder, f"batch_{batch_idx + 1}_pages_{start_page_num}-{start_page_num + len(batch_image_paths) - 1}.md")
            with open(batch_temp_file, "w", encoding="utf-8") as f:
                f.write(batch_content)
            print(f"✅ 已保存批次内容到临时文件: {batch_temp_file}")
        else:
            print(f"❌ 批次 {batch_idx + 1} 处理失败（已尝试 {max_retries + 1} 次）")
            all_contents.append(f"## 批次 {batch_idx + 1} (页面 {start_page_num}-{start_page_num + len(batch_image_paths) - 1})\n\n无法提取内容（API调用失败）")
    
    # 合并所有内容
    if all_contents:
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        md_file = os.path.splitext(pdf_path)[0] + ".md"
        
        with open(md_file, "w", encoding="utf-8") as outfile:
            outfile.write(f"# {pdf_basename}\n\n")
            outfile.write(f"*本文档由PDF自动转换生成，共 {len(image_paths)} 页，使用批量处理模式（每批 {batch_size} 页，最多重试 {max_retries} 次）*\n\n")
            
            for i, content in enumerate(all_contents):
                outfile.write(content)
                if i < len(all_contents) - 1:  # 不在最后一个内容后添加分隔符
                    outfile.write("\n\n---\n\n")
        
        print(f"📄 已合并所有内容并保存到: {md_file}")
        
        # 保存副本到图片文件夹
        folder_md_file = os.path.join(folder, pdf_basename + ".md")
        if md_file != folder_md_file:
            with open(folder_md_file, "w", encoding="utf-8") as f:
                f.write(open(md_file, "r", encoding="utf-8").read())
            print(f"📄 已保存副本到: {folder_md_file}")
        
        return md_file
    else:
        print("❌ 没有成功提取任何内容，无法生成文件")
        return None

def process_multiple_pdfs(pdf_paths, output_base_folder="output", dpi=200, batch_size=1, api_delay=10, max_retries=3):
    """
    处理多个PDF文件
    
    Args:
        pdf_paths: PDF文件路径列表
        output_base_folder: 输出基础文件夹
        dpi: 图像分辨率
        batch_size: 每次API调用处理的图片数量
        api_delay: API调用间隔时间（秒）
        max_retries: 最大重试次数
    """
    results = []
    
    os.makedirs(output_base_folder, exist_ok=True)
    
    print(f"🚀 开始批量处理模式：每次处理 {batch_size} 张图片，调用间隔 {api_delay} 秒，最多重试 {max_retries} 次")
    
    for i, pdf_path in enumerate(pdf_paths):
        print(f"\n📚 处理PDF {i+1}/{len(pdf_paths)}: {pdf_path}")
        
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_folder = os.path.join(output_base_folder, pdf_name)
        
        result = process_pdf_file(pdf_path, output_folder, dpi, batch_size, api_delay, max_retries)
        
        if result:
            results.append((pdf_path, result))
            print(f"✅ 成功处理 {pdf_path} -> {result}")
        else:
            print(f"❌ 处理 {pdf_path} 失败")
    
    print("\n📊 处理结果摘要:")
    for pdf_path, md_path in results:
        print(f"✅ PDF: {pdf_path} -> MD: {md_path}")
    
    if len(results) != len(pdf_paths):
        failed_count = len(pdf_paths) - len(results)
        print(f"⚠️  警告：{failed_count} 个PDF文件处理失败")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将PDF转换为Markdown (包含LaTeX格式的公式) - 支持批量图片处理和重试机制。")
    parser.add_argument("--pdf_dir", help="PDF文件所在目录（将处理该目录中的所有PDF）")
    parser.add_argument("--pdf_files", nargs="+", help="要处理的PDF文件列表")
    parser.add_argument("--output", default="output", help="输出文件夹路径")
    parser.add_argument("--dpi", type=int, default=200, help="图像分辨率DPI，默认为200")
    parser.add_argument("--batch_size", type=int, default=10, help="每次API调用处理的图片数量")
    parser.add_argument("--api_delay", type=int, default=10, help="API调用间隔时间（秒）")
    parser.add_argument("--max_retries", type=int, default=5, help="API调用失败时的最大重试次数")
    
    args = parser.parse_args()
    
    # 参数验证
    if args.batch_size < 1:
        print("错误：batch_size必须大于等于1")
        exit(1)
    
    if args.api_delay < 0:
        print("错误：api_delay不能为负数")
        exit(1)
    
    if args.max_retries < 0:
        print("错误：max_retries不能为负数")
        exit(1)

    pdf_paths = []
    
    if args.pdf_dir:
        if not os.path.exists(args.pdf_dir):
            print(f"错误: 目录 '{args.pdf_dir}' 不存在")
            exit(1)
        
        pdf_paths = glob.glob(os.path.join(args.pdf_dir, "*.pdf"))
        if not pdf_paths:
            print(f"警告: 在目录 '{args.pdf_dir}' 中未找到PDF文件")
            exit(0)
    
    elif args.pdf_files:
        for pdf_file in args.pdf_files:
            if os.path.exists(pdf_file):
                pdf_paths.append(pdf_file)
            else:
                print(f"警告: PDF文件 '{pdf_file}' 不存在，将被跳过")
    
    else:
        parser.print_help()
        print("\n错误: 必须指定 --pdf_dir 或 --pdf_files")
        exit(1)
    
    if not pdf_paths:
        print("错误: 没有找到有效的PDF文件")
        exit(1)
    
    print(f"🎯 配置信息:")
    print(f"  - 批量大小: {args.batch_size} 张图片/次")
    print(f"  - API延迟: {args.api_delay} 秒")
    print(f"  - 最大重试: {args.max_retries} 次")
    print(f"  - 图像DPI: {args.dpi}")
    print(f"  - 输出目录: {args.output}")
    
    print(f"\n📁 将处理 {len(pdf_paths)} 个PDF文件:")
    for pdf_path in pdf_paths:
        print(f"  - {pdf_path}")
    
    process_multiple_pdfs(pdf_paths, args.output, args.dpi, args.batch_size, args.api_delay, args.max_retries)
    print("\n🎉 所有处理完成！")
