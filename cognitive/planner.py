"""
JARVIS ReAct 任务规划器
实现 Reasoning + Acting 循环

Author: gngdingghuan
"""

import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from cognitive.llm_brain import LLMBrain
from cognitive.memory import MemoryManager
from cognitive.context_manager import ContextManager
from utils.logger import log


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    needs_confirmation: bool = False
    confirmation_message: Optional[str] = None


class ReActPlanner:
    """
    ReAct 任务规划器
    实现 感知 -> 思考 -> 行动 -> 观察 -> 反思 循环
    """
    
    MAX_ITERATIONS = 10  # 最大循环次数，防止无限循环
    
    def __init__(
        self,
        brain: LLMBrain,
        memory: MemoryManager,
        context: ContextManager,
        skills: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化规划器
        
        Args:
            brain: LLM 大脑实例
            memory: 记忆管理器
            context: 上下文管理器
            skills: 技能字典 {skill_name: skill_instance}
        """
        self.brain = brain
        self.memory = memory
        self.context = context
        self.skills = skills or {}
        
        # 确认回调函数
        self._confirmation_callback: Optional[Callable] = None
        
        log.info(f"ReAct 规划器初始化完成，已注册 {len(self.skills)} 个技能")
    
    def register_skill(self, name: str, skill: Any):
        """注册技能"""
        self.skills[name] = skill
        log.debug(f"已注册技能: {name}")
    
    def set_confirmation_callback(self, callback: Callable):
        """设置确认回调函数"""
        self._confirmation_callback = callback
    
    def _get_tools_schema(self) -> List[Dict]:
        """获取所有技能的 Function Calling Schema"""
        tools = []
        for name, skill in self.skills.items():
            if hasattr(skill, 'get_schema'):
                schema = skill.get_schema()
                if schema:
                    tools.append(schema)
        return tools
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        base_prompt = self.brain.get_system_prompt()
        
        # 添加上下文信息
        context_summary = self.context.get_context_summary()
        
        # 添加可用技能列表
        skill_list = []
        for name, skill in self.skills.items():
            if hasattr(skill, 'description'):
                skill_list.append(f"- {name}: {skill.description}")
        
        skills_text = "\n".join(skill_list) if skill_list else "暂无可用技能"
        
        full_prompt = f"""{base_prompt}

当前上下文信息：
{context_summary}

可用技能列表：
{skills_text}

重要提示：
1. 如果需要执行操作，请调用相应的工具函数
2. 如果任务需要多个步骤，请逐步执行并观察结果
3. 对于危险操作，系统会自动请求用户确认
4. 如果无法完成任务，请如实告知原因"""
        
        return full_prompt
    
    async def plan_and_execute(self, user_input: str) -> str:
        """
        规划并执行用户请求
        
        Args:
            user_input: 用户输入
            
        Returns:
            最终回复
        """
        log.info(f"开始处理用户请求: {user_input[:50]}...")
        
        # 添加到记忆
        self.memory.add_message("user", user_input)
        
        # 获取上下文和历史
        messages = []
        
        # 系统提示词
        messages.append({
            "role": "system",
            "content": self._build_system_prompt()
        })
        
        # 历史对话
        messages.extend(self.memory.get_recent_context())
        
        # 获取工具定义
        tools = self._get_tools_schema()
        
        # ReAct 循环
        iteration = 0
        final_response = ""
        
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            log.debug(f"ReAct 循环第 {iteration} 次")
            
            try:
                # 调用 LLM
                response = await self.brain.chat(messages, tools=tools if tools else None)
                
                # 检查是否有工具调用
                if response.get("tool_calls"):
                    # 执行工具调用
                    tool_results = await self._execute_tool_calls(response["tool_calls"])
                    
                    # 将工具调用和结果添加到消息
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False)
                                }
                            }
                            for tc in response["tool_calls"]
                        ]
                    })
                    
                    for tc, result in zip(response["tool_calls"], tool_results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False)
                        })
                    
                    # 继续循环，让 LLM 处理结果
                    continue
                
                else:
                    # 没有工具调用，直接返回回复
                    final_response = response.get("content", "")
                    break
                    
            except Exception as e:
                log.error(f"ReAct 循环出错: {e}")
                final_response = f"抱歉，处理请求时出现错误: {str(e)}"
                break
        
        if iteration >= self.MAX_ITERATIONS:
            log.warning("达到最大循环次数")
            final_response = "抱歉，任务过于复杂，无法在限定步骤内完成。"
        
        # 保存回复到记忆
        self.memory.add_message("assistant", final_response)
        
        log.info(f"请求处理完成，共 {iteration} 次循环")
        return final_response
    
    async def _execute_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """执行工具调用"""
        results = []
        
        for tc in tool_calls:
            name = tc["name"]
            arguments = tc["arguments"]
            
            log.info(f"执行工具: {name}, 参数: {arguments}")
            
            if name not in self.skills:
                results.append({
                    "success": False,
                    "error": f"未知的技能: {name}"
                })
                continue
            
            skill = self.skills[name]
            
            try:
                # 检查是否需要确认
                if hasattr(skill, 'needs_confirmation') and skill.needs_confirmation(arguments):
                    if self._confirmation_callback:
                        confirmed = await self._confirmation_callback(
                            f"是否允许执行 '{name}' 操作？\n参数: {arguments}"
                        )
                        if not confirmed:
                            results.append({
                                "success": False,
                                "error": "用户拒绝执行此操作"
                            })
                            continue
                
                # 执行技能
                result = await skill.execute(**arguments)
                
                if isinstance(result, SkillResult):
                    results.append({
                        "success": result.success,
                        "output": result.output,
                        "error": result.error
                    })
                else:
                    results.append({
                        "success": True,
                        "output": result
                    })
                    
            except Exception as e:
                log.error(f"技能执行失败: {name}, 错误: {e}")
                results.append({
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def simple_respond(self, user_input: str) -> str:
        """
        简单回复模式（不使用工具）
        
        Args:
            user_input: 用户输入
            
        Returns:
            AI 回复
        """
        self.memory.add_message("user", user_input)
        
        messages = self.memory.get_context_with_memory(user_input)
        messages.insert(0, {
            "role": "system",
            "content": self.brain.get_system_prompt()
        })
        
        response = await self.brain.chat(messages)
        reply = response.get("content", "")
        
        self.memory.add_message("assistant", reply)
        
        return reply
