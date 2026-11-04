"""cohere.types 桩：符号表由 cohere_llm.py 的 import 自动抽取生成。"""

class _Placeholder:
    def __init__(self, *a, **k):
        self.args, self.kwargs = a, k

class ChatbotMessage(_Placeholder): pass
class CohereMessage(_Placeholder): pass
class CohereTool(_Placeholder): pass
class CohereToolCall(_Placeholder): pass
class CohereToolResult(_Placeholder): pass
class Message(_Placeholder): pass
class Message_Chatbot(_Placeholder): pass
class Message_System(_Placeholder): pass
class Message_Tool(_Placeholder): pass
class Message_User(_Placeholder): pass
class NonStreamedChatResponse(_Placeholder): pass
class SystemMessage(_Placeholder): pass
class Tool(_Placeholder): pass
class ToolCall(_Placeholder): pass
class ToolMessage(_Placeholder): pass
class ToolParameterDefinitionsValue(_Placeholder): pass
class ToolResult(_Placeholder): pass
class UserMessage(_Placeholder): pass

def __getattr__(name):          # 任何未定义的属性都返回占位类，避免 import 期报错
    if name.startswith("__"):
        raise AttributeError(name)
    return type(name, (_Placeholder,), {})
