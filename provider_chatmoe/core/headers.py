


from typing import Dict


def build_headers(token: str) -> Dict[str, str]:
    """构建请求头。

    Args:
        token: UUID Key（不含 "Key " 前缀）。

    Returns:
        请求头字典。
    """
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "authorization": "Key {}".format(token),
        "content-type": "application/json",
        "origin": "https://chatmoe.cn",
        "referer": "https://chatmoe.cn/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Google Chrome";v="149","Chromium";v="149","Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

__all__ = [
    "build_headers",
]
