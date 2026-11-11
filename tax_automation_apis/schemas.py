
"""Pydantic schemas (request/response)"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from models import MessageStatus, TaskStatus, AccessLevel


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Auth
class LoginRequest(BaseModel):
    email: str
    password: str


# Category
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase): pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class CategoryOut(CategoryBase, ORM):
    id: int
    created_at: Optional[datetime] = None


# Staff
class StaffBase(BaseModel):
    name: str
    email: Optional[str] = None
    mobile_number: Optional[str] = None
    role: str = "Staff"
    access_level: AccessLevel = AccessLevel.LOW
    is_active: bool = True

class StaffCreate(StaffBase):
    password: Optional[str] = None

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    mobile_number: Optional[str] = None
    role: Optional[str] = None
    access_level: Optional[AccessLevel] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class StaffOut(StaffBase, ORM):
    id: int
    created_at: Optional[datetime] = None


class SwitchContextRequest(BaseModel):
    staff_id: int


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    mobile_number: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be blank or whitespace-only")
            if len(v) > 100:
                raise ValueError("Name must be 100 characters or fewer")
        return v

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) > 20:
                raise ValueError("Mobile number must be 20 characters or fewer")
        return v


class AuthMeResponse(StaffOut):
    selected_staff_id: int
    selected_staff: StaffOut
    effective_access_level: AccessLevel
    is_authenticated_high: bool = False


# Client
class ClientBase(BaseModel):
    business_name: str
    contact_name: str
    mobile_number: str
    email: Optional[str] = None
    alias_name: Optional[str] = None
    gst_details: Optional[str] = None
    pan_details: Optional[str] = None
    tan_details: Optional[str] = None
    category_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    is_active: bool = True

class ClientCreate(ClientBase):
    category_ids: List[int] = []   # many-to-many categories

class ClientUpdate(BaseModel):
    business_name: Optional[str] = None
    contact_name: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    alias_name: Optional[str] = None
    gst_details: Optional[str] = None
    pan_details: Optional[str] = None
    tan_details: Optional[str] = None
    category_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    is_active: Optional[bool] = None
    category_ids: Optional[List[int]] = None

class ClientOut(ClientBase, ORM):
    id: int
    categories: List[CategoryOut] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Compliance date
class ComplianceDateBase(BaseModel):
    category_id: int
    description: str
    due_date: date

class ComplianceDateCreate(ComplianceDateBase): pass

class ComplianceDateUpdate(BaseModel):
    category_id: Optional[int] = None
    description: Optional[str] = None
    due_date: Optional[date] = None

class ComplianceDateOut(ComplianceDateBase, ORM):
    id: int
    created_at: Optional[datetime] = None


# Invoice
class InvoiceBase(BaseModel):
    client_id: int
    invoice_number: str
    amount: Decimal
    service_type: str
    is_sent: bool = False

class InvoiceCreate(InvoiceBase): pass

class InvoiceUpdate(BaseModel):
    client_id: Optional[int] = None
    invoice_number: Optional[str] = None
    amount: Optional[Decimal] = None
    service_type: Optional[str] = None
    is_sent: Optional[bool] = None

class InvoiceOut(InvoiceBase, ORM):
    id: int
    created_at: Optional[datetime] = None


# Message history
class MessageBase(BaseModel):
    client_id: int
    message_type: str
    message_content: Optional[str] = None
    status: MessageStatus = MessageStatus.PENDING

class MessageCreate(MessageBase): pass

class MessageUpdate(BaseModel):
    message_type: Optional[str] = None
    message_content: Optional[str] = None
    status: Optional[MessageStatus] = None

class MessageOut(MessageBase, ORM):
    id: int
    sent_timestamp: Optional[datetime] = None


# Client task
class TaskBase(BaseModel):
    client_id: int
    staff_id: Optional[int] = None
    matter: str
    assigned_staff: Optional[str] = None
    date_assigned: Optional[date] = None
    due_date: Optional[date] = None
    next_followup_date: Optional[date] = None
    status: TaskStatus = TaskStatus.PENDING
    remarks: Optional[str] = None
    documents: Optional[str] = None

class TaskCreate(TaskBase): pass

class TaskUpdate(BaseModel):
    client_id: Optional[int] = None
    staff_id: Optional[int] = None
    matter: Optional[str] = None
    assigned_staff: Optional[str] = None
    date_assigned: Optional[date] = None
    due_date: Optional[date] = None
    next_followup_date: Optional[date] = None
    status: Optional[TaskStatus] = None
    remarks: Optional[str] = None
    documents: Optional[str] = None

class TaskOut(TaskBase, ORM):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
