// All text that participants see. experiment.js reads it and adds no text of its own.
//
// Rules for this file:
// - Never name the methods, the datasets or the condition letters in participant text.
// - The same wording is used whatever name (or no name) a round shows.
// - Placeholders in [SQUARE_BRACKETS] must be filled in by the author before launch.
// - 13 Oct. 2026: one introduction page (introHtml, with the "conditions" pop-up), no tutorial and no warm-up
//   announcement; the "i" buttons open the texts of `info`. Volunteers only: no payment, no Prolific.
// - 13 Oct. 2026 (evening): one screen per round (no confidence rating, no feedback); computers, tablets and phones;
//   arrow keys on a keyboard; the browser's back button returns to the previous round.

(function () {
  window.EXP_TEXTS = {
    title: "Image study",

    // Introduction page. The checkbox (id "agree") is required; the "conditions" link opens info.conditions.
    // Elements with class "kbd-only" are shown only on devices with a mouse or a trackpad.
    introHtml:
      "<h1>What does an AI model see in images?</h1>" +
      "<p>AI models that recognise images learn many visual <b>concepts</b> on their own: an object, a part of an object, " +
      "a material, a pattern or a kind of scene. We want to know how easily people can tell what such a concept responds to.</p>" +
      "<p>In each round you will see images that strongly match one concept and images that do not. " +
      "Then you pick, between two new images, the one that matches the concept. Sometimes a short name for the concept is shown. " +
      "There are about 50 rounds; it takes around 10 minutes.</p>" +
      '<p class="kbd-only">On a computer you can also answer with the arrow keys of your keyboard.</p>' +
      '<p class="help-hint">A small <span class="info-btn-sample" aria-hidden="true">i</span> button next to each part of the screen gives more details at any time.</p>' +
      '<label class="agree"><input type="checkbox" id="agree" name="agree" value="yes" required>' +
      '<span>I am 18 or older and I agree to the <button type="button" class="info-link" data-info="conditions">conditions of this study</button></span></label>',

    trialPrompt: "Which image matches this concept?",

    nameLabel: "This concept:",

    // Long labels: two rows of 9 (wide windows). Short labels: two columns of 9 (narrow windows and phones).
    referenceLabels: {
      high: "Images that match the concept most",
      low: "Images that match the concept least",
      highShort: "Match most",
      lowShort: "Match least"
    },

    // Names are fixed: analysis code reads q_strategy, q_used_name, q_age_range, q_ai_familiarity.
    questionnaireIntroHtml: "<h2>Almost done</h2><p>A few short questions to finish.</p>",
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
        options: ["Yes, on most rounds", "Yes, on some rounds", "Rarely", "No, never"]
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
      "<h1>Thank you!</h1>" +
      "<p>You have finished the study. Your answers have been recorded.</p>" +
      "<p><b>About this study.</b> We are testing whether short names, generated automatically " +
      "by computer programs, help people understand what a concept learned by an AI model " +
      "responds to. Some rounds showed no name, and the others showed names from different " +
      "programs. The programs are not perfect: if you saw a name that did not fit the images, " +
      "this may be why.</p>" +
      "<p>Please do not share these details with people who might still take part.</p>" +
      "<p>Questions: [CONTACT_EMAIL].</p>" +
      "<p>You can now close this page.</p>",

    // Detailed explanations behind the small "i" buttons.
    info: {
      conditions:
        "<h3>Conditions of this study</h3>" +
        "<ul>" +
        "<li><b>Age.</b> You must be 18 or older.</li>" +
        "<li><b>Voluntary.</b> Taking part is entirely voluntary and unpaid. You can stop at any time by closing this page; " +
        "your answers are only sent when you reach the end.</li>" +
        "<li><b>Anonymous.</b> We do not ask for your name, e-mail or any information that identifies you.</li>" +
        "<li><b>What we record.</b> Your choices, how long each answer took, your answers to a few short questions at the end, " +
        "and basic browser information (screen size, browser type). Until you finish, your progress is kept in this browser " +
        "so that you can continue if the page is closed or reloaded.</li>" +
        "<li><b>Use of the data.</b> The data are stored securely and used only for research. They may be published in anonymous, " +
        "aggregated form or shared as an anonymous dataset.</li>" +
        "<li><b>Images.</b> The photos come from public research image collections. They show everyday scenes and objects.</li>" +
        "<li><b>Device.</b> A computer, a tablet or a phone all work; on a phone, hold it upright. A larger screen shows the images larger.</li>" +
        "<li><b>Contact.</b> [PI_NAME], [INSTITUTION], [CONTACT_EMAIL].</li>" +
        "</ul>",
      name:
        "<h3>The name of the concept</h3>" +
        "<p>On some rounds a short name is shown. It was produced automatically by a computer program, from the images alone. " +
        "It is often helpful, but it can be too broad, too narrow or simply wrong. Use it as a hint and check it against the images.</p>",
      refsHigh:
        "<h3>Images that match the concept most</h3>" +
        "<p>These are the 9 images, out of thousands, to which the concept responds most strongly. " +
        "Whatever they have in common is what the concept looks for. It can be an object, a part, a material, a colour, a pattern or a kind of scene.</p>",
      refsLow:
        "<h3>Images that match the concept least</h3>" +
        "<p>These images often look similar to the first set, but the concept does not respond to them at all. " +
        "Comparing the two sets helps you see what really matters: what the first images have and the others lack.</p>",
      question:
        "<h3>Your choice</h3>" +
        "<p>Exactly one of the two new images strongly matches the concept: it belongs with the images that match the concept most. " +
        "Click or tap it. The other one does not match, even if it looks similar. If you are unsure, go with your best guess.</p>" +
        "<p>On a keyboard, the arrow keys answer too: <kbd>&larr;</kbd> and <kbd>&rarr;</kbd> pick the left or the right image; " +
        "when the two images are shown one above the other, <kbd>&uarr;</kbd> and <kbd>&darr;</kbd> pick the top or the bottom one.</p>" +
        "<p>Clicked by mistake? Your browser's back button takes you back to the previous round, and its forward button returns to where you were.</p>"
    },

    ui: {
      startButton: "Start",
      submitButton: "Submit",
      closeButton: "Close",
      retryButton: "Try again",
      infoButton: "More information",
      firstImage: "First image",
      secondImage: "Second image",
      yourAnswer: "Your answer",
      // Shown under the two images on devices with a mouse or a trackpad.
      keyHintRow: "Keyboard: <kbd>&larr;</kbd> left image &nbsp;·&nbsp; <kbd>&rarr;</kbd> right image",
      keyHintCol: "Keyboard: <kbd>&uarr;</kbd> top image &nbsp;·&nbsp; <kbd>&darr;</kbd> bottom image",
      rotateHtml: "<p><b>Please hold your phone upright.</b></p><p>The images are larger that way.</p>",
      resumedNote: "Welcome back: you can continue where you left off.",
      loadingHtml: "<p>Loading images, please wait...</p>",
      savingHtml: "<h2>Saving your answers</h2><p>Please do not close this page.</p>",
      saveErrorHtml:
        "<h2>Your answers could not be saved</h2>" +
        "<p>Something went wrong while sending them. Please check your internet connection and press the button below. " +
        "If it still fails, keep this page open and contact us at [CONTACT_EMAIL].</p>",
      loadErrorHtml:
        "<h2>The study could not be loaded</h2>" +
        "<p>Please check your internet connection and reload the page. If the problem " +
        "continues, please contact us at [CONTACT_EMAIL].</p>"
    }
  };
})();
