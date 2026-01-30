"""
JARVIS 技能基类
定义技能的统一接口

Author: gngdingghuan
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class PermissionLevel(Enum):
    """权限级别"""
    READ_ONLY = 1      # 只读，自动执行
    SAFE_WRITE = 2     # 安全写入，自动执行但记录
    CRITICAL = 3       # 危险操作，需要确认


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error
        }


class BaseSkill(ABC):
    """
    技能基类
    所有技能必须继承此类
    """
    
    # 子类必须定义这些属性
    name: str = "base_skill"
    description: str = "基础技能"
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    
    def __init__(self):
        pass
    
    @abstractmethod
    async def execute(self, **params) -> SkillResult:
        """
        执行技能
        
        Args:
            **params: 技能参数
            
        Returns:
            SkillResult 执行结果
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        获取 Function Calling Schema
        
        Returns:
            OpenAI 格式的工具定义
        """
        pass
    
    def needs_confirmation(self, params: Dict[str, Any]) -> bool:
        """
        检查是否需要用户确认
        
        Args:
            params: 执行参数
            
        Returns:
            是否需要确认
        """
        return self.permission_level == PermissionLevel.CRITICAL
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        验证参数
        
        Args:
            params: 执行参数
            
        Returns:
            错误信息，None 表示验证通过
        """
        return None
    
    def __repr__(self) -> str:
        return f"<Skill: {self.name}>"


def create_tool_schema(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    required: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    创建 OpenAI Function Calling 格式的工具定义
    
    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数定义
        required: 必需参数列表
        
    Returns:
        工具定义字典
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required or []
            }
        }
    }
