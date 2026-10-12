// All text that participants see. experiment.js reads it and adds no text of its own.
// Contract: SPEC.md section 5.3.
//
// Rules for this file:
// - Never name the methods, the datasets or the condition letters in participant text.
// - Conditions B, C and D share exactly the same pages (built from NAMED_PAGES below).
//   Condition A says nothing about names.
// - Placeholders in [SQUARE_BRACKETS] and COMPLETION_CODE must be filled in by the author
//   before launch (see DEPLOY.md).
//
// Example page: the last instruction page of every condition holds the token
// {{EXAMPLE_TRIAL}}. experiment.js replaces it with a static copy of a trial, built
// from stimuli/example/example.json and the images written by the stimuli builder:
//   stimuli/example/h0.jpg ... h8.jpg   (top row, strongest matches)
//   stimuli/example/l0.jpg ... l8.jpg   (bottom row, weakest matches)
//   stimuli/example/qpos.jpg            (correct answer, always shown on the right)
//   stimuli/example/qneg.jpg            (wrong answer, shown on the left)

(function () {
  // ---- instruction pages ----

  const PAGE_1 =
    "<h2>What this study is about</h2>" +
    "<p>An AI model has learned many visual <b>concepts</b>. " +
    "A concept is something the model looks for in images: an object, a part of an object, " +
    "a shape, a colour, a texture or a kind of scene.</p>" +
    "<p>Your job is to work out what a concept responds to, just by looking at examples.</p>";

  const PAGE_2_INTRO =
    "<h2>The examples</h2>" +
    "<p>For each concept you will see two rows of 9 images:</p>" +
    "<ul>" +
    "<li><b>Top row:</b> the images that match the concept most strongly.</li>" +
    "<li><b>Bottom row:</b> images that match the concept least.</li>" +
    "</ul>" +
    "<p>Compare the two rows. What do the top images have in common that the bottom images lack?</p>";

  // Within-subject design: every participant sees rounds with and without a name.
  const PAGE_2_NAME =
    "<p>On some rounds, a short name that describes the concept is also shown above the images, like this:</p>" +
    '<div class="concept-name">This concept: <strong class="concept-name-value">...</strong></div>' +
    "<p>The name was produced automatically by a computer program. " +
    "It may or may not be accurate.</p>";

  const PAGE_3 =
    "<h2>Your task</h2>" +
    "<p>Below the two rows you will see <b>two new images</b>. " +
    "Click the one that matches the concept: the one that belongs with the <b>top row</b>.</p>" +
    "<p>Be careful: the two new images often show the same kind of object or scene. " +
    "Look at what the top-row images really share.</p>" +
    "<p>After each choice, tell us how sure you are, from 1 (Guessing) to 5 (Very sure).</p>";

  const PAGE_4 =
    "<h2>How the session works</h2>" +
    "<ul>" +
    "<li>First, <b>9 practice rounds</b>. After each one we tell you if you were right.</li>" +
    "<li>Then the real task: <b>about 45 rounds</b>, with no feedback.</li>" +
    "<li>Each round takes about 10 seconds. Take a good look, but do not overthink it.</li>" +
    "<li>Please use your mouse or touchpad, stay on this page and do not switch tabs until the end.</li>" +
    "</ul>";

  const PAGE_EXAMPLE =
    "<h2>Example</h2>" +
    "<p>This is what a round looks like.</p>" +
    "{{EXAMPLE_TRIAL}}" +
    "<p>The outlined image on the right is the correct answer: it shares what the top-row " +
    "images have in common. The image on the left does not, even if it shows a similar " +
    "kind of thing.</p>" +
    "<p>Click <b>Next</b> to start the practice.</p>";

  const PLAIN_PAGES = [PAGE_1, PAGE_2_INTRO, PAGE_3, PAGE_4, PAGE_EXAMPLE];
  const NAMED_PAGES = [PAGE_1, PAGE_2_INTRO + PAGE_2_NAME, PAGE_3, PAGE_4, PAGE_EXAMPLE];

  window.EXP_TEXTS = {
    title: "Image study",

    consentHtml:
      '<div class="text-page">' +
      "<h2>Information and consent</h2>" +
      "<p><b>Purpose.</b> This study looks at how people interpret what image features " +
      "learned by an AI model respond to.</p>" +
      "<p><b>What you will do.</b> You will look at small sets of images and pick, between two " +
      "new images, the one that belongs with a set. Then you answer a few short questions. " +
      "It takes about <b>12 minutes</b>. You need a desktop or laptop computer.</p>" +
      "<p><b>Voluntary.</b> Taking part is your choice. You can stop at any time by closing " +
      "this page. If you stop early, please return the study on Prolific.</p>" +
      "<p><b>Payment.</b> You will be paid through Prolific, at the amount shown in the study listing.</p>" +
      "<p><b>Your data.</b> We record your answers, response times and basic browser information. " +
      "We do not ask for your name. Data are stored on a private Open Science Framework (OSF) " +
      "project and used for research and scientific publication. Your Prolific ID is used " +
      "only to manage payment and is removed before any data are shared.</p>" +
      "<p><b>Who can take part.</b> You must be 18 or older.</p>" +
      "<p><b>Contact.</b> [PI_NAME], [INSTITUTION], [CONTACT_EMAIL].</p>" +
      "<p><b>Ethics.</b> This study was approved by [ETHICS_COMMITTEE] " +
      "(approval number [APPROVAL_NUMBER]).</p>" +
      "<p>By clicking <b>I agree</b>, you confirm that you are 18 or older, that you have read " +
      "this information, and that you agree to take part.</p>" +
      "</div>",

    // Within-subject design: every participant reads the "mixed" pages (no condition letter is shown).
    instructionPages: {
      mixed: NAMED_PAGES.slice(),
      A: PLAIN_PAGES.slice(),
      B: NAMED_PAGES.slice(),
      C: NAMED_PAGES.slice(),
      D: NAMED_PAGES.slice()
    },

    practiceIntroHtml:
      '<div class="text-page">' +
      "<h2>Practice</h2>" +
      "<p>You will now do <b>9 practice rounds</b>. After each one, we will tell you if you " +
      "picked the right image.</p>" +
      "</div>",

    testIntroHtml:
      '<div class="text-page">' +
      "<h2>The real task starts now</h2>" +
      "<p>Practice is over. From now on you will <b>not</b> be told whether your answer was correct.</p>" +
      "<p>There are about 45 rounds. Once you start, you cannot go back to the instructions.</p>" +
      "<p>Take a good look at each round, but do not overthink it.</p>" +
      "</div>",

    trialPrompt: "Which image matches this concept? (Which one belongs with the top row?)",

    nameLabel: "This concept:",

    referenceLabels: {
      high: "Images that match the concept most",
      low: "Images that match the concept least"
    },

    confidencePrompt: "How sure are you?",

    // 1 (lowest) to 5 (highest), shown left to right.
    confidenceLabels: ["Guessing", "Not very sure", "Somewhat sure", "Quite sure", "Very sure"],

    feedback: {
      correct: "Correct.",
      incorrect: "Not quite. The outlined image is the one that matches the concept."
    },

    // Names are fixed: analysis code reads q_strategy, q_used_name, q_age_range, q_ai_familiarity.
    questionnaire: [
      {
        name: "strategy",
        type: "text",
        prompt: "In a few words, how did you choose between the two images?"
      },
      {
        name: "used_name",
        type: "multi-choice",
        prompt: "When a name was displayed, did you use it?",
        options: ["Yes, on most trials", "Yes, on some trials", "Rarely", "No, never"]
      },
      {
        name: "age_range",
        type: "multi-choice",
        prompt: "Your age range",
        options: ["18-24", "25-34", "35-44", "45-54", "55-64", "65 or older", "Prefer not to say"]
      },
      {
        name: "ai_familiarity",
        type: "multi-choice",
        prompt: "How familiar are you with artificial intelligence (AI)?",
        options: [
          "Not at all",
          "I have heard of it",
          "I use AI tools",
          "I have studied machine learning",
          "I work in AI or machine learning"
        ]
      }
    ],

    endHtml:
      '<div class="text-page">' +
      "<h2>Thank you!</h2>" +
      "<p>You have finished the study.</p>" +
      "<p><b>About this study.</b> We are testing whether short names, generated automatically " +
      "by computer programs, help people understand what a concept learned by an AI model " +
      "responds to. Some rounds showed no name, and the others showed names from different " +
      "programs. The programs are not perfect: if you saw a name that did not fit the images, " +
      "this may be why.</p>" +
      "<p>Please do not share these details with other people who might take part.</p>" +
      "<p>Questions: [CONTACT_EMAIL].</p>" +
      "<p>Click the button below to return to Prolific and confirm your participation. " +
      "You will be redirected automatically in a few seconds.</p>" +
      "</div>",

    prolificCompletionUrl: "https://app.prolific.com/submissions/complete?cc=COMPLETION_CODE",

    ui: {
      consentAgree: "I agree",
      consentDecline: "I do not agree",
      noConsentHtml:
        '<div class="text-page">' +
        "<h2>You chose not to take part</h2>" +
        "<p>Thank you for your time. No data have been saved.</p>" +
        "<p>Please return the study on Prolific (click <b>Stop without completing</b>), " +
        "then you can close this page.</p>" +
        "</div>",
      browserExclusionHtml:
        '<div class="text-page">' +
        "<h2>This device cannot be used</h2>" +
        "<p>This study needs a desktop or laptop computer, with a browser window of at least " +
        "1000 x 650 pixels. Phones and tablets are not supported.</p>" +
        "<p>Please return the study on Prolific. Thank you.</p>" +
        "</div>",
      fullscreenHtml:
        '<div class="text-page">' +
        "<p>The study works best in full screen. Click the button below to switch to full screen.</p>" +
        "</div>",
      fullscreenButton: "Enter full screen",
      nextButton: "Next",
      previousButton: "Previous",
      continueButton: "Continue",
      submitButton: "Submit",
      exampleTargetCaption: "Correct answer",
      yourChoice: "Your choice",
      progressLabel: "Progress",
      savingHtml:
        '<div class="text-page"><p>Saving your answers. Please do not close this page.</p></div>',
      saveErrorHtml:
        '<div class="text-page">' +
        "<h2>Your answers could not be saved</h2>" +
        "<p>Sorry, something went wrong while saving. Please send us a message on Prolific " +
        "with your Prolific ID so that we can sort it out. You will still be paid.</p>" +
        "<p>The button below still completes the study on Prolific.</p>" +
        "</div>",
      loadingHtml: "<p>Loading images, please wait...</p>",
      loadErrorHtml:
        '<div class="text-page">' +
        "<h2>The study could not be loaded</h2>" +
        "<p>Please check your internet connection and reload the page. If the problem " +
        "continues, please return the study on Prolific and send us a message.</p>" +
        "</div>",
      endButton: "Return to Prolific"
    }
  };
})();
