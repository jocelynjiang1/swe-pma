import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message, VisionBoard


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        # Check if the user is a member of the VisionBoard
        self.vision_board = await sync_to_async(VisionBoard.objects.get)(
            websocket_name=self.room_name
        )
        is_member = await sync_to_async(
            self.vision_board.members.filter(id=self.scope["user"].id).exists
        )()
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data["message"]

        user = self.scope["user"]
        message = await sync_to_async(Message.objects.create)(
            vision_board=self.vision_board, user=user, content=message_content
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message.content,
                "user": user.username,
                "timestamp": message.timestamp.strftime("%-m/%-d/%Y %-I:%M %p"),
            },
        )

    async def chat_message(self, event):
        message = event["message"]
        user = event["user"]
        timestamp = event["timestamp"]

        await self.send(
            text_data=json.dumps(
                {
                    "message": message,
                    "user": user,
                    "timestamp": timestamp,
                }
            )
        )
