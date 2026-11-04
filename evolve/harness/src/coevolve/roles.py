"""按任务把工具分成 read / act / report 三类角色（守卫按角色绑定，而不是按全局前缀清单）。

动机：AutoControl 的 70 个 spec 用的是各场景真实工具名，全局前缀清单匹配不到 → 大量"未测到"。
改成"每个任务自己声明角色"后，同一机制的守卫能在每个任务上自动落地。
"""
from __future__ import annotations

READ_PREFIX = ("read", "get", "list", "check", "status", "observe", "inspect", "query",
               "view", "search", "download", "preview", "review", "fetch", "lookup")
REPORT_PREFIX = ("report", "submit", "publish", "notify", "alert", "file_", "log_",
                 "record", "upload", "post", "share", "send")


def classify_tools(tools) -> dict:
    """read = 只读类；act = 所有非只读（**有副作用即可**，含 send/post/share）；
    report = act 里的"对外提交/通知"子集（供其它守卫使用）。"""
    read = [str(t) for t in tools if str(t).startswith(READ_PREFIX)]
    act = [str(t) for t in tools if str(t) not in read]
    report = [t for t in act if t.startswith(REPORT_PREFIX)]
    return {"read": read, "report": report, "act": act}


def role_of(tool: str, roles: dict) -> str:
    for role in ("read", "report", "act"):
        if tool in roles.get(role, []):
            return role
    return "act"
