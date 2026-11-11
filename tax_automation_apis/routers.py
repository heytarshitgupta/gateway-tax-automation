"""CRUD routers. A small factory covers the simple tables; clients are custom (M2M categories)."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models as m
import schemas as s
from database import get_db
from auth import get_authenticated_staff, get_effective_staff, require_high_access


def crud_router(prefix, tag, Model, Create, Update, Out, filters=()):
    r = APIRouter(prefix=prefix, tags=[tag])

    @r.get("/", response_model=List[Out])
    def list_items(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
        get_authenticated_staff(request, db)
        q = db.query(Model)
        for f in filters:  # e.g. ?client_id=1&status=PENDING
            if f in request.query_params:
                q = q.filter(getattr(Model, f) == request.query_params[f])
        return q.order_by(Model.id).offset(skip).limit(limit).all()

    @r.get("/{item_id}", response_model=Out)
    def get_item(item_id: int, request: Request, db: Session = Depends(get_db)):
        get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        return obj

    @r.post("/", response_model=Out, status_code=201)
    def create_item(request: Request, data: Create, db: Session = Depends(get_db)):
        get_authenticated_staff(request, db)
        obj = Model(**data.model_dump())
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(409, f"Integrity error: {e.orig}")
        db.refresh(obj)
        return obj

    @r.patch("/{item_id}", response_model=Out)
    def update_item(item_id: int, request: Request, data: Update, db: Session = Depends(get_db)):
        get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(409, f"Integrity error: {e.orig}")
        db.refresh(obj)
        return obj

    @r.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, request: Request, db: Session = Depends(get_db)):
        get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        db.delete(obj)
        db.commit()

    return r


categories = crud_router("/categories", "Category", m.Category, s.CategoryCreate, s.CategoryUpdate, s.CategoryOut)
compliance = crud_router("/compliance-dates", "ComplianceDate", m.ComplianceDate,
                         s.ComplianceDateCreate, s.ComplianceDateUpdate, s.ComplianceDateOut, ("category_id",))
invoices = crud_router("/invoices", "Invoice", m.Invoice, s.InvoiceCreate, s.InvoiceUpdate, s.InvoiceOut,
                       ("client_id", "is_sent"))
messages = crud_router("/messages", "Message", m.MessageHistory, s.MessageCreate, s.MessageUpdate, s.MessageOut,
                       ("client_id", "status"))

# ---------- Staff ----------
staff = APIRouter(prefix="/staff", tags=["Staff"])


@staff.get("/", response_model=List[s.StaffOut])
def list_staff(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    q = db.query(m.Staff)
    for f in ("is_active", "role"):
        if f in request.query_params:
            q = q.filter(getattr(m.Staff, f) == request.query_params[f])
    return q.order_by(m.Staff.id).offset(skip).limit(limit).all()


@staff.get("/{item_id}", response_model=s.StaffOut)
def get_staff(item_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    obj = db.get(m.Staff, item_id)
    if not obj:
        raise HTTPException(404, "Staff not found")
    return obj


@staff.post("/", response_model=s.StaffOut, status_code=201)
def create_staff(request: Request, data: s.StaffCreate, db: Session = Depends(get_db)):
    require_high_access(request, db)

    # Validate email
    if not data.email or not data.email.strip():
        raise HTTPException(400, "Email is required for new staff member")
    email = data.email.strip().lower()

    # Check email uniqueness (case-insensitive)
    existing = db.query(m.Staff).filter(func.lower(m.Staff.email) == email).first()
    if existing:
        raise HTTPException(409, "Email is already registered")

    # Validate password
    if not data.password or not data.password.strip():
        raise HTTPException(400, "Password is required for new staff member")

    payload = data.model_dump()
    payload["email"] = email
    payload["password"] = data.password.strip()

    obj = m.Staff(**payload)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@staff.patch("/{item_id}", response_model=s.StaffOut)
def update_staff(item_id: int, request: Request, data: s.StaffUpdate, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.Staff, item_id)
    if not obj:
        raise HTTPException(404, "Staff not found")

    changes = data.model_dump(exclude_unset=True)

    # Last active HIGH protection
    if obj.access_level == m.AccessLevel.HIGH and obj.is_active:
        will_demote = "access_level" in changes and changes["access_level"] != m.AccessLevel.HIGH
        will_deactivate = "is_active" in changes and not changes["is_active"]
        if will_demote or will_deactivate:
            active_high_count = db.query(m.Staff).filter(
                m.Staff.access_level == m.AccessLevel.HIGH,
                m.Staff.is_active == True
            ).count()
            if active_high_count <= 1:
                raise HTTPException(400, "Cannot demote or deactivate the last active HIGH staff member")

    for k, v in changes.items():
        setattr(obj, k, v)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@staff.delete("/{item_id}", status_code=204)
def delete_staff(item_id: int, request: Request, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.Staff, item_id)
    if not obj:
        raise HTTPException(404, "Staff not found")

    # Last active HIGH protection
    if obj.access_level == m.AccessLevel.HIGH and obj.is_active:
        active_high_count = db.query(m.Staff).filter(
            m.Staff.access_level == m.AccessLevel.HIGH,
            m.Staff.is_active == True
        ).count()
        if active_high_count <= 1:
            raise HTTPException(400, "Cannot delete the last active HIGH staff member")

    db.delete(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")


# ---------- Tasks / Matters ----------
tasks = APIRouter(prefix="/tasks", tags=["Task"])


@tasks.get("/", response_model=List[s.TaskOut])
def list_tasks(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    q = db.query(m.ClientTask)
    for f in ("client_id", "staff_id", "status"):
        if f in request.query_params:
            q = q.filter(getattr(m.ClientTask, f) == request.query_params[f])
    return q.order_by(m.ClientTask.id).offset(skip).limit(limit).all()


@tasks.get("/{item_id}", response_model=s.TaskOut)
def get_task(item_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    obj = db.get(m.ClientTask, item_id)
    if not obj:
        raise HTTPException(404, "Task not found")
    return obj


@tasks.post("/", response_model=s.TaskOut, status_code=201)
def create_task(request: Request, data: s.TaskCreate, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = m.ClientTask(**data.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@tasks.patch("/{item_id}", response_model=s.TaskOut)
def update_task(item_id: int, request: Request, data: s.TaskUpdate, db: Session = Depends(get_db)):
    operator = get_effective_staff(request, db)
    obj = db.get(m.ClientTask, item_id)
    if not obj:
        raise HTTPException(404, "Task not found")

    changes = data.model_dump(exclude_unset=True)

    if operator.access_level != m.AccessLevel.HIGH:
        # MEDIUM and LOW access rules:
        if obj.staff_id is None:
            raise HTTPException(403, "Unassigned matters can only be modified by HIGH staff")
        if obj.staff_id != operator.id:
            raise HTTPException(403, "Cannot modify matters assigned to another staff member")
        if "staff_id" in changes and changes["staff_id"] != obj.staff_id:
            raise HTTPException(403, "Cannot reassign matters")
        if "assigned_staff" in changes and changes["assigned_staff"] != obj.assigned_staff:
            raise HTTPException(403, "Cannot reassign matters")
        if "client_id" in changes and changes["client_id"] != obj.client_id:
            raise HTTPException(403, "Cannot change a matter's client association")

    for k, v in changes.items():
        setattr(obj, k, v)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@tasks.delete("/{item_id}", status_code=204)
def delete_task(item_id: int, request: Request, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.ClientTask, item_id)
    if not obj:
        raise HTTPException(404, "Task not found")
    db.delete(obj)
    db.commit()


# ---------- Clients (custom) ----------
clients = APIRouter(prefix="/clients", tags=["Client"])


def _load_categories(db: Session, ids: List[int]):
    cats = db.query(m.Category).filter(m.Category.id.in_(ids)).all() if ids else []
    if len(cats) != len(set(ids)):
        raise HTTPException(400, "One or more category_ids do not exist")
    return cats


@clients.get("/", response_model=List[s.ClientOut])
def list_clients(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    q = db.query(m.Client)
    for f in ("is_active", "category_id", "assigned_staff_id"):
        if f in request.query_params:
            q = q.filter(getattr(m.Client, f) == request.query_params[f])
    return q.order_by(m.Client.id).offset(skip).limit(limit).all()


@clients.get("/{client_id}", response_model=s.ClientOut)
def get_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    return obj


@clients.post("/", response_model=s.ClientOut, status_code=201)
def create_client(request: Request, data: s.ClientCreate, db: Session = Depends(get_db)):
    operator = get_effective_staff(request, db)
    if operator.access_level not in (m.AccessLevel.HIGH, m.AccessLevel.MEDIUM):
        raise HTTPException(403, "Adding clients requires HIGH or MEDIUM access level")
    payload = data.model_dump(exclude={"category_ids"})
    obj = m.Client(**payload)
    obj.categories = _load_categories(db, data.category_ids)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@clients.patch("/{client_id}", response_model=s.ClientOut)
def update_client(client_id: int, request: Request, data: s.ClientUpdate, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    changes = data.model_dump(exclude_unset=True)
    ids = changes.pop("category_ids", None)
    for k, v in changes.items():
        setattr(obj, k, v)
    if ids is not None:
        obj.categories = _load_categories(db, ids)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, f"Integrity error: {e.orig}")
    db.refresh(obj)
    return obj


@clients.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    db.delete(obj)
    db.commit()


@clients.get("/{client_id}/tasks", response_model=List[s.TaskOut])
def client_tasks(client_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    return db.query(m.ClientTask).filter_by(client_id=client_id).all()


@clients.get("/{client_id}/invoices", response_model=List[s.InvoiceOut])
def client_invoices(client_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    return db.query(m.Invoice).filter_by(client_id=client_id).all()


@clients.get("/{client_id}/messages", response_model=List[s.MessageOut])
def client_messages(client_id: int, request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    return db.query(m.MessageHistory).filter_by(client_id=client_id).all()
