"""
JARVIS 网页浏览技能
搜索、读取网页内容

Author: gngdingghuan
"""

import re
from typing import Dict, Any, Optional, List

import httpx

from skills.base_skill import BaseSkill, SkillResult, PermissionLevel, create_tool_schema
from utils.logger import log
from utils.platform_utils import open_url_in_browser

# DuckDuckGo 搜索
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


class WebBrowserSkill(BaseSkill):
    """网页浏览技能"""
    
    name = "web_browser"
    description = "网页浏览：搜索信息、读取网页内容、打开URL"
    permission_level = PermissionLevel.READ_ONLY
    
    def __init__(self):
        super().__init__()
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    async def execute(self, action: str, **params) -> SkillResult:
        """执行网页操作"""
        actions = {
            "search": self._search,
            "read_webpage": self._read_webpage,
            "open_url": self._open_url,
            "get_weather": self._get_weather,
        }
        
        if action not in actions:
            return SkillResult(success=False, output=None, error=f"未知的操作: {action}")
        
        try:
            result = await actions[action](**params)
            return result
        except Exception as e:
            log.error(f"网页操作失败: {action}, 错误: {e}")
            return SkillResult(success=False, output=None, error=str(e))
    
    async def _search(self, query: str, max_results: int = 5) -> SkillResult:
        """搜索信息"""
        if not DDGS_AVAILABLE:
            return SkillResult(
                success=False,
                output=None,
                error="搜索功能需要安装 duckduckgo-search 库"
            )
        
        log.info(f"搜索: {query}")
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return SkillResult(
                    success=True,
                    output={"message": "未找到相关结果", "results": []}
                )
            
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            
            return SkillResult(
                success=True,
                output={
                    "query": query,
                    "count": len(formatted_results),
                    "results": formatted_results
                }
            )
            
        except Exception as e:
            return SkillResult(success=False, output=None, error=f"搜索失败: {e}")
    
    async def _read_webpage(self, url: str) -> SkillResult:
        """读取网页内容（提取文本）"""
        log.info(f"读取网页: {url}")
        
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            
            html = response.text
            
            # 简单的 HTML 清理
            text = self._extract_text(html)
            
            # 限制长度
            if len(text) > 5000:
                text = text[:5000] + "...(内容已截断)"
            
            return SkillResult(
                success=True,
                output={
                    "url": url,
                    "status_code": response.status_code,
                    "content": text
                }
            )
            
        except httpx.HTTPError as e:
            return SkillResult(success=False, output=None, error=f"HTTP 错误: {e}")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
    
    def _extract_text(self, html: str) -> str:
        """从 HTML 提取纯文本"""
        # 移除 script 和 style 标签
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除所有 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # 清理空白字符
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # 解码 HTML 实体
        import html as html_module
        text = html_module.unescape(text)
        
        return text
    
    async def _open_url(self, url: str) -> SkillResult:
        """在浏览器中打开 URL"""
        log.info(f"打开 URL: {url}")
        
        success = open_url_in_browser(url)
        if success:
            return SkillResult(success=True, output=f"已在浏览器中打开: {url}")
        else:
            return SkillResult(success=False, output=None, error="无法打开浏览器")
    
    async def _get_weather(self, city: str = "北京") -> SkillResult:
        """获取天气信息（通过搜索）"""
        query = f"{city}天气"
        return await self._search(query, max_results=3)
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
    
    def get_schema(self) -> Dict[str, Any]:
        """获取 Function Calling Schema"""
        return create_tool_schema(
            name="web_browser",
            description="网页浏览操作：搜索信息、读取网页内容、打开URL、查询天气",
            parameters={
                "action": {
                    "type": "string",
                    "enum": ["search", "read_webpage", "open_url", "get_weather"],
                    "description": "要执行的操作类型"
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词（用于 search）"
                },
                "url": {
                    "type": "string",
                    "description": "网页 URL（用于 read_webpage, open_url）"
                },
                "city": {
                    "type": "string",
                    "description": "城市名称（用于 get_weather）"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数量（用于 search）"
                }
            },
            required=["action"]
        )
