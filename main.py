from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star
from astrbot.api import logger
import httpx
import time
import numpy as np

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选实现异步插件初始化。"""

    def _build_target_session(self, source_session: str, target_user_id: str) -> str:
        """
        支持三种输入：
        1. 完整 session: aiocqhttp:FriendMessage:123456
        2. 前缀 id: f:123456 / g:987654
        3. 纯 id（默认私聊）: 123456
        """
        target_user_id = target_user_id.strip()
        if target_user_id.count(":") == 2:
            return target_user_id

        platform = source_session.split(":")[0]
        if target_user_id.startswith("g:"):
            return f"{platform}:GroupMessage:{target_user_id[2:]}"
        if target_user_id.startswith("f:"):
            return f"{platform}:FriendMessage:{target_user_id[2:]}"
        return f"{platform}:FriendMessage:{target_user_id}"

    @filter.command("sendto")
    async def send_to(self, event: AstrMessageEvent, target_user_id: str, prompt: str):
        """用于给指定目标发送 LLM 生成的消息。"""
        user_name = event.get_sender_name()
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo)

        persona_mgr = self.context.persona_manager
        persona = await persona_mgr.get_persona("小北瓜3号")
        persona_prompt = persona.system_prompt if persona else ""

        begin_prompt = "现在要给你一个人设的信息，你需要根据这个人设和提示词来生成消息。下面是人设信息：\n"
        info_prompt = (
            "\n发出请求的用户QQ名是:"
            + user_name
            + ", 这个用户请求你给另一个QQid为"
            + target_user_id
            + "的人发消息"
        )
        emph_prompt = (
            "\n你需要特别注意：\n"
            "1.你只需要根据人设和提示词来生成你准备发送的消息内容，不要回复其他内容。\n"
            "2.你可能需要根据提供的QQid来找到相应的用户信息来生成消息内容。\n"
            "3.你需要根据人设来调整消息的风格和内容。\n"
        )
        important_prompt = (
            "\n你要知道，你是在替"
            + user_name
            + "这个用户来给"
            + target_user_id
            + "这个用户(也可能是个群)发消息。"
        )
        end_prompt = "\n用户的提示词是：" + prompt
        final_prompt = (
            begin_prompt + persona_prompt + info_prompt + emph_prompt + important_prompt * 3 + end_prompt
        )

        # 调试输出（你当前在用）
        # await event.send(event.plain_result(final_prompt))

        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=final_prompt,
        )

        # await event.send(event.plain_result("发送的消息为：" + llm_resp.completion_text))

        message_chain = MessageChain().message(llm_resp.completion_text)
        target_session = self._build_target_session(umo, target_user_id)

        try:
            ok = await self.context.send_message(target_session, message_chain=message_chain)
        except Exception as e:
            logger.exception(
                f"send_message failed, target={target_user_id}, session={target_session}, err={e}"
            )
            await event.send(event.plain_result(f"发送失败：{e}"))
            return

        if not ok:
            await event.send(
                event.plain_result(f"发送失败：未找到匹配平台，target_session={target_session}")
            )
            return

        event.stop_event()

        # await event.send(event.plain_result(f"发送成功，target_session={target_session}"))

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def auto_reply(self, event: AstrMessageEvent):

        try:

            message_text = event.get_message_str() or ""

            umo = event.unified_msg_origin
            provider_id = await self.context.get_current_chat_provider_id(umo=umo)

            final_prompt =  "以下是一个男性用户的发言，你的任务根据他的发言判断他是否有喜欢男性的倾向，"
            final_prompt += "如果你认为他可能有这种倾向（有一点点可能也算！），你只需要回复一个 1， 如果没有，你只需要回复一个 0，"
            final_prompt += "注意！你应该只回复一个 0 或者 1！不要回复其他东西！\n"
            final_prompt += "以下是他的发言：" + message_text

            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=final_prompt,
            )

            if "1" in llm_resp.completion_text:
                await event.send(event.plain_result("是男生就不要找男朋友，yx除外"))

#        if "男朋友" in message_text or ("男生" in message_text and "可爱" in message_text):
#            await event.send(event.plain_result("是男生就不要找男朋友，yx除外"))
        except Exception as e:
            
            logger.exception(f"auto_reply failed, err={e}")

            if np.random.rand() < 0.1:  # 10% 的概率回复
                await event.send(event.plain_result("喵呜~"))
    
    async def terminate(self):
        """可选实现异步插件销毁。"""
