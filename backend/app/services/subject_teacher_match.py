"""Normalize subject names on teachers vs catalog subjects (solver + validation)."""


def subject_name_labels(subject_name: str) -> set[str]:
    """Case-insensitive labels for matching teacher.subjects JSON to subjects.name."""
    n = subject_name.strip().casefold()
    labels = {n}
    pe = {"physical education", "pe", "physical culture", "физкультура", "физическая культура"}
    chem = {"chemistry", "chem", "химия"}
    phys = {"physics", "phys", "физика"}
    math = {"mathematics", "math", "математика", "алгебра", "geometry", "геометрия"}
    for group in (pe, chem, phys, math):
        if n in group:
            labels |= group
    return labels


def teacher_subjects_label_set(teacher_subjects: list[str] | None) -> set[str]:
    return {str(x).strip().casefold() for x in (teacher_subjects or []) if str(x).strip()}


def teacher_covers_subject(teacher_subjects: list[str] | None, subject_name: str) -> bool:
    return bool(teacher_subjects_label_set(teacher_subjects) & subject_name_labels(subject_name))
