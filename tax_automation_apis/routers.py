"""CRUD routers. A small factory covers the simple tables; clients are custom (M2M categories)."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models as m
import schemas as s
from database import get_db
from auth import get_authenticated_staff, get_effective_staff, require_high_access


def _safe_integrity_error(e: IntegrityError, default_msg: str = "Conflicting or invalid record details.") -> HTTPException:
    msg = str(e.orig) if hasattr(e, "orig") else str(e)
    if "Duplicate entry" in msg or "1062" in msg:
        return HTTPException(409, "A record with matching unique details already exists.")
    if "foreign key" in msg.lower() or "1452" in msg or "1217" in msg:
        return HTTPException(400, "Referenced record does not exist or has active dependencies.")
    if "chk_client_type" in msg or "3819" in msg:
        return HTTPException(400, "Invalid client type. Must be REGULAR or TEMP.")
    return HTTPException(409, default_msg)


def crud_router(prefix, tag, Model, Create, Update, Out, filters=()):
    r = APIRouter(prefix=prefix, tags=[tag])

    @r.get("/", response_model=List[Out])
    def list_items(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
        auth_staff = get_authenticated_staff(request, db)
        q = db.query(Model)
        if hasattr(Model, "client_id") and auth_staff.access_level != m.AccessLevel.HIGH:
            q = q.join(m.Client, Model.client_id == m.Client.id).filter(m.Client.assigned_staff_id == auth_staff.id)
        for f in filters:  # e.g. ?client_id=1&status=PENDING
            if f in request.query_params:
                q = q.filter(getattr(Model, f) == request.query_params[f])
        return q.order_by(Model.id).offset(skip).limit(limit).all()

    @r.get("/{item_id}", response_model=Out)
    def get_item(item_id: int, request: Request, db: Session = Depends(get_db)):
        auth_staff = get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        if hasattr(obj, "client_id") and auth_staff.access_level != m.AccessLevel.HIGH:
            client = db.get(m.Client, obj.client_id)
            if not client or client.assigned_staff_id != auth_staff.id:
                raise HTTPException(404, f"{tag} not found")
        return obj

    @r.post("/", response_model=Out, status_code=201)
    def create_item(request: Request, data: Create, db: Session = Depends(get_db)):
        auth_staff = get_authenticated_staff(request, db)
        if hasattr(Model, "client_id") and auth_staff.access_level != m.AccessLevel.HIGH:
            client_id = getattr(data, "client_id", None)
            client = db.get(m.Client, client_id) if client_id else None
            if not client or client.assigned_staff_id != auth_staff.id:
                raise HTTPException(404, "Client not found")
        if Model is m.MessageHistory:
            target_client = db.get(m.Client, getattr(data, "client_id", None))
            if not target_client or not target_client.mobile_number:
                raise HTTPException(400, "Cannot dispatch message: client does not have a valid mobile number.")
        obj = Model(**data.model_dump())
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _safe_integrity_error(e, f"{tag} could not be created due to conflicting data.")
        db.refresh(obj)
        return obj

    @r.patch("/{item_id}", response_model=Out)
    def update_item(item_id: int, request: Request, data: Update, db: Session = Depends(get_db)):
        auth_staff = get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        if hasattr(obj, "client_id") and auth_staff.access_level != m.AccessLevel.HIGH:
            client = db.get(m.Client, obj.client_id)
            if not client or client.assigned_staff_id != auth_staff.id:
                raise HTTPException(404, f"{tag} not found")
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _safe_integrity_error(e, f"{tag} could not be updated due to conflicting data.")
        db.refresh(obj)
        return obj

    @r.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, request: Request, db: Session = Depends(get_db)):
        auth_staff = get_authenticated_staff(request, db)
        obj = db.get(Model, item_id)
        if not obj:
            raise HTTPException(404, f"{tag} not found")
        if hasattr(obj, "client_id") and auth_staff.access_level != m.AccessLevel.HIGH:
            client = db.get(m.Client, obj.client_id)
            if not client or client.assigned_staff_id != auth_staff.id:
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
        raise _safe_integrity_error(e, "Staff member could not be created.")
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
        raise _safe_integrity_error(e, "Staff member could not be updated.")
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
        raise _safe_integrity_error(e, "Cannot delete staff member with linked records.")


# ---------- Tasks / Matters ----------
tasks = APIRouter(prefix="/tasks", tags=["Task"])


@tasks.get("/", response_model=List[s.TaskOut])
def list_tasks(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    q = db.query(m.ClientTask)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        q = q.join(m.ClientTask.client).filter(m.Client.assigned_staff_id == auth_staff.id)
    else:
        if "assigned_staff_id" in request.query_params:
            val = request.query_params["assigned_staff_id"]
            if val in ("unassigned", "null", ""):
                q = q.join(m.ClientTask.client).filter(m.Client.assigned_staff_id.is_(None))
            else:
                try:
                    q = q.join(m.ClientTask.client).filter(m.Client.assigned_staff_id == int(val))
                except ValueError:
                    pass
    for f in ("client_id", "staff_id", "status"):
        if f in request.query_params:
            q = q.filter(getattr(m.ClientTask, f) == request.query_params[f])
    return q.order_by(m.ClientTask.id).offset(skip).limit(limit).all()


@tasks.get("/{item_id}", response_model=s.TaskOut)
def get_task(item_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    obj = db.get(m.ClientTask, item_id)
    if not obj:
        raise HTTPException(404, "Task not found")
    if auth_staff.access_level != m.AccessLevel.HIGH:
        client = obj.client
        if not client or client.assigned_staff_id != auth_staff.id:
            raise HTTPException(404, "Task not found")
    return obj


@tasks.post("/", response_model=s.TaskOut, status_code=201)
def create_task(request: Request, data: s.TaskCreate, db: Session = Depends(get_db)):
    auth_staff = require_high_access(request, db)

    # Validate assigned staff member if provided
    staff_id = data.staff_id
    assigned_staff_name = data.assigned_staff
    if staff_id is not None:
        target_staff = db.get(m.Staff, staff_id)
        if not target_staff or not target_staff.is_active:
            raise HTTPException(400, "Assigned staff member does not exist or is inactive")
        if not assigned_staff_name:
            assigned_staff_name = target_staff.name

    # Workflow A: Existing Client
    if data.client_id is not None:
        client = db.get(m.Client, data.client_id)
        if not client:
            raise HTTPException(404, "Client not found")
        task_payload = data.model_dump(exclude={"new_client"})
        if assigned_staff_name:
            task_payload["assigned_staff"] = assigned_staff_name
        obj = m.ClientTask(**task_payload)
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _safe_integrity_error(e, "Task could not be created.")
        except Exception:
            db.rollback()
            raise
        db.refresh(obj)
        return obj

    # Workflow B: Inline New Client
    if data.new_client is not None:
        nc = data.new_client
        derived_contact = nc.business_name[:100]
        ct_val = nc.client_type.value if hasattr(nc.client_type, "value") else nc.client_type
        new_client_obj = m.Client(
            business_name=nc.business_name,
            contact_name=derived_contact,
            alias_name=nc.alias_name,
            mobile_number=nc.mobile_number,
            client_type=ct_val,
            assigned_staff_id=staff_id,
            is_active=True
        )
        db.add(new_client_obj)
        try:
            db.flush()  # Populates new_client_obj.id within open transaction
            task_payload = data.model_dump(exclude={"new_client", "client_id"})
            task_payload["client_id"] = new_client_obj.id
            if assigned_staff_name:
                task_payload["assigned_staff"] = assigned_staff_name
            obj = m.ClientTask(**task_payload)
            db.add(obj)
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise _safe_integrity_error(e, "Task or client could not be created.")
        except Exception:
            db.rollback()
            raise
        db.refresh(obj)
        return obj

    raise HTTPException(400, "Either client_id or new_client must be provided")


@tasks.patch("/{item_id}", response_model=s.TaskOut)
def update_task(item_id: int, request: Request, data: s.TaskUpdate, db: Session = Depends(get_db)):
    operator = get_effective_staff(request, db)

    # Section 10: Explicitly reject LOW task updates with HTTP 403
    if operator.access_level == m.AccessLevel.LOW:
        raise HTTPException(403, "LOW access level accounts have read-only permissions")
    obj = db.get(m.ClientTask, item_id)
    if not obj:
        raise HTTPException(404, "Task not found")

    changes = data.model_dump(exclude_unset=True)

    if operator.access_level != m.AccessLevel.HIGH:
        client = obj.client
        if not client or client.assigned_staff_id != operator.id:
            raise HTTPException(404, "Task not found")
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
        raise _safe_integrity_error(e, "Task could not be updated.")
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
    auth_staff = get_authenticated_staff(request, db)
    q = db.query(m.Client)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        q = q.filter(m.Client.assigned_staff_id == auth_staff.id)
    else:
        if "assigned_staff_id" in request.query_params:
            val = request.query_params["assigned_staff_id"]
            if val in ("unassigned", "null", ""):
                q = q.filter(m.Client.assigned_staff_id.is_(None))
            else:
                try:
                    q = q.filter(m.Client.assigned_staff_id == int(val))
                except ValueError:
                    pass
    if "is_active" in request.query_params:
        q = q.filter(m.Client.is_active == request.query_params["is_active"])
    if "category_id" in request.query_params:
        try:
            cat_id = int(request.query_params["category_id"])
            q = q.filter(
                or_(
                    m.Client.category_id == cat_id,
                    m.Client.categories.any(m.Category.id == cat_id)
                )
            )
        except ValueError:
            pass
    if "client_type" in request.query_params:
        ct_param = request.query_params["client_type"].strip().upper()
        if ct_param not in (m.ClientType.REGULAR.value, m.ClientType.TEMP.value):
            raise HTTPException(400, f"Invalid client_type filter: {request.query_params['client_type']}. Must be REGULAR or TEMP.")
        q = q.filter(m.Client.client_type == ct_param)
    return q.order_by(m.Client.id).offset(skip).limit(limit).all()


@clients.get("/{client_id}", response_model=s.ClientOut)
def get_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and obj.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")
    return obj


@clients.post("/", response_model=s.ClientOut, status_code=201)
def create_client(request: Request, data: s.ClientCreate, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level not in (m.AccessLevel.HIGH, m.AccessLevel.MEDIUM):
        raise HTTPException(403, "Adding clients requires HIGH or MEDIUM access level")
    payload = data.model_dump(exclude={"category_ids"})
    if "client_type" in payload and hasattr(payload["client_type"], "value"):
        payload["client_type"] = payload["client_type"].value
    if auth_staff.access_level == m.AccessLevel.MEDIUM:
        payload["assigned_staff_id"] = auth_staff.id
    elif auth_staff.access_level == m.AccessLevel.HIGH:
        if payload.get("assigned_staff_id") is not None:
            target = db.get(m.Staff, payload["assigned_staff_id"])
            if not target or not target.is_active:
                raise HTTPException(400, "Assigned staff member does not exist or is inactive")
    if data.category_ids and payload.get("category_id") is None:
        payload["category_id"] = data.category_ids[0]
    obj = m.Client(**payload)
    obj.categories = _load_categories(db, data.category_ids)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _safe_integrity_error(e, "Client could not be created due to database integrity constraints.")
    db.refresh(obj)
    return obj


@clients.patch("/{client_id}", response_model=s.ClientOut)
def update_client(client_id: int, request: Request, data: s.ClientUpdate, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        raise HTTPException(403, "Operation requires HIGH access level")
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    changes = data.model_dump(exclude_unset=True)
    if "assigned_staff_id" in changes and changes["assigned_staff_id"] is not None:
        target = db.get(m.Staff, changes["assigned_staff_id"])
        if not target or not target.is_active:
            raise HTTPException(400, "Assigned staff member does not exist or is inactive")
    ids = changes.pop("category_ids", None)
    for k, v in changes.items():
        if hasattr(v, "value"):
            v = v.value
        setattr(obj, k, v)
    if ids is not None:
        obj.categories = _load_categories(db, ids)
        if "category_id" not in changes:
            obj.category_id = ids[0] if ids else None
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _safe_integrity_error(e, "Client could not be updated due to database integrity constraints.")
    db.refresh(obj)
    return obj


@clients.patch("/{client_id}/reassign", response_model=s.ClientOut)
def reassign_client(client_id: int, request: Request, data: s.ClientReassignRequest, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level == m.AccessLevel.LOW:
        raise HTTPException(403, "LOW staff cannot reassign clients")

    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")

    if auth_staff.access_level == m.AccessLevel.MEDIUM:
        if obj.assigned_staff_id != auth_staff.id:
            raise HTTPException(404, "Client not found")
        if data.assigned_staff_id is None:
            raise HTTPException(400, "MEDIUM staff cannot clear client assignment")
        target = db.get(m.Staff, data.assigned_staff_id)
        if not target or not target.is_active:
            raise HTTPException(400, "Target staff member does not exist or is inactive")
        obj.assigned_staff_id = target.id
    elif auth_staff.access_level == m.AccessLevel.HIGH:
        if data.assigned_staff_id is not None:
            target = db.get(m.Staff, data.assigned_staff_id)
            if not target or not target.is_active:
                raise HTTPException(400, "Target staff member does not exist or is inactive")
            obj.assigned_staff_id = target.id
        else:
            obj.assigned_staff_id = None

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _safe_integrity_error(e, "Client reassignment failed due to database integrity constraints.")
    db.refresh(obj)
    return obj


@clients.delete("/{client_id}", status_code=204)
def delete_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level != m.AccessLevel.HIGH:
        raise HTTPException(403, "Operation requires HIGH access level")
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    db.delete(obj)
    db.commit()


@clients.get("/{client_id}/tasks", response_model=List[s.TaskOut])
def client_tasks(client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and obj.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")
    return db.query(m.ClientTask).filter_by(client_id=client_id).all()


@clients.get("/{client_id}/invoices", response_model=List[s.InvoiceOut])
def client_invoices(client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and obj.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")
    return db.query(m.Invoice).filter_by(client_id=client_id).all()


@clients.get("/{client_id}/messages", response_model=List[s.MessageOut])
def client_messages(client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    obj = db.get(m.Client, client_id)
    if not obj:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and obj.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")
    return db.query(m.MessageHistory).filter_by(client_id=client_id).all()


# ---------- Client Groups ----------
groups = APIRouter(prefix="/groups", tags=["Client Groups"])


def require_group_management_access(request: Request, db: Session) -> m.Staff:
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level not in (m.AccessLevel.HIGH, m.AccessLevel.MEDIUM):
        raise HTTPException(
            status_code=403,
            detail="Operation requires HIGH or MEDIUM access level"
        )
    return auth_staff


@groups.get("/", response_model=List[s.ClientGroupOut])
def list_groups(request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    if auth_staff.access_level == m.AccessLevel.HIGH:
        rows = (
            db.query(m.ClientGroup, func.count(m.Client.id).label("client_count"))
            .outerjoin(m.Client, m.Client.group_id == m.ClientGroup.id)
            .group_by(m.ClientGroup.id)
            .order_by(m.ClientGroup.name)
            .all()
        )
    else:
        rows = (
            db.query(m.ClientGroup, func.count(m.Client.id).label("client_count"))
            .outerjoin(
                m.Client,
                and_(
                    m.Client.group_id == m.ClientGroup.id,
                    m.Client.assigned_staff_id == auth_staff.id
                )
            )
            .group_by(m.ClientGroup.id)
            .order_by(m.ClientGroup.name)
            .all()
        )
    result = []
    for grp, cnt in rows:
        result.append(s.ClientGroupOut(id=grp.id, name=grp.name, client_count=cnt))
    return result


@groups.get("/{group_id}", response_model=s.ClientGroupDetailOut)
def get_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = get_authenticated_staff(request, db)
    group = db.get(m.ClientGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    visible_clients = group.clients
    if auth_staff.access_level != m.AccessLevel.HIGH:
        visible_clients = [c for c in group.clients if c.assigned_staff_id == auth_staff.id]
    return s.ClientGroupDetailOut(
        id=group.id,
        name=group.name,
        clients=[s.ClientOut.model_validate(c) for c in visible_clients]
    )


@groups.post("/", response_model=s.ClientGroupOut, status_code=201)
def create_group(request: Request, data: s.ClientGroupCreate, db: Session = Depends(get_db)):
    require_group_management_access(request, db)
    trimmed_name = data.name.strip()
    existing = db.query(m.ClientGroup).filter(func.lower(m.ClientGroup.name) == trimmed_name.lower()).first()
    if existing:
        raise HTTPException(409, "A group with this name already exists")

    obj = m.ClientGroup(name=trimmed_name)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A group with this name already exists")
    db.refresh(obj)
    return s.ClientGroupOut(id=obj.id, name=obj.name, client_count=0)


@groups.patch("/{group_id}", response_model=s.ClientGroupOut)
def rename_group(group_id: int, request: Request, data: s.ClientGroupUpdate, db: Session = Depends(get_db)):
    require_group_management_access(request, db)
    group = db.get(m.ClientGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    trimmed_name = data.name.strip()
    existing = db.query(m.ClientGroup).filter(
        func.lower(m.ClientGroup.name) == trimmed_name.lower(),
        m.ClientGroup.id != group_id
    ).first()
    if existing:
        raise HTTPException(409, "A group with this name already exists")

    group.name = trimmed_name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A group with this name already exists")
    db.refresh(group)
    cnt = db.query(m.Client).filter(m.Client.group_id == group.id).count()
    return s.ClientGroupOut(id=group.id, name=group.name, client_count=cnt)


@groups.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    require_group_management_access(request, db)
    group = db.get(m.ClientGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    db.delete(group)
    db.commit()


@groups.post("/{group_id}/clients/{client_id}", response_model=s.ClientOut)
def assign_client_to_group(group_id: int, client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = require_group_management_access(request, db)
    group = db.get(m.ClientGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    client = db.get(m.Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and client.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")

    client.group_id = group.id
    db.commit()
    db.refresh(client)
    return client


@groups.delete("/{group_id}/clients/{client_id}", response_model=s.ClientOut)
def remove_client_from_group(group_id: int, client_id: int, request: Request, db: Session = Depends(get_db)):
    auth_staff = require_group_management_access(request, db)
    group = db.get(m.ClientGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    client = db.get(m.Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    if auth_staff.access_level != m.AccessLevel.HIGH and client.assigned_staff_id != auth_staff.id:
        raise HTTPException(404, "Client not found")

    if client.group_id != group.id:
        raise HTTPException(400, "Client does not belong to this group")

    client.group_id = None
    db.commit()
    db.refresh(client)
    return client

# ---------- Matter Types ----------
matter_types = APIRouter(prefix="/matter-types", tags=["MatterType"])


@matter_types.get("/", response_model=List[s.MatterTypeOut])
def list_matter_types(request: Request, db: Session = Depends(get_db)):
    get_authenticated_staff(request, db)
    return db.query(m.MatterType).order_by(m.MatterType.name.asc()).all()


@matter_types.post("/", response_model=s.MatterTypeOut, status_code=201)
def create_matter_type(request: Request, data: s.MatterTypeCreate, db: Session = Depends(get_db)):
    require_high_access(request, db)
    norm_name = s.normalize_matter_name(data.name)
    existing = db.query(m.MatterType).filter(func.lower(m.MatterType.name) == func.lower(norm_name)).first()
    if existing:
        raise HTTPException(409, "A matter type with this name already exists")
    obj = m.MatterType(name=norm_name)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _safe_integrity_error(e, "Matter type could not be created.")
    db.refresh(obj)
    return obj


@matter_types.delete("/{item_id}", status_code=204)
def delete_matter_type(item_id: int, request: Request, db: Session = Depends(get_db)):
    require_high_access(request, db)
    obj = db.get(m.MatterType, item_id)
    if not obj:
        raise HTTPException(404, "Matter type not found")
    db.delete(obj)
    db.commit()
