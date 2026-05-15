from __future__ import annotations

from io import BytesIO
from typing import Literal

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Classroom, LessonSlot, ScheduleItem, StudentClass, Subject, Teacher

ExportView = Literal["class", "teacher", "school"]
ExportFormat = Literal["xlsx", "pdf"]


def _collect_rows(db: Session, school_id: int, view: ExportView, entity_id: int | None) -> list[dict[str, object]]:
    items = list(db.scalars(select(ScheduleItem).where(ScheduleItem.school_id == school_id)))
    classes = {row.id: row.class_name for row in db.scalars(select(StudentClass).where(StudentClass.school_id == school_id))}
    teachers = {row.id: row.full_name for row in db.scalars(select(Teacher).where(Teacher.school_id == school_id))}
    rooms = {row.id: row.room_number for row in db.scalars(select(Classroom).where(Classroom.school_id == school_id))}
    subjects = {row.id: row.name for row in db.scalars(select(Subject))}
    slots = {row.id: row for row in db.scalars(select(LessonSlot))}

    if view == "class":
        if entity_id is None:
            raise ValueError("entity_id is required for class export")
        items = [item for item in items if item.class_id == entity_id]
    elif view == "teacher":
        if entity_id is None:
            raise ValueError("entity_id is required for teacher export")
        items = [item for item in items if item.teacher_id == entity_id]

    rows: list[dict[str, object]] = []
    for item in items:
        slot = slots.get(item.lesson_slot_id)
        rows.append(
            {
                "class_name": classes.get(item.class_id, f"#{item.class_id}"),
                "subject_name": subjects.get(item.subject_id, f"#{item.subject_id}"),
                "teacher_name": teachers.get(item.teacher_id, f"#{item.teacher_id}"),
                "room_number": rooms.get(item.classroom_id, f"#{item.classroom_id}"),
                "day_of_week": slot.day_of_week if slot else None,
                "lesson_number": slot.lesson_number if slot else None,
                "start_time": slot.start_time.isoformat(timespec="minutes") if slot else "",
                "end_time": slot.end_time.isoformat(timespec="minutes") if slot else "",
            }
        )
    rows.sort(key=lambda row: ((row["day_of_week"] or 0), (row["lesson_number"] or 0), str(row["class_name"])))
    return rows


def _build_xlsx(rows: list[dict[str, object]], title: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(
        [
            "Class",
            "Subject",
            "Teacher",
            "Room",
            "Day",
            "Lesson",
            "Start",
            "End",
        ]
    )
    for row in rows:
        ws.append(
            [
                row["class_name"],
                row["subject_name"],
                row["teacher_name"],
                row["room_number"],
                row["day_of_week"],
                row["lesson_number"],
                row["start_time"],
                row["end_time"],
            ]
        )
    for column_cells, width in zip(
        ("A", "B", "C", "D", "E", "F", "G", "H"),
        (18, 20, 20, 12, 8, 8, 10, 10),
        strict=True,
    ):
        ws.column_dimensions[column_cells].width = width
    ws["A1"] = f"{title} schedule export"
    payload = BytesIO()
    wb.save(payload)
    return payload.getvalue()


def _escape_pdf_text(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_minimal_pdf(rows: list[dict[str, object]], title: str) -> bytes:
    """
    A tiny self-contained PDF writer (single font, text rows only).
    Keeps dependencies minimal while still returning a valid PDF file.
    """
    lines = [title, ""] + [
        f"D{row['day_of_week']} L{row['lesson_number']} | {row['class_name']} | {row['subject_name']} | "
        f"{row['teacher_name']} | room {row['room_number']} ({row['start_time']}-{row['end_time']})"
        for row in rows
    ]
    if len(lines) == 2:
        lines.append("No schedule items found.")

    stream_parts = ["BT", "/F1 10 Tf", "36 806 Td", "14 TL"]
    first = True
    for line in lines:
        safe = _escape_pdf_text(line)
        if first:
            stream_parts.append(f"({safe}) Tj")
            first = False
        else:
            stream_parts.append(f"T* ({safe}) Tj")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def build_schedule_export(
    db: Session,
    school_id: int,
    *,
    view: ExportView,
    fmt: ExportFormat,
    entity_id: int | None = None,
) -> tuple[bytes, str, str]:
    rows = _collect_rows(db, school_id, view, entity_id)
    title = f"School {school_id} {view}"
    if fmt == "xlsx":
        payload = _build_xlsx(rows, title)
        return payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"schedule_{view}.xlsx"
    payload = _build_minimal_pdf(rows, title)
    return payload, "application/pdf", f"schedule_{view}.pdf"
