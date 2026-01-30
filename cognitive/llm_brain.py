"""
JARVIS LLM 大脑模块
封装多个 LLM 提供商的统一接口

Author: gngdingghuan
"""

import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
import httpx

from config import get_config, LLMProvider
from utils.logger import log


class LLMBrain:
    """
    LLM 大脑 - 统一的 LLM 接口
    支持 OpenAI, DeepSeek, Ollama
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        """
        初始化 LLM Brain
        
        Args:
            provider: LLM 提供商，默认从配置读取
        """
        self.config = get_config().llm
        self.provider = provider or self.config.provider
        self._client: Optional[AsyncOpenAI] = None
        self._init_client()
        
        log.info(f"LLM Brain 初始化完成，使用 {self.provider.value}")
    
    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        if self.provider == LLMProvider.OPENAI:
            self._client = AsyncOpenAI(
                api_key=self.config.openai_api_key,
                base_url=self.config.openai_base_url,
            )
            self._model = self.config.openai_model
            
        elif self.provider == LLMProvider.DEEPSEEK:
            self._client = AsyncOpenAI(
                api_key=self.config.deepseek_api_key,
                base_url=self.config.deepseek_base_url,
            )
            self._model = self.config.deepseek_model
            
        elif self.provider == LLMProvider.OLLAMA:
            self._client = AsyncOpenAI(
                api_key="ollama",  # Ollama 不需要真实 key
                base_url=f"{self.config.ollama_base_url}/v1",
            )
            self._model = self.config.ollama_model
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: Function Calling 工具定义
            temperature: 温度参数
            max_tokens: 最大 token 数
            
        Returns:
            完整响应字典，包含 content 和可能的 tool_calls
        """
        try:
            kwargs = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens,
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = await self._client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "tool_calls": None,
                "finish_reason": response.choices[0].finish_reason,
            }
            
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                    for tc in message.tool_calls
                ]
            
            return result
            
        except Exception as e:
            log.error(f"LLM 请求失败: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            
        Yields:
            生成的文本片段
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                stream=True,
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            log.error(f"LLM 流式请求失败: {e}")
            raise
    
    async def simple_chat(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """
        简单聊天接口
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            
        Returns:
            AI 回复文本
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_message})
        
        response = await self.chat(messages)
        return response["content"]
    
    def get_system_prompt(self) -> str:
        """获取 JARVIS 系统提示词"""
        return """你是 JARVIS，一个智能 AI 助手，由用户创建来帮助管理日常任务和操作电脑。

你的核心特征：
1. 专业、高效、简洁的回答风格
2. 像钢铁侠里的JARVIS一样，礼貌但不啰嗦
3. 能够理解和执行用户的各种指令
4. 对于危险操作会主动提醒并请求确认

你可以使用的能力：
- 系统控制：打开应用、调节音量、执行命令
- 文件管理：读取、创建、移动、删除文件
- 网页浏览：搜索信息、打开网页
- 智能家居：控制 IoT 设备（如已配置）

当用户发出指令时，你需要分析意图并调用相应的工具来完成任务。
如果不确定用户的意图，请主动询问确认。
对于危险操作（如删除文件、执行系统命令），请务必在执行前确认。"""

    def switch_provider(self, provider: LLMProvider):
        """切换 LLM 提供商"""
        self.provider = provider
        self._init_client()
        log.info(f"已切换到 {provider.value}")
