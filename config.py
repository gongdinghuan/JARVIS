"""
JARVIS 配置管理模块
支持环境变量和配置文件

Author: gngdingghuan
"""

import os
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class LLMProvider(Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


class PermissionLevel(Enum):
    """权限级别枚举"""
    READ_ONLY = 1      # 只读操作，自动执行
    SAFE_WRITE = 2     # 安全写入，自动执行但记录日志
    CRITICAL = 3       # 危险操作，必须人工确认


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: LLMProvider = LLMProvider.DEEPSEEK
    
    # OpenAI 配置
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    
    # DeepSeek 配置
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    
    # Ollama 配置
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    
    # 通用配置
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True


@dataclass
class VoiceConfig:
    """语音配置"""
    # Whisper 配置
    whisper_model: str = "base"  # tiny, base, small, medium, large
    
    # TTS 配置
    tts_voice: str = "zh-CN-YunxiNeural"  # Edge-TTS 语音
    tts_rate: str = "+0%"  # 语速
    tts_volume: str = "+0%"  # 音量
    
    # VAD 配置
    vad_threshold: float = 0.5
    silence_duration: float = 0.8  # 静音多久后停止录音（秒）


@dataclass
class SecurityConfig:
    """安全配置"""
    # 允许操作的目录白名单
    allowed_directories: List[str] = field(default_factory=lambda: [
        str(Path.home() / "Desktop"),
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
    ])
    
    # 禁止访问的目录黑名单
    forbidden_directories: List[str] = field(default_factory=lambda: [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "/System",
        "/usr",
        "/bin",
    ])
    
    # 允许的安全命令（只读类）
    safe_commands: List[str] = field(default_factory=lambda: [
        "dir", "ls", "cat", "type", "echo", "pwd", "cd",
        "whoami", "date", "time", "hostname",
        "python --version", "pip list", "node --version",
    ])
    
    # 禁止的危险命令关键词
    forbidden_commands: List[str] = field(default_factory=lambda: [
        "rm -rf", "del /f", "format", "mkfs",
        "shutdown", "reboot", "halt",
        "DROP", "DELETE FROM", "TRUNCATE",
    ])
    
    # 是否需要确认危险操作
    require_confirmation: bool = True
    
    # 确认超时时间（秒）
    confirmation_timeout: int = 30


@dataclass
class MemoryConfig:
    """记忆系统配置"""
    # ChromaDB 存储路径
    chroma_persist_dir: str = field(default_factory=lambda: str(Path.home() / ".jarvis" / "memory"))
    
    # 短期记忆保留的对话轮数
    short_term_turns: int = 20
    
    # 长期记忆检索数量
    retrieval_k: int = 5
    
    # 嵌入模型
    embedding_model: str = "text-embedding-3-small"


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = "127.0.0.1"
    port: int = 8765
    cors_origins: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class IoTConfig:
    """IoT 配置"""
    # Home Assistant 配置
    ha_url: Optional[str] = field(default_factory=lambda: os.getenv("HA_URL"))
    ha_token: Optional[str] = field(default_factory=lambda: os.getenv("HA_TOKEN"))
    enabled: bool = False


@dataclass
class JarvisConfig:
    """JARVIS 总配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    iot: IoTConfig = field(default_factory=IoTConfig)
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = field(default_factory=lambda: str(Path.home() / ".jarvis" / "jarvis.log"))
    
    # 调试模式
    debug: bool = False


# 全局配置实例
config = JarvisConfig()


def get_config() -> JarvisConfig:
    """获取配置实例"""
    return config


def update_config(**kwargs) -> JarvisConfig:
    """更新配置"""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config
