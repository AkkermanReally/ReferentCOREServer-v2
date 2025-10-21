# rcs/nucleus/protocol.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime, timezone
import uuid


def new_message_id() -> str:
    """Generates a new unique message ID in the format 'msg_uuid'."""
    return f"msg_{uuid.uuid4()}"


class Envelope(BaseModel):
    """
    The standard 'envelope' model for the Persona Synchronization Protocol (PSP) v1.2.
    This is the single, canonical version for the entire Persona ecosystem.
    It defines the immutable contract for data exchange.
    """

    psp_version: str = Field(default="1.2", frozen=True, description="The version of the PSP protocol.")
    message_id: str = Field(default_factory=new_message_id, description="A unique identifier for the message.")
    session_id: Optional[str] = Field(None, description="An identifier for a user session or a multi-step process.")

    type: Literal[
        "command",
        "response",
        "event",
        "error",
        "handshake",
        "secrets",
        "handshake_confirmed",
        "module_registration", # For clients to register themselves
        "error_manifest_registration",
    ] = Field(..., description="The type of the message, determining its purpose.")

    return_from: str = Field(..., description="The name of the component sending the message.")
    return_to: Optional[str] = Field(None, description="The name of the intended recipient component.")

    request_id: Optional[str] = Field(None, description="If this is a response or error, the message_id of the original request.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The UTC timestamp of when the message was created."
    )

    payload: Dict[str, Any] = Field(..., description="A dictionary containing the actual data of the message.")
