#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU显存监控任务调度器
功能：
1. 监控指定GPU的剩余显存
2. 当显存充足时按顺序执行命令列表
3. 监控进程状态，自动执行下一个任务
"""

import subprocess
import time
import logging
import argparse
import json
import os
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import pynvml
NVML_AVAILABLE = True

def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    清理文件名，移除非法字符并限制长度
    
    Args:
        filename: 原始文件名
        max_length: 最大长度限制
        
    Returns:
        清理后的合法文件名
    """
    # 移除或替换非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除多余的空格和点
    filename = re.sub(r'\s+', '_', filename.strip())
    filename = filename.strip('.')
    # 限制长度
    if len(filename) > max_length:
        filename = filename[:max_length]
    # 确保不为空
    if not filename:
        filename = "unnamed"
    
    return filename


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


@dataclass
class Task:
    """任务数据类"""
    id: int
    command: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    exit_code: Optional[int] = None
    log_file: Optional[str] = None


class GPUMemoryMonitor:
    """GPU显存监控器"""
    
    def __init__(self):
        if not NVML_AVAILABLE:
            raise RuntimeError("pynvml库未安装，无法监控GPU显存")
        
        try:
            pynvml.nvmlInit()
            self.device_count = pynvml.nvmlDeviceGetCount()
            print(f"检测到 {self.device_count} 个GPU设备")
        except Exception as e:
            raise RuntimeError(f"初始化NVML失败: {e}")
    
    def get_gpu_memory_info(self, gpu_id: int) -> Dict[str, int]:
        """
        获取指定GPU的显存信息
        
        Args:
            gpu_id: GPU设备ID
            
        Returns:
            包含total, used, free显存信息的字典 (单位: MB)
        """
        if gpu_id >= self.device_count:
            raise ValueError(f"GPU ID {gpu_id} 超出范围，系统只有 {self.device_count} 个GPU")
        
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            return {
                'total': mem_info.total // (1024 * 1024),  # 转换为MB
                'used': mem_info.used // (1024 * 1024),
                'free': mem_info.free // (1024 * 1024)
            }
        except Exception as e:
            raise RuntimeError(f"获取GPU {gpu_id} 显存信息失败: {e}")
    
    def check_memory_available(self, gpu_id: int, required_memory_mb: int) -> bool:
        """
        检查GPU是否有足够的可用显存
        
        Args:
            gpu_id: GPU设备ID
            required_memory_mb: 所需显存大小(MB)
            
        Returns:
            True if 可用显存 >= 所需显存
        """
        mem_info = self.get_gpu_memory_info(gpu_id)
        return mem_info['free'] >= required_memory_mb


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, gpu_id: int, required_memory_mb: int, 
                 check_interval: float = 5.0, log_dir: str = "./logs",
                 scheduler_log_name: str = "scheduler"):
        """
        初始化任务调度器
        
        Args:
            gpu_id: 目标GPU设备ID
            required_memory_mb: 所需显存大小(MB)
            check_interval: 检查间隔时间(秒)
            log_dir: 日志目录
            scheduler_log_name: 调度器日志文件名(不含扩展名)
        """
        self.gpu_id = gpu_id
        self.required_memory_mb = required_memory_mb
        self.check_interval = check_interval
        self.log_dir = log_dir
        self.scheduler_log_name = scheduler_log_name
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 初始化GPU监控器
        try:
            self.gpu_monitor = GPUMemoryMonitor()
        except Exception as e:
            self.logger.error(f"GPU监控器初始化失败: {e}")
            raise
        
        # 任务列表和当前运行的进程
        self.tasks: List[Task] = []
        self.current_process: Optional[subprocess.Popen] = None
        self.current_task_index = 0
        
        self.logger.info(f"任务调度器初始化完成 - GPU: {gpu_id}, 所需显存: {required_memory_mb}MB")
    
    def _setup_logging(self):
        """设置日志配置"""
        # 清理调度器日志名称
        clean_log_name = sanitize_filename(self.scheduler_log_name)
        log_file = os.path.join(self.log_dir, f'{clean_log_name}.log')
        
        # 创建logger
        self.logger = logging.getLogger('TaskScheduler')
        self.logger.setLevel(logging.INFO)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 设置格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def add_task(self, command: str, description: str = "") -> int:
        """
        添加任务到执行列表
        
        Args:
            command: 要执行的命令
            description: 任务描述
            
        Returns:
            任务ID
        """
        task_id = len(self.tasks)
        task_description = description or f"Task {task_id}"
        
        # 根据description生成日志文件名
        if description:
            # 使用description作为文件名
            log_filename = sanitize_filename(description)
        else:
            # 使用默认格式
            log_filename = f"task_{task_id}"
        
        # 确保文件名唯一性
        base_log_file = os.path.join(self.log_dir, f'{log_filename}.log')
        log_file = base_log_file
        counter = 1
        while any(task.log_file == log_file for task in self.tasks):
            log_file = os.path.join(self.log_dir, f'{log_filename}_{counter}.log')
            counter += 1
        
        task = Task(
            id=task_id,
            command=command,
            description=task_description,
            log_file=log_file
        )
        self.tasks.append(task)
        
        self.logger.info(f"添加任务 {task_id}: {task_description} -> {command}")
        self.logger.info(f"任务 {task_id} 日志文件: {log_file}")
        return task_id
    
    def load_tasks_from_file(self, file_path: str):
        """
        从文件加载任务列表
        
        Args:
            file_path: 任务配置文件路径 (JSON格式)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            for task_data in tasks_data:
                self.add_task(
                    command=task_data['command'],
                    description=task_data.get('description', '')
                )
            
            self.logger.info(f"从文件 {file_path} 加载了 {len(tasks_data)} 个任务")
            
        except Exception as e:
            self.logger.error(f"加载任务文件失败: {e}")
            raise
    
    def check_gpu_memory(self) -> bool:
        """检查GPU显存是否足够"""
        try:
            mem_info = self.gpu_monitor.get_gpu_memory_info(self.gpu_id)
            available = mem_info['free'] >= self.required_memory_mb
            
            self.logger.debug(
                f"GPU {self.gpu_id} 显存状态: "
                f"总计={mem_info['total']}MB, "
                f"已用={mem_info['used']}MB, "
                f"可用={mem_info['free']}MB, "
                f"所需={self.required_memory_mb}MB, "
                f"满足条件={available}"
            )
            
            return available
            
        except Exception as e:
            self.logger.error(f"检查GPU显存失败: {e}")
            return False
    
    def execute_task(self, task: Task) -> bool:
        """
        执行单个任务
        
        Args:
            task: 要执行的任务
            
        Returns:
            True if 任务启动成功
        """
        try:
            self.logger.info(f"开始执行任务 {task.id}: {task.description}")
            
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            
            # 打开日志文件
            log_file = open(task.log_file, 'w', encoding='utf-8')
            
            # 启动进程
            self.current_process = subprocess.Popen(
                task.command,
                shell=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            self.logger.info(f"任务 {task.id} 已启动，PID: {self.current_process.pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动任务 {task.id} 失败: {e}")
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            return False
    
    def check_current_process(self) -> bool:
        """
        检查当前进程状态
        
        Returns:
            True if 进程仍在运行
        """
        if self.current_process is None:
            return False
        
        # 检查进程是否结束
        exit_code = self.current_process.poll()
        
        if exit_code is not None:
            # 进程已结束
            current_task = self.tasks[self.current_task_index]
            current_task.end_time = time.time()
            current_task.exit_code = exit_code
            
            if exit_code == 0:
                current_task.status = TaskStatus.COMPLETED
                self.logger.info(f"任务 {current_task.id} 执行成功")
            else:
                current_task.status = TaskStatus.FAILED
                self.logger.error(f"任务 {current_task.id} 执行失败，退出码: {exit_code}")
            
            # 计算执行时间
            if current_task.start_time:
                duration = current_task.end_time - current_task.start_time
                self.logger.info(f"任务 {current_task.id} 执行耗时: {duration:.2f}秒")
            
            self.current_process = None
            self.current_task_index += 1
            
            return False
        
        return True
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取调度器状态摘要"""
        completed = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
        failed = sum(1 for task in self.tasks if task.status == TaskStatus.FAILED)
        pending = sum(1 for task in self.tasks if task.status == TaskStatus.PENDING)
        running = sum(1 for task in self.tasks if task.status == TaskStatus.RUNNING)
        
        try:
            mem_info = self.gpu_monitor.get_gpu_memory_info(self.gpu_id)
        except:
            mem_info = {'total': 0, 'used': 0, 'free': 0}
        
        return {
            'total_tasks': len(self.tasks),
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'running': running,
            'current_task_index': self.current_task_index,
            'gpu_memory': mem_info,
            'memory_sufficient': mem_info['free'] >= self.required_memory_mb
        }
    
    def run(self):
        """运行任务调度器主循环"""
        self.logger.info("任务调度器开始运行")
        
        if not self.tasks:
            self.logger.warning("没有任务需要执行")
            return
        
        try:
            while self.current_task_index < len(self.tasks):
                # 检查当前进程状态
                if self.check_current_process():
                    # 进程仍在运行，等待
                    time.sleep(self.check_interval)
                    continue
                
                # 没有运行中的进程，尝试启动下一个任务
                if self.current_task_index >= len(self.tasks):
                    break
                
                current_task = self.tasks[self.current_task_index]
                
                # 检查GPU显存
                if not self.check_gpu_memory():
                    self.logger.info(
                        f"GPU {self.gpu_id} 显存不足，等待 {self.check_interval} 秒后重试..."
                    )
                    time.sleep(self.check_interval)
                    continue
                
                # 显存充足，执行任务
                if not self.execute_task(current_task):
                    # 任务启动失败，跳过到下一个
                    self.current_task_index += 1
                    continue
                
                # 任务启动成功，等待一段时间再检查
                time.sleep(self.check_interval)
            
            # 等待最后一个任务完成
            while self.current_process and self.check_current_process():
                time.sleep(self.check_interval)
            
            self.logger.info("所有任务执行完成")
            
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在停止...")
            if self.current_process:
                self.logger.info("终止当前进程...")
                self.current_process.terminate()
                self.current_process.wait()
        
        except Exception as e:
            self.logger.error(f"调度器运行出错: {e}")
            raise
        
        finally:
            # 打印最终统计
            summary = self.get_status_summary()
            self.logger.info(f"执行统计: {summary}")


