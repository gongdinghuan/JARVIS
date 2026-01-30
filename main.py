"""
JARVIS 智能助手 - 主入口
类似钢铁侠的 J.A.R.V.I.S. AI 助手

Author: gngdingghuan

使用方式:
    python main.py          # 命令行交互模式
    python main.py --voice  # 语音交互模式
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from config import get_config, LLMProvider
from utils.logger import log
from cognitive.llm_brain import LLMBrain
from cognitive.memory import MemoryManager
from cognitive.context_manager import ContextManager
from cognitive.planner import ReActPlanner
from skills.system_control import SystemControlSkill
from skills.file_manager import FileManagerSkill
from skills.web_browser import WebBrowserSkill
from skills.terminal import TerminalSkill
from skills.iot_bridge import IoTBridgeSkill
from expression.tts import TTS
from security.confirmation import get_confirmation_handler


console = Console()


class Jarvis:
    """
    JARVIS 主类
    整合所有模块，提供统一的交互接口
    """
    
    def __init__(self):
        self.config = get_config()
        
        # 初始化核心组件
        console.print("[cyan]正在初始化 JARVIS...[/cyan]")
        
        # 中枢层
        self.brain = LLMBrain()
        self.memory = MemoryManager()
        self.context = ContextManager()
        
        # 技能层
        self.skills = self._init_skills()
        
        # 规划器
        self.planner = ReActPlanner(
            brain=self.brain,
            memory=self.memory,
            context=self.context,
            skills=self.skills
        )
        
        # 表达层
        self.tts = TTS()
        
        # 安全层
        self.confirmation_handler = get_confirmation_handler()
        
        # 设置确认回调
        self.planner.set_confirmation_callback(self._handle_confirmation)
        
        console.print("[green]✓ JARVIS 初始化完成[/green]")
    
    def _init_skills(self) -> dict:
        """初始化所有技能"""
        skills = {}
        
        # 系统控制
        system_skill = SystemControlSkill()
        skills["system_control"] = system_skill
        
        # 文件管理
        file_skill = FileManagerSkill()
        skills["file_manager"] = file_skill
        
        # 网页浏览
        web_skill = WebBrowserSkill()
        skills["web_browser"] = web_skill
        
        # 终端命令
        terminal_skill = TerminalSkill()
        skills["terminal"] = terminal_skill
        
        # IoT 控制（如果配置了）
        if self.config.iot.enabled:
            iot_skill = IoTBridgeSkill()
            skills["iot_bridge"] = iot_skill
        
        console.print(f"[dim]已加载 {len(skills)} 个技能[/dim]")
        
        return skills
    
    async def _handle_confirmation(self, message: str) -> bool:
        """处理确认请求"""
        console.print(f"\n[yellow]⚠️  {message}[/yellow]")
        console.print("[dim]输入 y 确认，n 拒绝:[/dim]", end=" ")
        
        # 使用异步输入
        user_input = await asyncio.to_thread(input)
        
        return user_input.strip().lower() in ['y', 'yes', '是', '确认']
    
    async def process(self, user_input: str) -> str:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            AI 回复
        """
        # 更新上下文
        self.context.set_current_task(user_input[:50])
        
        # 使用规划器处理
        response = await self.planner.plan_and_execute(user_input)
        
        # 清除当前任务
        self.context.clear_current_task()
        
        return response
    
    async def speak(self, text: str):
        """语音输出"""
        await self.tts.speak(text)
    
    async def run_cli(self):
        """运行命令行交互模式"""
        self._print_welcome()
        
        while True:
            try:
                # 获取用户输入
                console.print("\n[bold cyan]You:[/bold cyan] ", end="")
                user_input = await asyncio.to_thread(input)
                
                if not user_input.strip():
                    continue
                
                # 退出命令
                if user_input.strip().lower() in ['exit', 'quit', '退出', 'bye']:
                    console.print("\n[cyan]JARVIS: 再见，Sir。[/cyan]")
                    break
                
                # 特殊命令
                if user_input.startswith('/'):
                    await self._handle_command(user_input)
                    continue
                
                # 处理请求
                console.print("\n[bold green]JARVIS:[/bold green] ", end="")
                
                response = await self.process(user_input)
                
                # 输出回复
                console.print(Markdown(response))
                
            except KeyboardInterrupt:
                console.print("\n\n[cyan]JARVIS: 收到中断信号，再见。[/cyan]")
                break
            except Exception as e:
                console.print(f"\n[red]错误: {e}[/red]")
                log.error(f"处理请求时出错: {e}")
    
    async def run_voice(self):
        """运行语音交互模式"""
        from senses.ears import Ears
        
        ears = Ears()
        
        if not ears.is_available():
            console.print("[red]语音识别不可用，请检查依赖安装[/red]")
            return
        
        self._print_welcome()
        console.print("[cyan]语音模式已启动，请说话...[/cyan]\n")
        
        await self.speak("JARVIS 已就绪，请说出您的指令。")
        
        while True:
            try:
                # 监听语音
                text = await ears.listen(timeout=10)
                
                if not text:
                    continue
                
                console.print(f"\n[bold cyan]You:[/bold cyan] {text}")
                
                # 退出命令
                if any(word in text for word in ['退出', '再见', '关闭']):
                    await self.speak("再见，Sir。")
                    break
                
                # 处理请求
                response = await self.process(text)
                
                console.print(f"\n[bold green]JARVIS:[/bold green] {response}")
                
                # 语音输出
                await self.speak(response)
                
            except KeyboardInterrupt:
                await self.speak("收到中断信号，再见。")
                break
            except Exception as e:
                console.print(f"\n[red]错误: {e}[/red]")
                log.error(f"语音模式错误: {e}")
    
    async def _handle_command(self, command: str):
        """处理特殊命令"""
        cmd = command[1:].strip().lower()
        
        if cmd == 'help':
            self._print_help()
        elif cmd == 'clear':
            self.memory.clear_short_term()
            console.print("[dim]对话记忆已清空[/dim]")
        elif cmd == 'status':
            self._print_status()
        elif cmd == 'skills':
            self._print_skills()
        elif cmd.startswith('voice '):
            voice_name = cmd[6:].strip()
            self.tts.set_voice(voice_name)
            console.print(f"[dim]语音已切换为: {voice_name}[/dim]")
        else:
            console.print(f"[yellow]未知命令: {command}[/yellow]")
    
    def _print_welcome(self):
        """打印欢迎信息"""
        welcome = """
   ╦╔═╗╦═╗╦  ╦╦╔═╗
   ║╠═╣╠╦╝╚╗╔╝║╚═╗
  ╚╝╩ ╩╩╚═ ╚╝ ╩╚═╝
        
  Just A Rather Very Intelligent System
        """
        
        console.print(Panel(
            welcome,
            title="[bold cyan]Welcome[/bold cyan]",
            border_style="cyan"
        ))
        
        console.print("[dim]输入 /help 查看帮助，输入 exit 退出[/dim]")
    
    def _print_help(self):
        """打印帮助信息"""
        help_text = """
## 可用命令

- `/help`    - 显示此帮助信息
- `/clear`   - 清空对话记忆
- `/status`  - 显示系统状态
- `/skills`  - 显示可用技能
- `/voice <name>` - 切换语音
- `exit`     - 退出程序

## 示例指令

- "打开记事本"
- "搜索今天的新闻"
- "读取桌面上的文件列表"
- "帮我创建一个笔记文件"
        """
        console.print(Markdown(help_text))
    
    def _print_status(self):
        """打印系统状态"""
        memory_stats = self.memory.get_stats()
        context = self.context.get_system_state()
        
        status = f"""
## 系统状态

- **LLM 提供商**: {self.brain.provider.value}
- **短期记忆**: {memory_stats['short_term_count']} 条
- **长期记忆**: {memory_stats['long_term_count']} 条
- **活跃窗口**: {context.get('active_window', 'N/A')}
- **CPU 使用率**: {context.get('cpu_percent', 0):.1f}%
- **内存使用率**: {context.get('memory_percent', 0):.1f}%
        """
        console.print(Markdown(status))
    
    def _print_skills(self):
        """打印可用技能"""
        console.print("\n## 可用技能\n")
        for name, skill in self.skills.items():
            console.print(f"- **{name}**: {skill.description}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='JARVIS AI Assistant')
    parser.add_argument('--voice', action='store_true', help='启用语音交互模式')
    parser.add_argument('--provider', choices=['openai', 'deepseek', 'ollama'], 
                       help='LLM 提供商')
    args = parser.parse_args()
    
    # 设置 LLM 提供商
    if args.provider:
        from config import update_config, LLMConfig, LLMProvider
        config = get_config()
        config.llm.provider = LLMProvider(args.provider)
    
    # 创建 JARVIS 实例
    jarvis = Jarvis()
    
    # 运行
    if args.voice:
        await jarvis.run_voice()
    else:
        await jarvis.run_cli()


if __name__ == "__main__":
    asyncio.run(main())
