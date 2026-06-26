import type {
  AtAGlanceSection,
  DataSheetDraft,
  GoalDraft,
  StepValidation,
  StudentSetupDraft,
  ValidationIssue,
} from "../types/projects";

export function validateStudentSetup(value: StudentSetupDraft): StepValidation {
  const issues: ValidationIssue[] = [];
  if (!value.student.name.trim()) {
    issues.push({ field: "student.name", message: "Enter the student's name." });
  }
  if (!value.student.grade.trim()) {
    issues.push({ field: "student.grade", message: "Enter the student's grade." });
  }
  if (!value.student.iep_end_date) {
    issues.push({ field: "student.iep_end_date", message: "Enter the IEP end date." });
  }
  if (!value.service_areas.some((area) => area.name.trim())) {
    issues.push({ field: "service_areas", message: "Add at least one named service area." });
  }
  return { is_complete: issues.length === 0, issues };
}

export function validateGoals(goals: readonly GoalDraft[]): StepValidation {
  const issues: ValidationIssue[] = [];
  if (!goals.length) {
    issues.push({ field: "goals", message: "Add at least one annual goal." });
  }
  const fields: readonly [keyof GoalDraft, string][] = [
    ["title", "Enter a goal title."],
    ["statement", "Enter the complete goal statement."],
    ["data_sheet_summary", "Enter a concise summary for future data sheets."],
    ["service_area_id", "Assign the goal to a service area."],
    ["mastery_criteria", "Enter mastery criteria."],
    ["progress_monitoring_method", "Enter a progress-monitoring method."],
  ];
  goals.forEach((goal, index) => {
    fields.forEach(([field, message]) => {
      const value = goal[field];
      if (value === null || !String(value).trim()) {
        issues.push({ field: `goals.${index}.${field}`, message });
      }
    });
  });
  return { is_complete: issues.length === 0, issues };
}

export function validateDataSheets(
  dataSheets: readonly DataSheetDraft[],
): StepValidation {
  const issues: ValidationIssue[] = [];
  if (!dataSheets.length) {
    issues.push({
      field: "data_sheets",
      message: "Add at least one data sheet for progress monitoring.",
    });
  }
  dataSheets.forEach((sheet, index) => {
    if (!sheet.title.trim()) {
      issues.push({ field: `data_sheets.${index}.title`, message: "Enter a data sheet title." });
    }
    if (!sheet.sheet_type) {
      issues.push({ field: `data_sheets.${index}.sheet_type`, message: "Choose a data collection type." });
    }
    if (!sheet.collection_schedule.trim()) {
      issues.push({ field: `data_sheets.${index}.collection_schedule`, message: "Enter a collection schedule." });
    }
    if (sheet.blank_instance_count < 1) {
      issues.push({
        field: `data_sheets.${index}.blank_instance_count`,
        message: "Enter at least one blank table instance for the packet.",
      });
    }
    if (!sheet.goal_ids.length) {
      issues.push({ field: `data_sheets.${index}.goal_ids`, message: "Attach at least one goal." });
    }
    if (!sheet.columns.length) {
      issues.push({ field: `data_sheets.${index}.columns`, message: "Add at least one table column." });
    }
    sheet.columns.forEach((column, columnIndex) => {
      if (!column.title.trim()) {
        issues.push({
          field: `data_sheets.${index}.columns.${columnIndex}.title`,
          message: "Enter a title for every table column.",
        });
      }
    });
  });
  return { is_complete: issues.length === 0, issues };
}

export function validateAtAGlance(
  sections: readonly AtAGlanceSection[],
): StepValidation {
  const complete = sections.some((section) => section.enabled && section.content.trim());
  return {
    is_complete: complete,
    issues: complete
      ? []
      : [
          {
            field: "at_a_glance",
            message: "Add at least one instructional summary before continuing.",
          },
        ],
  };
}
