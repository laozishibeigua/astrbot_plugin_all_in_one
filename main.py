from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star
from astrbot.api import logger
import httpx
import time

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
        message_text = event.get_message_str() or ""
        if "男朋友" in message_text or ("男生" in message_text and "可爱" in message_text):
            await event.send(event.plain_result("是男生就不要找男朋友，yx除外"))
    

    def get_cf_contest_info(self):
        cf_contest_request = httpx.get("https://codeforces.com/api/contest.list?gym=false")
        
        if cf_contest_request.status_code != 200:
            return "小北瓜查不到欸，是不是CF又爆炸了？"
        
        cf_contest_result  = cf_contest_request.json()

        if cf_contest_result["status"] != "OK":
            return "小北瓜查不到欸，是不是CF又爆炸了？"
        
        contests_info = [] # not all string 
        contest_result_recent5 = cf_contest_result["result"][:5][::-1] # get first 5 contest and reverse

        for contest_result in contest_result_recent5:
            if contest_result["phase"] == "finished":
                continue
            contest_info = []
            contest_info.append(contest_result["name"])
            contest_info.append(contest_result["startTimeSeconds"])
            contest_info.append(contest_result["durationSeconds"])
            contests_info.append(contest_info)

        final_cf_contest_info = ""

        for contest_info in contests_info:
            final_cf_contest_info +=  "--------------------\n"
            final_cf_contest_info += contest_info[0] + "\n"
            final_cf_contest_info += "开始时间：" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(contest_info[1])) + "\n"
            final_cf_contest_info += "持续时间：" + str(contest_info[2] // 3600) + "小时" + (str(contest_info[2] % 3600 // 60) + "分钟" if contest_info[2] % 3600 != 0 else "") + "\n"
        return final_cf_contest_info

    def get_atc_contest_info(self):
        pass 
    
    @filter.command("cpcquery")
    async def cpc_query(self, event: AstrMessageEvent):

        cf_context_info = self.get_cf_contest_info()
        
        final_message =  "即将到来的比赛：\n"
        final_message += "CodeForces:\n"
        final_message += cf_context_info

        await event.send(event.plain_result(final_message))


    async def terminate(self):
        """可选实现异步插件销毁。"""
