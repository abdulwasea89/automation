from pydantic import BaseModel

class ZokoCustomer(BaseModel):
    id: str
    name: str

class ZokoWebhookPayload(BaseModel):
    customer: ZokoCustomer
    customerName: str
    deliveryStatus: str
    direction: str
    event: str
    id: str
    platform: str
    platformSenderId: str
    platformTimestamp: str
    senderName: str
    text: str = None
    type: str

class BroadcastResponse(BaseModel):
    status: str
