// MOCK texts.js for local testing of experiment.js only.
// The real file is site/js/texts.js (written by another builder).
(function () {
  const p1 = "<h2>About this study</h2><p>An AI model has many small units. Each unit responds to a visual concept.</p>";
  const p2 = "<h2>Reference images</h2><p>We show 9 images that activate a unit most (top row) and 9 that activate it least (bottom row).</p>";
  const p2name = p2 + "<p>Above the images you will also see a short name for the concept, produced automatically by a computer program, shown as: <strong>This concept: ...</strong></p>";
  const p3 = "<h2>Your task</h2><p>You then see two new images. Click the one that activates the unit, the one that belongs with the top row. Then say how sure you are.</p>";
  const p4 = "<h2>Plan</h2><p>9 practice trials with feedback, then about 45 trials without feedback.</p>";
  const ex = "<h2>Example</h2>{{EXAMPLE_TRIAL}}<p>The outlined image is the correct answer.</p>";
  const withName = [p1, p2name, p3, p4, ex];
  window.EXP_TEXTS = {
    title: "Image study",
    consentHtml: "<h2>Consent (MOCK)</h2><p>Mock consent text. [CONTACT_EMAIL] [PI_NAME] [INSTITUTION] [ETHICS_COMMITTEE] [ETHICS_REF]</p>",
    instructionPages: { A: [p1, p2, p3, p4, ex], B: withName, C: withName, D: withName },
    practiceIntroHtml: "<p>Now 9 practice trials, with feedback.</p>",
    testIntroHtml: "<p>Practice is over. From now on there is no feedback, and you cannot go back.</p>",
    trialPrompt: "Which image activates this concept? (Which one belongs with the top row?)",
    nameLabel: "This concept:",
    referenceLabels: { high: "Most activating images", low: "Least activating images" },
    confidencePrompt: "How sure are you?",
    confidenceLabels: ["Guessing", "Not very sure", "Somewhat sure", "Quite sure", "Very sure"],
    feedback: { correct: "Correct.", incorrect: "Not quite. The outlined image is the one that activates the concept." },
    questionnaire: [
      { name: "strategy", type: "text", prompt: "In a few words, how did you choose between the two images?" },
      { name: "used_name", type: "multi-choice", conditions: ["B", "C", "D"], prompt: "Did you use the displayed name?",
        options: ["Yes, on most trials", "Yes, on some trials", "Rarely", "No, never"] },
      { name: "age_range", type: "multi-choice", prompt: "Your age range",
        options: ["18-24", "25-34", "35-44", "45-54", "55-64", "65 or older", "Prefer not to say"] },
      { name: "ai_familiarity", type: "multi-choice", prompt: "How familiar are you with artificial intelligence (AI)?",
        options: ["Not at all", "I have heard of it", "I use AI tools", "I have studied machine learning", "I work in AI or machine learning"] }
    ],
    endHtml: "<h2>Thank you</h2><p>Mock debrief.</p>",
    prolificCompletionUrl: "https://app.prolific.com/submissions/complete?cc=COMPLETION_CODE",
    ui: {
      consentAgree: "I agree", consentDecline: "I do not agree",
      noConsentHtml: "<p>You did not agree. Please return the study on Prolific.</p>",
      browserExclusionHtml: "<p>Please use a desktop or laptop computer.</p>",
      fullscreenHtml: "<p>The study will now switch to full screen.</p>", fullscreenButton: "Enter full screen",
      nextButton: "Next", previousButton: "Previous", continueButton: "Continue", submitButton: "Submit",
      exampleTargetCaption: "This one belongs with the top row",
      yourChoice: "Your choice",
      progressLabel: "Progress",
      savingHtml: "<p>Saving your data. Please do not close this page.</p>",
      saveErrorHtml: "<p>Your data could not be saved. Please send us a Prolific message with your Prolific ID. You will still be paid.</p>",
      loadingHtml: "<p>Loading images...</p>",
      loadErrorHtml: "<p>The study could not be loaded. Please try again later.</p>",
      endButton: "Return to Prolific"
    }
  };
})();
