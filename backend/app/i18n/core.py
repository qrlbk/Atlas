from __future__ import annotations

from fastapi import Request

SUPPORTED_LOCALES = {"en", "ru", "kk"}
DEFAULT_LOCALE = "en"

MESSAGES = {
    "en": {
        "errors.invalidCredentials": "Invalid credentials",
        "errors.couldNotValidateCredentials": "Could not validate credentials",
        "errors.insufficientPermissions": "Insufficient permissions",
        "errors.crossSchoolAccessDenied": "Cross-school access denied",
        "errors.teacherNotFound": "Teacher not found",
        "errors.classroomNotFound": "Classroom not found",
        "errors.classNotFound": "Class not found",
        "errors.groupedFlowNotFound": "Grouped flow not found",
        "errors.classNotFoundInSchool": "Class not found in this school",
        "errors.subjectNotFound": "Subject not found",
        "errors.curriculumRowNotFound": "Curriculum row not found",
        "errors.cannotChangeCurriculumSchool": "Cannot change school_id of curriculum row",
        "errors.scheduleItemNotFound": "Schedule item not found",
        "errors.teacherNotInSchool": "Teacher does not belong to this school",
        "errors.classroomNotInSchool": "Classroom does not belong to this school",
        "errors.lessonSlotNotFound": "Lesson slot not found",
        "errors.groupFlowNotInSchool": "Group flow does not belong to this school",
        "errors.scheduleGroupRequired": "Grouped lesson requires group_id",
        "errors.scheduleGroupForbidden": "Non-grouped lesson must not set group_id",
        "errors.cannotChangeEntitySchool": "Cannot change school_id of this resource",
        "errors.requestValidation": "Request validation failed",
        "errors.importInvalidModes": "Invalid import modes payload",
        "errors.importInvalidWorkbook": "Could not read the uploaded workbook",
        "errors.importEmptyFile": "Uploaded file is empty",
        "errors.importReadFailed": "Could not read the uploaded file",
        "errors.importCommitFailed": "Failed to apply the import",
        "validation.TEACHER_DOUBLE_BOOKING.message": "Teacher is busy.",
        "validation.TEACHER_DOUBLE_BOOKING.fix": "Pick another slot.",
        "validation.CLASSROOM_DOUBLE_BOOKING.message": "Room is busy.",
        "validation.CLASSROOM_DOUBLE_BOOKING.fix": "Pick another room.",
        "validation.CLASS_DOUBLE_BOOKING.message": "Class is busy.",
        "validation.CLASS_DOUBLE_BOOKING.fix": "Pick another slot.",
        "validation.TEACHER_SUBJECT_MISMATCH.message": "Wrong teacher for subject.",
        "validation.TEACHER_SUBJECT_MISMATCH.fix": "Pick another teacher.",
        "validation.ROOM_CAPACITY_EXCEEDED.message": "Room is too small.",
        "validation.ROOM_CAPACITY_EXCEEDED.fix": "Pick a bigger room.",
        "validation.SPECIAL_ROOM_MISMATCH.message": "Need special room.",
        "validation.SPECIAL_ROOM_MISMATCH.fix": "Pick a matching room.",
        "validation.GROUP_CAPACITY_EXCEEDED.message": "Group is too big.",
        "validation.GROUP_CAPACITY_EXCEEDED.fix": "Pick a bigger room.",
        "validation.TEACHER_WINDOW_DETECTED.message": "Long gap in day.",
        "validation.TEACHER_WINDOW_DETECTED.fix": "Move lessons closer.",
        "validation.TEACHER_UNAVAILABLE_DAY.message": "Teacher unavailable.",
        "validation.TEACHER_UNAVAILABLE_DAY.fix": "Pick another day.",
        "validation.TEACHER_LOAD_LIMIT_EXCEEDED.message": "Load is too high.",
        "validation.TEACHER_LOAD_LIMIT_EXCEEDED.fix": "Reduce lessons.",
        "validation.PLAN_UNDERFILLED.message": "Too few lessons.",
        "validation.PLAN_UNDERFILLED.fix": "Add lessons.",
        "validation.PLAN_OVERFLOW.message": "Too many lessons.",
        "validation.PLAN_OVERFLOW.fix": "Remove lessons.",
    },
    "ru": {},
    "kk": {},
}
MESSAGES["ru"] = MESSAGES["en"] | {
    "errors.invalidCredentials": "Неверные учетные данные",
    "errors.couldNotValidateCredentials": "Не удалось проверить учетные данные",
    "errors.insufficientPermissions": "Недостаточно прав",
    "errors.crossSchoolAccessDenied": "Доступ между школами запрещен",
    "errors.teacherNotFound": "Учитель не найден",
    "errors.classroomNotFound": "Кабинет не найден",
    "errors.classNotFound": "Класс не найден",
    "errors.groupedFlowNotFound": "Поток не найден",
    "errors.classNotFoundInSchool": "Класс не найден в этой школе",
    "errors.subjectNotFound": "Предмет не найден",
    "errors.curriculumRowNotFound": "Строка учебного плана не найдена",
    "errors.cannotChangeCurriculumSchool": "Нельзя изменить school_id строки учебного плана",
    "errors.scheduleItemNotFound": "Элемент расписания не найден",
    "errors.teacherNotInSchool": "Учитель не относится к этой школе",
    "errors.classroomNotInSchool": "Кабинет не относится к этой школе",
    "errors.lessonSlotNotFound": "Слот урока не найден",
    "errors.groupFlowNotInSchool": "Поток не относится к этой школе",
    "errors.scheduleGroupRequired": "Для группового урока нужен group_id",
    "errors.scheduleGroupForbidden": "Для обычного урока нельзя указывать group_id",
    "errors.cannotChangeEntitySchool": "Нельзя изменить school_id этого ресурса",
    "errors.requestValidation": "Ошибка валидации запроса",
    "errors.importInvalidModes": "Некорректные режимы импорта",
    "errors.importInvalidWorkbook": "Не удалось прочитать загруженный файл",
    "errors.importEmptyFile": "Загруженный файл пуст",
    "errors.importReadFailed": "Не удалось прочитать файл",
    "errors.importCommitFailed": "Не удалось применить импорт",
    "validation.TEACHER_DOUBLE_BOOKING.message": "Учитель занят.",
    "validation.TEACHER_DOUBLE_BOOKING.fix": "Выберите другой слот.",
    "validation.CLASSROOM_DOUBLE_BOOKING.message": "Кабинет занят.",
    "validation.CLASSROOM_DOUBLE_BOOKING.fix": "Выберите другой кабинет.",
    "validation.CLASS_DOUBLE_BOOKING.message": "Класс занят.",
    "validation.CLASS_DOUBLE_BOOKING.fix": "Выберите другой слот.",
    "validation.TEACHER_SUBJECT_MISMATCH.message": "Не тот учитель.",
    "validation.TEACHER_SUBJECT_MISMATCH.fix": "Выберите другого учителя.",
    "validation.ROOM_CAPACITY_EXCEEDED.message": "Кабинет мал.",
    "validation.ROOM_CAPACITY_EXCEEDED.fix": "Выберите кабинет больше.",
    "validation.SPECIAL_ROOM_MISMATCH.message": "Нужен спецкабинет.",
    "validation.SPECIAL_ROOM_MISMATCH.fix": "Выберите подходящий кабинет.",
    "validation.GROUP_CAPACITY_EXCEEDED.message": "Поток не помещается.",
    "validation.GROUP_CAPACITY_EXCEEDED.fix": "Выберите кабинет больше.",
    "validation.TEACHER_WINDOW_DETECTED.message": "Длинное окно.",
    "validation.TEACHER_WINDOW_DETECTED.fix": "Сдвиньте уроки ближе.",
    "validation.TEACHER_UNAVAILABLE_DAY.message": "Учитель недоступен.",
    "validation.TEACHER_UNAVAILABLE_DAY.fix": "Выберите другой день.",
    "validation.TEACHER_LOAD_LIMIT_EXCEEDED.message": "Нагрузка высокая.",
    "validation.TEACHER_LOAD_LIMIT_EXCEEDED.fix": "Уменьшите уроки.",
    "validation.PLAN_UNDERFILLED.message": "Мало уроков.",
    "validation.PLAN_UNDERFILLED.fix": "Добавьте уроки.",
    "validation.PLAN_OVERFLOW.message": "Много уроков.",
    "validation.PLAN_OVERFLOW.fix": "Уберите лишние.",
}
MESSAGES["kk"] = MESSAGES["en"] | {
    "errors.invalidCredentials": "Жарамсыз тіркелгі деректері",
    "errors.couldNotValidateCredentials": "Тіркелгі деректерін тексеру мүмкін болмады",
    "errors.insufficientPermissions": "Құқықтар жеткіліксіз",
    "errors.crossSchoolAccessDenied": "Мектепаралық қолжетімділікке тыйым салынған",
    "errors.teacherNotFound": "Мұғалім табылмады",
    "errors.classroomNotFound": "Кабинет табылмады",
    "errors.classNotFound": "Сынып табылмады",
    "errors.groupedFlowNotFound": "Ағын табылмады",
    "errors.classNotFoundInSchool": "Сынып осы мектептен табылмады",
    "errors.subjectNotFound": "Пән табылмады",
    "errors.curriculumRowNotFound": "Оқу жоспары жолы табылмады",
    "errors.cannotChangeCurriculumSchool": "Оқу жоспары жолының school_id мәнін өзгертуге болмайды",
    "errors.scheduleItemNotFound": "Кесте элементі табылмады",
    "errors.teacherNotInSchool": "Мұғалім осы мектепке жатпайды",
    "errors.classroomNotInSchool": "Кабинет осы мектепке жатпайды",
    "errors.lessonSlotNotFound": "Сабақ слоты табылмады",
    "errors.groupFlowNotInSchool": "Ағын осы мектепке жатпайды",
    "errors.scheduleGroupRequired": "Топтық сабақ үшін group_id қажет",
    "errors.scheduleGroupForbidden": "Қарапайым сабақта group_id болмауы керек",
    "errors.cannotChangeEntitySchool": "Бұл ресурстың school_id мәнін өзгертуге болмайды",
    "errors.requestValidation": "Сұранысты тексеру қатесі",
    "errors.importInvalidModes": "Импорт режимдері қате",
    "errors.importInvalidWorkbook": "Жүктелген файлды оқу мүмкін болмады",
    "errors.importEmptyFile": "Жүктелген файл бос",
    "errors.importReadFailed": "Файлды оқу мүмкін болмады",
    "errors.importCommitFailed": "Импортты қолдану мүмкін болмады",
    "validation.TEACHER_DOUBLE_BOOKING.message": "Мұғалім бос емес.",
    "validation.TEACHER_DOUBLE_BOOKING.fix": "Басқа слот таңдаңыз.",
    "validation.CLASSROOM_DOUBLE_BOOKING.message": "Кабинет бос емес.",
    "validation.CLASSROOM_DOUBLE_BOOKING.fix": "Басқа кабинет таңдаңыз.",
    "validation.CLASS_DOUBLE_BOOKING.message": "Сынып бос емес.",
    "validation.CLASS_DOUBLE_BOOKING.fix": "Басқа слот таңдаңыз.",
    "validation.TEACHER_SUBJECT_MISMATCH.message": "Пәнге мұғалім сәйкес емес.",
    "validation.TEACHER_SUBJECT_MISMATCH.fix": "Басқа мұғалім таңдаңыз.",
    "validation.ROOM_CAPACITY_EXCEEDED.message": "Кабинет тар.",
    "validation.ROOM_CAPACITY_EXCEEDED.fix": "Үлкен кабинет таңдаңыз.",
    "validation.SPECIAL_ROOM_MISMATCH.message": "Арнайы кабинет керек.",
    "validation.SPECIAL_ROOM_MISMATCH.fix": "Сәйкес кабинет таңдаңыз.",
    "validation.GROUP_CAPACITY_EXCEEDED.message": "Ағын сыймайды.",
    "validation.GROUP_CAPACITY_EXCEEDED.fix": "Үлкен кабинет таңдаңыз.",
    "validation.TEACHER_WINDOW_DETECTED.message": "Ұзақ терезе бар.",
    "validation.TEACHER_WINDOW_DETECTED.fix": "Сабақты жақындатыңыз.",
    "validation.TEACHER_UNAVAILABLE_DAY.message": "Мұғалім қолжетімсіз.",
    "validation.TEACHER_UNAVAILABLE_DAY.fix": "Басқа күн таңдаңыз.",
    "validation.TEACHER_LOAD_LIMIT_EXCEEDED.message": "Жүктеме жоғары.",
    "validation.TEACHER_LOAD_LIMIT_EXCEEDED.fix": "Сабақты азайтыңыз.",
    "validation.PLAN_UNDERFILLED.message": "Сабақ аз.",
    "validation.PLAN_UNDERFILLED.fix": "Сабақ қосыңыз.",
    "validation.PLAN_OVERFLOW.message": "Сабақ көп.",
    "validation.PLAN_OVERFLOW.fix": "Артықты алып тастаңыз.",
}


def resolve_locale(request: Request) -> str:
    explicit = request.headers.get("x-locale")
    if explicit in SUPPORTED_LOCALES:
        return explicit

    accept = request.headers.get("accept-language", "")
    for raw in accept.split(","):
        code = raw.split(";")[0].strip().lower()
        primary = code.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE


def t(locale: str, key: str, **params: object) -> str:
    bundle = MESSAGES.get(locale) or MESSAGES[DEFAULT_LOCALE]
    template = bundle.get(key) or MESSAGES[DEFAULT_LOCALE].get(key) or key
    if params:
        return template.format(**params)
    return template


def localize_issue(issue_code: str, locale: str, **params: object) -> tuple[str, str | None]:
    message = t(locale, f"validation.{issue_code}.message", **params)
    fix_key = f"validation.{issue_code}.fix"
    fix_text = MESSAGES.get(locale, {}).get(fix_key) or MESSAGES[DEFAULT_LOCALE].get(fix_key)
    return message, (fix_text.format(**params) if fix_text else None)
