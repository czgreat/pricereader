from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class WeChatPushMessage:
    title: str
    content: str
    target_id: str
    image_url: str | None = None
    link_url: str | None = None


class WeChatGatewayNotifier:
    def __init__(self, *, push_url: str, token: str = "", timeout: float = 10.0) -> None:
        self.push_url = push_url
        self.token = token
        self.timeout = timeout

    def build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def build_payload(self, message: WeChatPushMessage) -> dict[str, str]:
        payload = {
            "title": message.title,
            "content": message.content,
            "targetId": message.target_id,
        }
        if message.image_url:
            payload["imageUrl"] = message.image_url
        if message.link_url:
            payload["linkUrl"] = message.link_url
        return payload

    async def send(self, message: WeChatPushMessage) -> httpx.Response:
        if not self.push_url:
            raise ValueError("WeChat push URL is not configured.")
        if not message.target_id:
            raise ValueError("target_id is required for WeChat push.")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.push_url,
                headers=self.build_headers(),
                json=self.build_payload(message),
            )
            response.raise_for_status()
            return response

    def send_sync(self, message: WeChatPushMessage) -> httpx.Response:
        if not self.push_url:
            raise ValueError("WeChat push URL is not configured.")
        if not message.target_id:
            raise ValueError("target_id is required for WeChat push.")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.push_url,
                headers=self.build_headers(),
                json=self.build_payload(message),
            )
            response.raise_for_status()
            return response