def create_sample_config(file_path: str):
    """创建示例配置文件"""
    sample_tasks = [
        {
            "command": "python train_model_1.py --epochs 10",
            "description": "ResNet50_ImageNet_Training"
        },
        {
            "command": "python train_model_2.py --batch_size 32",
            "description": "BERT_Fine_Tuning_Task"
        },
        {
            "command": "python evaluate_model.py --model_path ./models/",
            "description": "Model_Performance_Evaluation"
        },
        {
            "command": "python data_preprocessing.py --dataset large_dataset",
            "description": "Large_Dataset_Preprocessing"
        }
    ]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(sample_tasks, f, ensure_ascii=False, indent=2)
    
    print(f"示例配置文件已创建: {file_path}")
    print("注意: description将用作任务日志文件名，请使用有意义的描述")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GPU显存监控任务调度器')
    parser.add_argument('--gpu-id', type=int, default=0, help='GPU设备ID (默认: 0)')
    parser.add_argument('--memory', type=int, required=True, 
                       help='所需显存大小(MB)')
    parser.add_argument('--config', type=str, help='任务配置文件路径')
    parser.add_argument('--command', type=str, action='append', 
                       help='直接指定要执行的命令 (可重复使用)')
    parser.add_argument('--interval', type=float, default=5.0, 
                       help='检查间隔时间(秒) (默认: 5.0)')
    parser.add_argument('--log-dir', type=str, default='./logs', 
                       help='日志目录 (默认: ./logs)')
    parser.add_argument('--scheduler-log-name', type=str, default='scheduler',
                       help='调度器日志文件名(不含扩展名) (默认: scheduler)')
    parser.add_argument('--create-sample', type=str, 
                       help='创建示例配置文件')
    
    args = parser.parse_args()
    
    # 创建示例配置文件
    if args.create_sample:
        create_sample_config(args.create_sample)
        return
    
    # 检查参数
    if not args.config and not args.command:
        parser.error("必须指定 --config 或 --command 参数")
    
    try:
        # 创建调度器
        scheduler = TaskScheduler(
            gpu_id=args.gpu_id,
            required_memory_mb=args.memory,
            check_interval=args.interval,
            log_dir=args.log_dir,
            scheduler_log_name=args.scheduler_log_name
        )
        
        # 加载任务
        if args.config:
            scheduler.load_tasks_from_file(args.config)
        
        if args.command:
            for i, cmd in enumerate(args.command):
                scheduler.add_task(cmd, f"命令行任务 {i+1}")
        
        # 运行调度器
        scheduler.run()
        
    except Exception as e:
        print(f"程序执行失败: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
