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

# --- 配置 ---
# 从.env文件加载API密钥
load_dotenv(dotenv_path="./API.env")
API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
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

def extract_text_from_image(image_path):
    """
    将图像发送到Gemini API并请求提取文本并格式化为LaTeX。
    """
    if not API_KEY:
        print("错误：在环境变量或.env文件中未找到GOOGLE_API_KEY。")
        return None

    mime_type = get_image_mime_type(image_path)
    if not mime_type:
        print(f"错误：无法确定{image_path}的支持图像MIME类型。")
        print("支持的类型：JPEG, PNG, GIF, WEBP, BMP")
        return None

    print(f"处理 '{os.path.basename(image_path)}' (类型: {mime_type})...")

    encoded_image = encode_image(image_path)
    if not encoded_image:
        return None

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Extract all the visible text in the image and output the result as ordinary markdown text. For formulas, output them in latex format"
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048
        }
    }

    headers = {
        'Content-Type': 'application/json'
    }

    params = {
        'key': API_KEY
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, params=params)
        response.raise_for_status()

        result = response.json()

        if 'candidates' in result and result['candidates']:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                if 'text' in candidate['content']['parts'][0]:
                    extracted_text = candidate['content']['parts'][0]['text']
                    return extracted_text.strip()
                else:
                    print("错误：API响应部分不包含文本。")
                    return None
            else:
                print("错误：意外的API响应结构（缺少content或parts）。")
                return None
        elif 'error' in result:
            print(f"API错误：{result['error'].get('message', '未知错误')}")
            return None
        else:
            print("错误：意外的API响应结构（缺少candidates）。")
            return None

    except requests.exceptions.RequestException as e:
        print(f"发出API请求时出错: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print("响应状态码:", e.response.status_code)
                print("响应文本:", e.response.text)
            except Exception as inner_e:
                print(f"无法打印错误响应详情: {inner_e}")
        return None
    except Exception as e:
        print(f"发生意外错误: {e}")
        return None

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
    
    print(f"PDF已成功转换为图片并保存到 '{output_folder}' 文件夹")
    return image_paths, output_folder

def process_pdf_file(pdf_path, output_folder=None, dpi=200):
    """处理单个PDF文件，转换为LaTeX并保存为与PDF同名的MD文件"""
    image_paths, folder = convert_pdf_to_images(pdf_path, output_folder, dpi)
    
    latex_contents = []
    for i, image_path in enumerate(image_paths):
        print(f"处理图片 {i+1}/{len(image_paths)}...")
        
        if i > 0:
            print("等待10秒...")
            time.sleep(10)
        
        latex_content = extract_text_from_image(image_path)
        
        if latex_content:
            page_info = f"## 第{i+1}页\n\n"
            latex_contents.append(page_info + latex_content)
            
            temp_file = os.path.splitext(image_path)[0] + ".md"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(page_info + latex_content)
            
            print(f"已保存页面内容到临时文件: {temp_file}")
        else:
            print(f"无法从 {image_path} 提取内容")
            latex_contents.append(f"## 第{i+1}页\n\n无法提取内容")
    
    if latex_contents:
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        md_file = os.path.splitext(pdf_path)[0] + ".md"
        
        with open(md_file, "w", encoding="utf-8") as outfile:
            outfile.write(f"# {pdf_basename}\n\n")
            
            for content in latex_contents:
                outfile.write(content)
                outfile.write("\n\n---\n\n")
        
        print(f"已合并所有内容并保存到: {md_file}")
        
        folder_md_file = os.path.join(folder, pdf_basename + ".md")
        if md_file != folder_md_file:
            with open(folder_md_file, "w", encoding="utf-8") as f:
                f.write(open(md_file, "r", encoding="utf-8").read())
            print(f"已保存副本到: {folder_md_file}")
        
        return md_file
    else:
        print("没有成功提取任何内容，无法生成文件")
        return None

def process_multiple_pdfs(pdf_paths, output_base_folder="output", dpi=200):
    """处理多个PDF文件"""
    results = []
    
    os.makedirs(output_base_folder, exist_ok=True)
    
    for i, pdf_path in enumerate(pdf_paths):
        print(f"\n处理PDF {i+1}/{len(pdf_paths)}: {pdf_path}")
        
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_folder = os.path.join(output_base_folder, pdf_name)
        
        result = process_pdf_file(pdf_path, output_folder, dpi)
        
        if result:
            results.append((pdf_path, result))
            print(f"成功处理 {pdf_path} -> {result}")
        else:
            print(f"处理 {pdf_path} 失败")
    
    print("\n处理结果摘要:")
    for pdf_path, md_path in results:
        print(f"PDF: {pdf_path} -> MD: {md_path}")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将PDF转换为Markdown (包含LaTeX格式的公式)。")
    parser.add_argument("--pdf_dir", help="PDF文件所在目录（将处理该目录中的所有PDF）")
    parser.add_argument("--pdf_files", nargs="+", help="要处理的PDF文件列表")
    parser.add_argument("--output", default="output", help="输出文件夹路径")
    parser.add_argument("--dpi", type=int, default=200, help="图像分辨率DPI，默认为200")
    
    args = parser.parse_args()
    
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
    
    print(f"将处理 {len(pdf_paths)} 个PDF文件:")
    for pdf_path in pdf_paths:
        print(f"  - {pdf_path}")
    
    process_multiple_pdfs(pdf_paths, args.output, args.dpi)
