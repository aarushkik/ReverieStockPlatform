/**
 * MarketLens feedback system
 *
 * Run setupFeedbackSystem() once from a standalone Google Apps Script project.
 * It creates:
 *   1. A detailed Google Form for product feedback.
 *   2. A linked Google Sheet containing all responses and artifact URLs.
 *   3. A Google Doc that presents the feedback and a prioritized action plan.
 *   4. An installable trigger that refreshes the report after every submission.
 */

const CONFIG = Object.freeze({
  productName: 'MarketLens',
  productDescription:
    'A stock-market research platform with live quotes, charts, screeners, ' +
    'technical analysis, paper trading, security controls, and an AI copilot.',
  minimumReviewers: 3,
  detailMinimumCharacters: 100,
  propertyKeys: Object.freeze({
    formId: 'REVERIE_FEEDBACK_FORM_ID',
    spreadsheetId: 'REVERIE_FEEDBACK_SHEET_ID',
    reportId: 'REVERIE_FEEDBACK_REPORT_ID',
  }),
});

const QUESTIONS = Object.freeze({
  name: 'Reviewer name',
  audience: 'Which description best matches you?',
  experience: 'How experienced are you with investing or market-research tools?',
  task: 'What did you try to accomplish with MarketLens?',
  worked: 'What worked well, and why was it useful?',
  grievance: 'What was confusing, frustrating, missing, or unreliable?',
  evidence: 'Describe exactly what happened and how it affected your experience.',
  improvement: 'What specific change would improve the product most?',
  impact: 'How much did the issue affect your ability to complete your task?',
  feature: 'Which product area most needs attention?',
  rating: 'Optional overall rating (the written feedback matters more)',
  followUp: 'May the project team contact you for a follow-up?',
});

/** Creates the complete feedback system. Run this function once. */
function setupFeedbackSystem() {
  const spreadsheet = SpreadsheetApp.create(
    CONFIG.productName + ' — Feedback Responses'
  );
  prepareOverviewSheet_(spreadsheet);

  const form = buildFeedbackForm_();
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());

  const report = DocumentApp.create(
    CONFIG.productName + ' — Feedback Findings & Action Plan'
  );

  const properties = PropertiesService.getScriptProperties();
  properties.setProperties({
    [CONFIG.propertyKeys.formId]: form.getId(),
    [CONFIG.propertyKeys.spreadsheetId]: spreadsheet.getId(),
    [CONFIG.propertyKeys.reportId]: report.getId(),
  });

  writeArtifactLinks_(spreadsheet, form, report);
  replaceSubmissionTrigger_(form);
  refreshFeedbackReport();

  const links = {
    responderForm: form.getPublishedUrl(),
    editForm: form.getEditUrl(),
    responses: spreadsheet.getUrl(),
    report: report.getUrl(),
  };

  Logger.log('Setup complete:\n' + JSON.stringify(links, null, 2));
  return links;
}

/** Runs automatically after each response. You may also run it manually. */
function onFeedbackSubmit(event) {
  // The lock prevents simultaneous submissions from editing the Doc at once.
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    refreshFeedbackReport();
  } finally {
    lock.releaseLock();
  }
}

/** Rebuilds the shareable findings document from all current form responses. */
function refreshFeedbackReport() {
  const resources = getResources_();
  const reviews = resources.form.getResponses().map(normalizeResponse_);
  const categories = summarizeCategories_(reviews);
  renderReport_(resources.report, reviews, categories, resources);
  updateOverview_(resources.spreadsheet, reviews.length, resources);

  Logger.log(
    'Report refreshed with ' + reviews.length + ' review(s): ' +
      resources.report.getUrl()
  );
  return resources.report.getUrl();
}

/** Logs the URLs again if you lose them. */
function showFeedbackSystemLinks() {
  const resources = getResources_();
  const links = {
    responderForm: resources.form.getPublishedUrl(),
    editForm: resources.form.getEditUrl(),
    responses: resources.spreadsheet.getUrl(),
    report: resources.report.getUrl(),
  };
  Logger.log(JSON.stringify(links, null, 2));
  return links;
}

function buildFeedbackForm_() {
  const form = FormApp.create(
    CONFIG.productName + ' — Product Feedback',
    true
  );

  form
    .setDescription(
      'Help us improve ' + CONFIG.productName + '.\n\n' +
        CONFIG.productDescription + '\n\n' +
        'Please test the product before responding. Concrete examples matter ' +
        'more than the numeric rating. Detailed answers will be shared with ' +
        'the project team and judges.'
    )
    .setConfirmationMessage(
      'Thank you. Your detailed feedback has been recorded and will be used ' +
        'to prioritize product improvements.'
    )
    .setProgressBar(true)
    .setShuffleQuestions(false)
    .setAcceptingResponses(true);

  form.addSectionHeaderItem()
    .setTitle('About the reviewer')
    .setHelpText(
      'This identifies the target audience represented by each review.'
    );

  form.addTextItem()
    .setTitle(QUESTIONS.name)
    .setHelpText('Use your real name or a consistent identifier.')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(QUESTIONS.audience)
    .setChoiceValues([
      'Student learning about investing',
      'Beginner or casual investor',
      'Active retail investor or trader',
      'Finance, data, or software professional',
      'Educator, mentor, or project judge',
      'Other',
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(QUESTIONS.experience)
    .setChoiceValues([
      'None — this is new to me',
      'Beginner',
      'Intermediate',
      'Advanced',
      'Professional',
    ])
    .setRequired(true);

  form.addPageBreakItem()
    .setTitle('Your test session')
    .setHelpText(
      'Describe what you actually attempted so the feedback has context.'
    );

  addDetailedQuestion_(form, QUESTIONS.task,
    'Mention the feature(s), ticker(s), and goal you pursued.');
  addDetailedQuestion_(form, QUESTIONS.worked,
    'Identify specific screens, information, interactions, or outcomes.');

  form.addPageBreakItem()
    .setTitle('Grievances and evidence')
    .setHelpText(
      'Be candid and precise. Explain the problem, not only whether you liked it.'
    );

  addDetailedQuestion_(form, QUESTIONS.grievance,
    'Name the exact feature or step and explain why it was a problem.');
  addDetailedQuestion_(form, QUESTIONS.evidence,
    'Include what you expected, what occurred, and whether you could recover.');
  addDetailedQuestion_(form, QUESTIONS.improvement,
    'Propose a concrete behavior, wording, layout, or feature change.');

  form.addMultipleChoiceItem()
    .setTitle(QUESTIONS.impact)
    .setChoiceValues([
      'Blocked me from completing the task',
      'Major friction — I completed it only with difficulty',
      'Minor friction — I could continue',
      'No meaningful issue',
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(QUESTIONS.feature)
    .setChoiceValues([
      'Getting started / sign-in',
      'Navigation / information architecture',
      'Visual design / readability / accessibility',
      'Quotes / charts / market-data accuracy',
      'Research / technical analysis',
      'Paper trading / order entry',
      'AI copilot',
      'Speed / reliability',
      'Security / privacy / trust',
      'Missing feature / other',
    ])
    .setRequired(true);

  form.addScaleItem()
    .setTitle(QUESTIONS.rating)
    .setBounds(1, 5)
    .setLabels('Needs substantial work', 'Excellent')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle(QUESTIONS.followUp)
    .setChoiceValues(['Yes', 'No'])
    .setRequired(true);

  return form;
}

function addDetailedQuestion_(form, title, helpText) {
  const validation = FormApp.createParagraphTextValidation()
    .setHelpText(
      'Please provide at least ' + CONFIG.detailMinimumCharacters +
        ' characters of specific detail.'
    )
    .requireTextLengthGreaterThanOrEqualTo(CONFIG.detailMinimumCharacters)
    .build();

  form.addParagraphTextItem()
    .setTitle(title)
    .setHelpText(helpText)
    .setValidation(validation)
    .setRequired(true);
}

function normalizeResponse_(formResponse) {
  const answers = {};
  formResponse.getItemResponses().forEach(function(itemResponse) {
    const value = itemResponse.getResponse();
    answers[itemResponse.getItem().getTitle()] = Array.isArray(value)
      ? value.join(', ')
      : String(value || '');
  });

  return {
    timestamp: formResponse.getTimestamp(),
    name: answers[QUESTIONS.name] || 'Anonymous reviewer',
    audience: answers[QUESTIONS.audience] || 'Not provided',
    experience: answers[QUESTIONS.experience] || 'Not provided',
    task: answers[QUESTIONS.task] || '',
    worked: answers[QUESTIONS.worked] || '',
    grievance: answers[QUESTIONS.grievance] || '',
    evidence: answers[QUESTIONS.evidence] || '',
    improvement: answers[QUESTIONS.improvement] || '',
    impact: answers[QUESTIONS.impact] || 'No meaningful issue',
    feature: answers[QUESTIONS.feature] || 'Missing feature / other',
    rating: answers[QUESTIONS.rating] || 'Not provided',
    followUp: answers[QUESTIONS.followUp] || 'No',
  };
}

function summarizeCategories_(reviews) {
  const groups = {};

  reviews.forEach(function(review) {
    const category = review.feature;
    if (!groups[category]) {
      groups[category] = {
        category: category,
        count: 0,
        totalImpact: 0,
        grievances: [],
        suggestions: [],
      };
    }

    groups[category].count += 1;
    groups[category].totalImpact += impactScore_(review.impact);
    groups[category].grievances.push(review.grievance);
    groups[category].suggestions.push(review.improvement);
  });

  return Object.keys(groups)
    .map(function(key) {
      const group = groups[key];
      group.priorityScore = group.totalImpact + group.count;
      group.priority = priorityLabel_(group.priorityScore);
      return group;
    })
    .sort(function(a, b) {
      return b.priorityScore - a.priorityScore || b.count - a.count;
    });
}

function impactScore_(impact) {
  if (impact.indexOf('Blocked') === 0) return 4;
  if (impact.indexOf('Major') === 0) return 3;
  if (impact.indexOf('Minor') === 0) return 2;
  return 1;
}

function priorityLabel_(score) {
  if (score >= 10) return 'P0 — address immediately';
  if (score >= 7) return 'P1 — next iteration';
  if (score >= 4) return 'P2 — planned improvement';
  return 'P3 — monitor';
}

function actionForCategory_(category) {
  const actions = {
    'Getting started / sign-in':
      'Simplify first-run guidance, clarify account creation, and test recovery/error states.',
    'Navigation / information architecture':
      'Rework labels and hierarchy around reviewers’ stated tasks; validate with a short task-based usability test.',
    'Visual design / readability / accessibility':
      'Audit contrast, type scale, spacing, focus order, and keyboard/screen-reader behavior; correct failed checks.',
    'Quotes / charts / market-data accuracy':
      'Reproduce the reported symbols and time ranges, expose data freshness/source, and add empty/error-state checks.',
    'Research / technical analysis':
      'Clarify metric definitions and assumptions, verify calculations, and add explanations near complex outputs.',
    'Paper trading / order entry':
      'Review the order flow, add clear validation and confirmation, and test balances, quantities, and failure cases.',
    'AI copilot':
      'Evaluate the reported prompts, improve grounding and uncertainty language, and add source/limitation cues.',
    'Speed / reliability':
      'Profile the affected path, cache safe repeated work, add timeout/error handling, and measure before/after latency.',
    'Security / privacy / trust':
      'Review the reported trust concern, explain data use plainly, minimize retained data, and test security controls.',
    'Missing feature / other':
      'Convert the request into a scoped user story, compare its value with effort, and prototype before full implementation.',
  };
  return actions[category] || actions['Missing feature / other'];
}

function acceptanceCriteriaForCategory_(category) {
  const common =
    'Retest the same reviewer task with at least one target user; the issue should no longer block completion.';
  if (category === 'Speed / reliability') {
    return common + ' Record a measurable reduction in load time or failure rate.';
  }
  if (category === 'Quotes / charts / market-data accuracy') {
    return common + ' Confirm values against the named source and display freshness.';
  }
  if (category === 'Visual design / readability / accessibility') {
    return common + ' Pass keyboard, focus, and contrast checks on the affected screen.';
  }
  return common;
}

function renderReport_(doc, reviews, categories, resources) {
  const body = doc.getBody();
  body.clear();

  body.appendParagraph(CONFIG.productName + ' Feedback Findings & Action Plan')
    .setHeading(DocumentApp.ParagraphHeading.TITLE);
  body.appendParagraph(
    'Last refreshed: ' + Utilities.formatDate(
      new Date(), Session.getScriptTimeZone(), 'MMMM d, yyyy h:mm a'
    )
  );
  body.appendParagraph(CONFIG.productDescription);

  const requirementMet = reviews.length >= CONFIG.minimumReviewers;
  body.appendParagraph('Review requirement')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  const statusParagraph = body.appendParagraph(
    (requirementMet ? 'MET' : 'NOT YET MET') + ': ' + reviews.length +
      ' of at least ' + CONFIG.minimumReviewers + ' detailed reviews collected.'
  );
  statusParagraph.editAsText()
    .setBold(true)
    .setForegroundColor(requirementMet ? '#137333' : '#B3261E');

  body.appendParagraph('Audience represented')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  if (!reviews.length) {
    body.appendParagraph('No responses yet. Share the form with at least three reviewers.');
  } else {
    countValues_(reviews, 'audience').forEach(function(row) {
      body.appendListItem(row.label + ': ' + row.count)
        .setGlyphType(DocumentApp.GlyphType.BULLET);
    });
  }

  body.appendParagraph('Prioritized grievance plan')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  body.appendParagraph(
    'Priority combines reported impact and recurrence. Revalidate each fix with the original task, not only a visual review.'
  );

  if (!categories.length) {
    body.appendParagraph('The action plan will appear after the first response.');
  } else {
    const planRows = [[
      'Priority', 'Product area', 'Mentions', 'Planned response', 'Done when'
    ]];
    categories.forEach(function(group) {
      planRows.push([
        group.priority,
        group.category,
        String(group.count),
        actionForCategory_(group.category),
        acceptanceCriteriaForCategory_(group.category),
      ]);
    });
    const planTable = body.appendTable(planRows);
    styleHeaderRow_(planTable);
  }

  body.appendParagraph('Feedback summary')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  if (reviews.length) {
    const summaryRows = [[
      'Reviewer / audience', 'Task', 'Main grievance', 'Requested change', 'Impact'
    ]];
    reviews.forEach(function(review) {
      summaryRows.push([
        review.name + '\n' + review.audience + ' · ' + review.experience,
        review.task,
        review.grievance + '\n\nEvidence: ' + review.evidence,
        review.improvement,
        review.impact,
      ]);
    });
    const summaryTable = body.appendTable(summaryRows);
    styleHeaderRow_(summaryTable);
  }

  body.appendParagraph('Detailed reviewer notes')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  reviews.forEach(function(review, index) {
    body.appendParagraph(
      (index + 1) + '. ' + review.name + ' — ' + review.audience
    ).setHeading(DocumentApp.ParagraphHeading.HEADING2);
    appendLabeledParagraph_(body, 'Experience', review.experience);
    appendLabeledParagraph_(body, 'Task attempted', review.task);
    appendLabeledParagraph_(body, 'What worked', review.worked);
    appendLabeledParagraph_(body, 'Grievance', review.grievance);
    appendLabeledParagraph_(body, 'Evidence and effect', review.evidence);
    appendLabeledParagraph_(body, 'Suggested improvement', review.improvement);
    appendLabeledParagraph_(body, 'Impact', review.impact);
    appendLabeledParagraph_(body, 'Product area', review.feature);
    appendLabeledParagraph_(body, 'Optional rating', review.rating);
  });

  body.appendParagraph('Project links')
    .setHeading(DocumentApp.ParagraphHeading.HEADING1);
  appendLinkedParagraph_(body, 'Feedback form', resources.form.getPublishedUrl());
  appendLinkedParagraph_(body, 'Response spreadsheet', resources.spreadsheet.getUrl());

  doc.saveAndClose();
}

function appendLabeledParagraph_(body, label, value) {
  const paragraph = body.appendParagraph(label + ': ' + value);
  paragraph.editAsText().setBold(0, label.length, true);
}

function appendLinkedParagraph_(body, label, url) {
  const paragraph = body.appendParagraph(label + ': ' + url);
  const start = label.length + 2;
  paragraph.editAsText().setLinkUrl(start, start + url.length - 1, url);
}

function styleHeaderRow_(table) {
  if (table.getNumRows() === 0) return;
  const row = table.getRow(0);
  for (let i = 0; i < row.getNumCells(); i += 1) {
    row.getCell(i).setBackgroundColor('#D9EAF7');
    row.getCell(i).editAsText().setBold(true);
  }
}

function countValues_(items, key) {
  const counts = {};
  items.forEach(function(item) {
    counts[item[key]] = (counts[item[key]] || 0) + 1;
  });
  return Object.keys(counts)
    .map(function(label) { return { label: label, count: counts[label] }; })
    .sort(function(a, b) { return b.count - a.count; });
}

function prepareOverviewSheet_(spreadsheet) {
  const sheet = spreadsheet.getSheets()[0];
  sheet.setName('Overview');
  sheet.getRange('A1:B1').setValues([['MarketLens Feedback System', 'Value']]);
  sheet.getRange('A2:A7').setValues([
    ['Status'],
    ['Reviews collected'],
    ['Minimum required'],
    ['Responder form'],
    ['Form editor'],
    ['Findings report'],
  ]);
  sheet.setFrozenRows(1);
  sheet.getRange('A1:B1').setFontWeight('bold').setBackground('#D9EAF7');
  sheet.autoResizeColumns(1, 2);
}

function writeArtifactLinks_(spreadsheet, form, report) {
  const sheet = spreadsheet.getSheetByName('Overview');
  sheet.getRange('B2:B7').setValues([
    ['Waiting for reviews'],
    [0],
    [CONFIG.minimumReviewers],
    [form.getPublishedUrl()],
    [form.getEditUrl()],
    [report.getUrl()],
  ]);
}

function updateOverview_(spreadsheet, reviewCount, resources) {
  const sheet = spreadsheet.getSheetByName('Overview');
  const met = reviewCount >= CONFIG.minimumReviewers;
  sheet.getRange('B2:B7').setValues([
    [met ? 'Requirement met' : 'Need ' + (CONFIG.minimumReviewers - reviewCount) + ' more review(s)'],
    [reviewCount],
    [CONFIG.minimumReviewers],
    [resources.form.getPublishedUrl()],
    [resources.form.getEditUrl()],
    [resources.report.getUrl()],
  ]);
}

function replaceSubmissionTrigger_(form) {
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'onFeedbackSubmit') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger('onFeedbackSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();
}

function getResources_() {
  const properties = PropertiesService.getScriptProperties();
  const formId = properties.getProperty(CONFIG.propertyKeys.formId);
  const spreadsheetId = properties.getProperty(CONFIG.propertyKeys.spreadsheetId);
  const reportId = properties.getProperty(CONFIG.propertyKeys.reportId);

  if (!formId || !spreadsheetId || !reportId) {
    throw new Error(
      'Feedback system is not configured. Run setupFeedbackSystem() first.'
    );
  }

  return {
    form: FormApp.openById(formId),
    spreadsheet: SpreadsheetApp.openById(spreadsheetId),
    report: DocumentApp.openById(reportId),
  };
}
